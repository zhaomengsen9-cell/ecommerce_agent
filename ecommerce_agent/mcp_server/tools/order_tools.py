from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from ecommerce_agent.mcp_server.erp_client import erp_client


def register_order_tools(mcp: Any) -> None:
    @mcp.tool()
    def get_sales_order_detail(sales_order: str) -> dict[str, Any]:
        """Get one ERPNext Sales Order document including child rows returned by Frappe."""
        return erp_client.get_doc("Sales Order", sales_order)

    @mcp.tool()
    def analyze_sales_orders(days: int = 30, status: str | None = None, limit: int = 300) -> dict[str, Any]:
        """Analyze recent ERPNext Sales Orders by status, customer, and revenue."""
        from_date = (date.today() - timedelta(days=days)).isoformat()
        filters: list[Any] = [["Sales Order", "transaction_date", ">=", from_date]]
        if status:
            filters.append(["Sales Order", "status", "=", status])
        orders = erp_client.list_docs(
            "Sales Order",
            fields=["name", "transaction_date", "customer", "status", "grand_total", "currency", "delivery_date"],
            filters=filters,
            limit=min(limit, 1000),
            order_by="transaction_date desc",
        )
        by_status: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "grand_total": 0.0})
        by_customer: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "grand_total": 0.0})
        for order in orders:
            status_key = str(order.get("status") or "Unknown")
            customer_key = str(order.get("customer") or "Unknown")
            total = float(order.get("grand_total") or 0)
            by_status[status_key]["count"] += 1
            by_status[status_key]["grand_total"] += total
            by_customer[customer_key]["count"] += 1
            by_customer[customer_key]["grand_total"] += total
        top_customers = sorted(by_customer.items(), key=lambda row: row[1]["grand_total"], reverse=True)[:10]
        return {
            "window_days": days,
            "order_count": len(orders),
            "grand_total": sum(float(order.get("grand_total") or 0) for order in orders),
            "by_status": dict(by_status),
            "top_customers": [{"customer": name, **metrics} for name, metrics in top_customers],
            "sample_orders": orders[:20],
        }

    @mcp.tool()
    def analyze_sales_order_items(days: int = 30, limit: int = 500) -> dict[str, Any]:
        """Analyze ERPNext Sales Order Item child rows for recent orders."""
        from_date = (date.today() - timedelta(days=days)).isoformat()
        rows = erp_client.list_docs(
            "Sales Order Item",
            fields=["parent", "item_code", "item_name", "qty", "amount", "warehouse", "delivery_date", "creation"],
            filters=[["Sales Order Item", "creation", ">=", from_date]],
            limit=min(limit, 2000),
            order_by="creation desc",
        )
        by_item: dict[str, dict[str, Any]] = defaultdict(lambda: {"qty": 0.0, "amount": 0.0, "order_lines": 0})
        for row in rows:
            item_code = str(row.get("item_code") or "Unknown")
            by_item[item_code]["qty"] += float(row.get("qty") or 0)
            by_item[item_code]["amount"] += float(row.get("amount") or 0)
            by_item[item_code]["order_lines"] += 1
        top_items = sorted(by_item.items(), key=lambda row: row[1]["amount"], reverse=True)[:20]
        return {
            "window_days": days,
            "line_count": len(rows),
            "top_items": [{"item_code": item_code, **metrics} for item_code, metrics in top_items],
            "sample_lines": rows[:20],
        }

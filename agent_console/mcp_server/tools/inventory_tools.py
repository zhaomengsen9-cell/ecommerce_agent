from __future__ import annotations

from typing import Any

from agent_console.mcp_server.erp_client import erp_client


def register_inventory_tools(mcp: Any) -> None:
    @mcp.tool()
    def get_inventory_snapshot(item_code: str | None = None, warehouse: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        """Read ERPNext Bin stock quantities by item and/or warehouse."""
        filters: dict[str, Any] = {}
        if item_code:
            filters["item_code"] = item_code
        if warehouse:
            filters["warehouse"] = warehouse
        return erp_client.list_docs(
            "Bin",
            fields=["item_code", "warehouse", "actual_qty", "projected_qty", "ordered_qty", "reserved_qty", "indented_qty", "planned_qty"],
            filters=filters or None,
            limit=min(limit, 1000),
            order_by="projected_qty asc",
        )

    @mcp.tool()
    def find_low_stock_items(threshold: float = 0, warehouse: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Find stock items whose projected quantity is at or below a threshold."""
        filters: list[Any] = [["Bin", "projected_qty", "<=", threshold]]
        if warehouse:
            filters.append(["Bin", "warehouse", "=", warehouse])
        return erp_client.list_docs(
            "Bin",
            fields=["item_code", "warehouse", "actual_qty", "projected_qty", "ordered_qty", "reserved_qty"],
            filters=filters,
            limit=min(limit, 500),
            order_by="projected_qty asc",
        )

    @mcp.tool()
    def suggest_replenishment(threshold: float = 0, limit: int = 50) -> list[dict[str, Any]]:
        """Generate replenishment suggestions from low projected stock Bin records."""
        low_stock = find_low_stock_items(threshold=threshold, limit=limit)
        suggestions: list[dict[str, Any]] = []
        for row in low_stock:
            projected_qty = float(row.get("projected_qty") or 0)
            actual_qty = float(row.get("actual_qty") or 0)
            ordered_qty = float(row.get("ordered_qty") or 0)
            suggestions.append(
                {
                    "item_code": row.get("item_code"),
                    "warehouse": row.get("warehouse"),
                    "actual_qty": actual_qty,
                    "projected_qty": projected_qty,
                    "ordered_qty": ordered_qty,
                    "priority": "high" if projected_qty < 0 else "medium",
                    "recommended_action": "Review demand and create a Material Request or Purchase Order in ERPNext after approval.",
                }
            )
        return suggestions

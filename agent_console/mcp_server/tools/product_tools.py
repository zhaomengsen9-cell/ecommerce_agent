from __future__ import annotations

from typing import Any

from agent_console.mcp_server.erp_client import erp_client
from agent_console.sandbox_gateway.permission import ApprovalRequest, require_approval


def register_product_tools(mcp: Any) -> None:
    @mcp.tool()
    def search_products(keyword: str = "", item_group: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        """Search ERPNext Item records by item name, item code, and optional item group."""
        filters: list[Any] = []
        if keyword:
            filters.append(["Item", "item_name", "like", f"%{keyword}%"])
        if item_group:
            filters.append(["Item", "item_group", "=", item_group])
        return erp_client.list_docs(
            "Item",
            fields=["name", "item_code", "item_name", "item_group", "stock_uom", "disabled", "is_stock_item"],
            filters=filters or None,
            limit=min(limit, 100),
            order_by="modified desc",
        )

    @mcp.tool()
    def get_product_profile(item_code: str) -> dict[str, Any]:
        """Get Item, Item Price, and Bin records for one product."""
        item = erp_client.get_doc("Item", item_code)
        prices = erp_client.list_docs(
            "Item Price",
            fields=["name", "item_code", "price_list", "price_list_rate", "currency", "selling", "buying", "valid_from", "valid_upto"],
            filters={"item_code": item_code},
            limit=50,
            order_by="modified desc",
        )
        bins = erp_client.list_docs(
            "Bin",
            fields=["item_code", "warehouse", "actual_qty", "projected_qty", "ordered_qty", "reserved_qty"],
            filters={"item_code": item_code},
            limit=100,
        )
        return {"item": item, "prices": prices, "inventory_bins": bins}

    @mcp.tool()
    def update_item_price(item_code: str, price_list: str, new_rate: float, reason: str) -> dict[str, Any]:
        """Update the latest Item Price for a product and price list. Requires approval."""
        matches = erp_client.list_docs(
            "Item Price",
            fields=["name", "item_code", "price_list", "price_list_rate", "currency"],
            filters={"item_code": item_code, "price_list": price_list},
            limit=1,
            order_by="modified desc",
        )
        if not matches:
            raise ValueError(f"No Item Price found for item_code={item_code!r}, price_list={price_list!r}")
        current = matches[0]
        approval = require_approval(
            ApprovalRequest(
                action="update_item_price",
                risk="Price changes can affect storefront revenue, margin, and downstream orders.",
                details=f"{item_code} {price_list}: {current.get('price_list_rate')} -> {new_rate}. Reason: {reason}",
                tool_name="update_item_price",
                tool_args={"item_code": item_code, "price_list": price_list, "new_rate": new_rate, "reason": reason},
            )
        )
        if approval:
            return approval
        return erp_client.update_doc("Item Price", current["name"], {"price_list_rate": new_rate})

    @mcp.tool()
    def set_product_disabled(item_code: str, disabled: bool, reason: str) -> dict[str, Any]:
        """Enable or disable an ERPNext Item. Requires approval."""
        approval = require_approval(
            ApprovalRequest(
                action="set_product_disabled",
                risk="Changing product availability can affect selling, fulfillment, and catalog operations.",
                details=f"item_code={item_code}, disabled={disabled}, reason={reason}",
                tool_name="set_product_disabled",
                tool_args={"item_code": item_code, "disabled": disabled, "reason": reason},
            )
        )
        if approval:
            return approval
        return erp_client.update_doc("Item", item_code, {"disabled": 1 if disabled else 0})

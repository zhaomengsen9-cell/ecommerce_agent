from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from ecommerce_agent.mcp_server.erp_client import erp_client
from ecommerce_agent.mcp_server.tools import (
    register_inventory_tools,
    register_marketing_tools,
    register_order_tools,
    register_product_tools,
)
from ecommerce_agent.sandbox_gateway.permission import ApprovalRequest, require_approval


mcp = FastMCP("frappe-ecommerce-erp")


@mcp.tool()
def erp_ping() -> dict[str, Any]:
    """Check whether the Frappe/ERPNext API is reachable."""
    return erp_client.ping()


@mcp.tool()
def erp_list_docs(
    doctype: str,
    fields: list[str] | None = None,
    filters: dict[str, Any] | list[Any] | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Generic read-only list operation for Frappe documents."""
    return erp_client.list_docs(doctype=doctype, fields=fields, filters=filters, limit=limit)


@mcp.tool()
def erp_get_doc(doctype: str, name: str) -> dict[str, Any]:
    """Generic read-only get operation for one Frappe document."""
    return erp_client.get_doc(doctype=doctype, name=name)


@mcp.tool()
def erp_create_doc(doctype: str, doc: dict[str, Any], reason: str) -> dict[str, Any]:
    """Generic write operation for creating Frappe documents. Requires approval."""
    require_approval(
        ApprovalRequest(
            action="erp_create_doc",
            risk="Creates ERP data and may affect downstream business workflows.",
            details=f"doctype={doctype}, reason={reason}, doc_keys={sorted(doc.keys())}",
        )
    )
    return erp_client.create_doc(doctype=doctype, doc=doc)


@mcp.tool()
def erp_update_doc(doctype: str, name: str, updates: dict[str, Any], reason: str) -> dict[str, Any]:
    """Generic write operation for updating Frappe documents. Requires approval."""
    require_approval(
        ApprovalRequest(
            action="erp_update_doc",
            risk="Updates ERP data and may affect customer-facing or financial records.",
            details=f"doctype={doctype}, name={name}, reason={reason}, update_keys={sorted(updates.keys())}",
        )
    )
    return erp_client.update_doc(doctype=doctype, name=name, updates=updates)


register_product_tools(mcp)
register_order_tools(mcp)
register_inventory_tools(mcp)
register_marketing_tools(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

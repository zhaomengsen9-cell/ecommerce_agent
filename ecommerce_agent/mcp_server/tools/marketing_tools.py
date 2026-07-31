from __future__ import annotations

from typing import Any

from ecommerce_agent.mcp_server.erp_client import erp_client
from ecommerce_agent.rag_system.wiki_manager import KnowledgeBase
from ecommerce_agent.sandbox_gateway.permission import ApprovalRequest, require_approval


knowledge_base = KnowledgeBase()


def register_marketing_tools(mcp: Any) -> None:
    @mcp.tool()
    def retrieve_operation_policy(query: str, k: int = 4) -> list[dict[str, Any]]:
        """Retrieve ecommerce operation policies from the local Wiki knowledge base."""
        return [hit.__dict__ for hit in knowledge_base.search(query, k=k)]

    @mcp.tool()
    def draft_campaign_strategy(goal: str, target_items: list[str] | None = None, budget: float | None = None) -> dict[str, Any]:
        """Draft a marketing campaign strategy without writing ERP data."""
        policy_hits = retrieve_operation_policy(query=f"营销 促销 库存 毛利 审批 {goal}", k=4)
        return {
            "goal": goal,
            "target_items": target_items or [],
            "budget": budget,
            "policy_context": policy_hits,
            "draft": {
                "audience": "Define target customer segment before execution.",
                "offer": "Prefer bundles/member benefits for low-margin or low-stock items.",
                "inventory_guardrail": "Check projected stock before promotion.",
                "approval_required": True,
                "metrics": ["sales_amount", "gross_margin", "stockout_rate", "return_rate"],
            },
        }

    @mcp.tool()
    def create_campaign(campaign_name: str, description: str, reason: str) -> dict[str, Any]:
        """Create an ERPNext Campaign document. Requires approval."""
        require_approval(
            ApprovalRequest(
                action="create_campaign",
                risk="Campaign creation can trigger customer-facing and operational workflows.",
                details=f"campaign_name={campaign_name}, reason={reason}",
            )
        )
        return erp_client.create_doc("Campaign", {"campaign_name": campaign_name, "description": description})

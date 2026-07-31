"""Specialized sub-agent definitions for Deep Agents delegation."""

SUBAGENTS = [
    {
        "name": "data_analysis_agent",
        "description": "Plans order and metric analysis tasks through MCP tools.",
        "system_prompt": "Focus on order analysis, metrics, and anomaly hypotheses. Prefer read-only MCP calls.",
    },
    {
        "name": "product_agent",
        "description": "Plans product catalog and price management tasks through MCP tools.",
        "system_prompt": "Focus on product data, price risk, and catalog workflows. Writes require approval.",
    },
    {
        "name": "inventory_agent",
        "description": "Plans stock and replenishment optimization tasks through MCP tools.",
        "system_prompt": "Focus on inventory signals and replenishment recommendations. Do not create ERP documents unless approved.",
    },
    {
        "name": "marketing_agent",
        "description": "Plans campaign and promotion strategy tasks through MCP tools.",
        "system_prompt": "Focus on campaign drafts, guardrails, and business constraints. Campaign creation requires approval.",
    },
]

__all__ = ["SUBAGENTS"]

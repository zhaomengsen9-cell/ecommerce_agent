from __future__ import annotations

import asyncio
import argparse
import json
import sys
from typing import Any

from ecommerce_agent.agents.sub_agents import SUBAGENTS
from ecommerce_agent.config import ROOT, settings


HARNESS_INSTRUCTIONS = """You are the supervisor agent for an ecommerce ERP sandbox.

Architecture:
- You do not connect to ERPNext directly.
- You discover and call ERP capabilities through the local MCP server.
- You must maintain a readable todo plan with the built-in write_todos tool before multi-step work.
- Update the todo plan when the task changes or a step completes.
- You plan tasks, delegate where useful, manage context, and request approval for risky writes.
- Prefer business-specific MCP tools over generic ERP tools.
- Use product tools for Item and Item Price work, order tools for Sales Order analysis, inventory tools for Bin stock checks, and marketing/RAG tools for campaign planning.
- Use generic erp_create_doc and erp_update_doc only when no business-specific tool exists.
- Never invent ERP data. If tool results are empty or incomplete, say so explicitly.
- For high-risk write operations, explain the business reason and wait for approval before execution.
- Always explain completed steps, tool-backed findings, pending approvals, and remaining implementation gaps clearly.
"""


def mcp_stdio_config() -> dict[str, Any]:
    return {
        "erp": {
            "command": sys.executable,
            "args": ["-m", "ecommerce_agent.mcp_server.erp_server"],
            "transport": "stdio",
            "cwd": str(ROOT),
        }
    }


async def build_agent():
    from deepagents import create_deep_agent
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(mcp_stdio_config())
    tools = await client.get_tools()
    return create_deep_agent(
        tools=tools,
        system_prompt=HARNESS_INSTRUCTIONS,
        subagents=SUBAGENTS,
        interrupt_on={
            "erp_create_doc": True,
            "erp_update_doc": True,
            "update_item_price": True,
            "set_product_disabled": True,
            "create_campaign": True,
        },
        model=settings.agent_model,
    )


async def run_task(task: str) -> Any:
    agent = await build_agent()
    return await agent.ainvoke({"messages": [{"role": "user", "content": task}]})


def run_task_sync(task: str) -> Any:
    return asyncio.run(run_task(task))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ecommerce Deep Agent supervisor.")
    parser.add_argument("task", nargs="*", help="Business task for the agent.")
    args = parser.parse_args()
    task = " ".join(args.task).strip()
    if not task:
        task = input("Task: ").strip()
    if not task:
        raise SystemExit("No task provided.")
    print(_format_result(run_task_sync(task)))


def _format_result(result: Any) -> str:
    if isinstance(result, dict) and result.get("messages"):
        last = result["messages"][-1]
        content = getattr(last, "content", None)
        if content:
            return str(content)
        if isinstance(last, dict) and last.get("content"):
            return str(last["content"])
    return json.dumps(result, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    main()

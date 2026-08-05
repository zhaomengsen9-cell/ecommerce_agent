from __future__ import annotations

import asyncio
import argparse
import json
import sys
from typing import Any

from agent_console.agents.hitl_tools import request_human_input
from agent_console.agents.sub_agents import SUBAGENTS
from agent_console.config import ROOT, settings


FALLBACK_INSTRUCTIONS = """You are the supervisor agent for an ecommerce ERP sandbox.
Use MCP tools to inspect ERPNext data, maintain todos for multi-step tasks, and request approval before risky writes.
Never invent ERP data.
"""


def mcp_stdio_config() -> dict[str, Any]:
    return {
        "erp": {
            "command": sys.executable,
            "args": ["-m", "agent_console.mcp_server.erp_server"],
            "transport": "stdio",
            "cwd": str(ROOT),
        }
    }


async def build_agent():
    from deepagents import create_deep_agent
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(mcp_stdio_config())
    tools = await client.get_tools()
    tools.append(request_human_input)
    return create_deep_agent(
        tools=tools,
        system_prompt=load_system_prompt(),
        subagents=SUBAGENTS,
        model=settings.agent_model,
    )


def load_system_prompt() -> str:
    instructions_path = ROOT / "AGENT.md"
    if not instructions_path.exists():
        return FALLBACK_INSTRUCTIONS
    content = instructions_path.read_text(encoding="utf-8").strip()
    return content or FALLBACK_INSTRUCTIONS


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

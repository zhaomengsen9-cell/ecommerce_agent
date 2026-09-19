from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ToolCallRequest
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from agent_console.backend.db import db_session
from agent_console.backend.db_models import AgentTask


class ToolCallLimitExceeded(RuntimeError):
    """Raised when an Agent task has exhausted its tool-call budget."""


@dataclass
class ToolCallBudget:
    """Persistent, task-scoped budget shared by the main and sub agents."""

    task_id: str | None
    max_calls: int
    local_count: int = 0

    @property
    def count(self) -> int:
        if self.task_id is None:
            return self.local_count
        with db_session() as session:
            task = session.get(AgentTask, self.task_id)
            return int(task.tool_call_count) if task is not None else self.local_count

    def reserve(self, tool_name: str) -> int:
        """Atomically reserve one call before the underlying tool runs."""
        if self.max_calls < 1:
            raise ToolCallLimitExceeded("Agent task tool-call limit must be at least 1.")

        if self.task_id is None:
            if self.local_count >= self.max_calls:
                raise ToolCallLimitExceeded(self._message(tool_name))
            self.local_count += 1
            return self.local_count

        with db_session() as session:
            task = session.query(AgentTask).filter(AgentTask.id == self.task_id).with_for_update().one_or_none()
            if task is None:
                raise ToolCallLimitExceeded(f"Agent task not found while calling tool {tool_name!r}.")
            limit = int(task.max_tool_calls or self.max_calls)
            if int(task.tool_call_count or 0) >= limit:
                raise ToolCallLimitExceeded(self._message(tool_name, limit=limit, count=int(task.tool_call_count or 0)))
            task.tool_call_count = int(task.tool_call_count or 0) + 1
            task.updated_at = datetime.now(timezone.utc)
            self.max_calls = limit
            return int(task.tool_call_count)

    def _message(self, tool_name: str, *, limit: int | None = None, count: int | None = None) -> str:
        effective_limit = self.max_calls if limit is None else limit
        effective_count = self.local_count if count is None else count
        return (
            f"Agent task exceeded maximum tool call limit ({effective_limit}) "
            f"before calling {tool_name!r}; calls_used={effective_count}."
        )


class ToolCallBudgetMiddleware(AgentMiddleware[Any, Any, Any]):
    """Count every tool call, including calls made by delegated subagents."""

    name = "ToolCallBudgetMiddleware"

    def __init__(self, budget: ToolCallBudget) -> None:
        super().__init__()
        self.budget = budget

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> ToolMessage | Command[Any]:
        self.budget.reserve(str(request.tool_call.get("name") or "unknown"))
        return handler(request)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> ToolMessage | Command[Any]:
        self.budget.reserve(str(request.tool_call.get("name") or "unknown"))
        return await handler(request)

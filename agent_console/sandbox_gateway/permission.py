from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_console.config import settings


@dataclass(frozen=True)
class ApprovalRequest:
    action: str
    risk: str
    details: str
    tool_name: str
    tool_args: dict[str, Any]


def require_approval(request: ApprovalRequest) -> dict[str, Any] | None:
    if settings.human_approval_mode == "off":
        return None

    if settings.human_approval_mode == "web":
        return {
            "approval_required": True,
            "action": request.action,
            "risk": request.risk,
            "details": request.details,
            "tool_name": request.tool_name,
            "tool_args": request.tool_args,
        }

    print("\nHuman approval required")
    print(f"Action: {request.action}")
    print(f"Risk: {request.risk}")
    print(f"Details: {request.details}")
    answer = input("Approve? Type YES to continue: ").strip()
    if answer != "YES":
        raise PermissionError(f"Rejected high-risk action: {request.action}")
    return None

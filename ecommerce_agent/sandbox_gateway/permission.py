from __future__ import annotations

from dataclasses import dataclass

from ecommerce_agent.config import settings


@dataclass(frozen=True)
class ApprovalRequest:
    action: str
    risk: str
    details: str


def require_approval(request: ApprovalRequest) -> None:
    if settings.human_approval_mode == "off":
        return

    print("\nHuman approval required")
    print(f"Action: {request.action}")
    print(f"Risk: {request.risk}")
    print(f"Details: {request.details}")
    answer = input("Approve? Type YES to continue: ").strip()
    if answer != "YES":
        raise PermissionError(f"Rejected high-risk action: {request.action}")

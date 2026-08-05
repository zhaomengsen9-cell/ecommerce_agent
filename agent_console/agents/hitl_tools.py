from __future__ import annotations

from typing import Any


def request_human_input(question: str, reason: str, required_fields: list[str] | None = None) -> dict[str, Any]:
    """Pause the task and ask the user for missing information before continuing."""
    return {
        "human_input_required": True,
        "question": question,
        "reason": reason,
        "required_fields": required_fields or [],
    }

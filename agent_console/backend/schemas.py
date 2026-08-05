from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    roles: list[str]


class UserResponse(BaseModel):
    username: str
    roles: list[str]


class RunTaskRequest(BaseModel):
    prompt: str = Field(min_length=1)
    conversation_id: str | None = None


class RunTaskResponse(BaseModel):
    task_id: str
    conversation_id: str
    status: str


class TaskStatusResponse(BaseModel):
    task_id: str
    conversation_id: str | None = None
    conversation_title: str | None = None
    conversation_summary: str | None = None
    prompt: str
    status: Literal["queued", "running", "waiting_approval", "needs_input", "succeeded", "failed", "cancelled"]
    created_by: str
    created_at: str
    updated_at: str
    result: Any | None = None
    approval: Any | None = None
    input_request: Any | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    ok: bool
    detail: Any


class MemoryCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    memory_type: str = "manual_note"
    conversation_id: str | None = None


class MemoryUpdateRequest(BaseModel):
    content: str = Field(min_length=1)
    memory_type: str | None = None


class MemoryResponse(BaseModel):
    id: str
    conversation_id: str | None = None
    source_task_id: str | None = None
    memory_type: str
    content: str
    metadata: Any | None = None
    created_at: str
    updated_at: str


class ApprovalDecisionRequest(BaseModel):
    note: str | None = None


class ApprovalResponse(BaseModel):
    id: str
    task_id: str
    status: str
    action: str
    risk: str
    details: str
    tool_name: str
    tool_args: Any
    decision_note: str | None = None
    execution_result: Any | None = None
    created_at: str
    decided_at: str | None = None


class HumanInputRequest(BaseModel):
    response: str = Field(min_length=1)

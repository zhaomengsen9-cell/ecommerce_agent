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
    prompt: str
    status: Literal["queued", "running", "waiting_approval", "needs_input", "succeeded", "failed", "cancelled"]
    created_by: str
    created_at: str
    updated_at: str
    result: Any | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    ok: bool
    detail: Any

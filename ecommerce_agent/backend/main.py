from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ecommerce_agent.backend.auth import CurrentUser, authenticate, create_token, get_current_user
from ecommerce_agent.backend.schemas import (
    HealthResponse,
    LoginRequest,
    LoginResponse,
    RunTaskRequest,
    RunTaskResponse,
    TaskStatusResponse,
    UserResponse,
)
from ecommerce_agent.backend.db import init_db
from ecommerce_agent.backend.task_store import create_task, get_task, list_tasks, reset_stale_tasks
from ecommerce_agent.mcp_server.erp_client import ERPClientError, erp_client


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    reset_stale_tasks()
    yield


app = FastAPI(title="ERPNext Ecommerce Agent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://192\.168\.\d+\.\d+:5173",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    user = authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return LoginResponse(token=create_token(user), username=user.username, roles=user.roles)


@app.get("/api/auth/me", response_model=UserResponse)
def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> UserResponse:
    return UserResponse(username=user.username, roles=user.roles)


@app.get("/api/erp/health", response_model=HealthResponse)
def erp_health(_: Annotated[CurrentUser, Depends(get_current_user)]) -> HealthResponse:
    try:
        return HealthResponse(ok=True, detail=erp_client.ping())
    except (ERPClientError, OSError) as exc:
        return HealthResponse(ok=False, detail=str(exc))


@app.post("/api/agent/run", response_model=RunTaskResponse)
async def run_agent_task(payload: RunTaskRequest, user: Annotated[CurrentUser, Depends(get_current_user)]) -> RunTaskResponse:
    task = create_task(payload.prompt, user.username, payload.conversation_id)
    return RunTaskResponse(task_id=task["task_id"], conversation_id=task["conversation_id"], status=task["status"])


@app.get("/api/agent/tasks", response_model=list[TaskStatusResponse])
def tasks(_: Annotated[CurrentUser, Depends(get_current_user)]) -> list[TaskStatusResponse]:
    return [TaskStatusResponse(**task) for task in list_tasks()]


@app.get("/api/agent/tasks/{task_id}", response_model=TaskStatusResponse)
def task_status(task_id: str, _: Annotated[CurrentUser, Depends(get_current_user)]) -> TaskStatusResponse:
    task = get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskStatusResponse(**task)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

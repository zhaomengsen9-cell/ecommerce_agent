from __future__ import annotations

from typing import Any

from redis import Redis
from rq import Queue

from agent_console.config import settings


def get_redis_connection() -> Redis:
    return Redis.from_url(settings.redis_url)


def get_task_queue() -> Queue:
    return Queue(
        name=settings.agent_queue_name,
        connection=get_redis_connection(),
        default_timeout=settings.agent_job_timeout,
    )


def enqueue_agent_task(task_id: str) -> Any:
    return get_task_queue().enqueue(
        "agent_console.backend.task_store.execute_task_job",
        task_id,
        job_id=f"agent-task:{task_id}",
        result_ttl=86400,
        failure_ttl=604800,
    )


def enqueue_approval_task(task_id: str, approval_id: str) -> Any:
    return get_task_queue().enqueue(
        "agent_console.backend.task_store.continue_after_approval_job",
        task_id,
        job_id=f"agent-approval:{approval_id}",
        result_ttl=86400,
        failure_ttl=604800,
    )


def enqueue_human_input_task(task_id: str, response: str, input_request: dict[str, Any] | None) -> Any:
    return get_task_queue().enqueue(
        "agent_console.backend.task_store.continue_after_human_input_job",
        task_id,
        response,
        input_request,
        result_ttl=86400,
        failure_ttl=604800,
    )

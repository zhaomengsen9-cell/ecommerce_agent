from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from ecommerce_agent.agents.main_agent import run_task
from ecommerce_agent.backend.db import db_session
from ecommerce_agent.backend.models import AgentConversation, AgentTask, User


def create_task(prompt: str, username: str, conversation_id: str | None = None) -> dict[str, Any]:
    now = _now()
    task_id = str(uuid.uuid4())
    with db_session() as session:
        user = session.query(User).filter(User.username == username, User.status == "active").one_or_none()
        if user is None:
            raise ValueError(f"User not found: {username}")
        conversation = None
        if conversation_id:
            conversation = (
                session.query(AgentConversation)
                .filter(AgentConversation.id == conversation_id, AgentConversation.user_id == user.id)
                .one_or_none()
            )
        if conversation is None:
            conversation = AgentConversation(
                id=str(uuid.uuid4()),
                user_id=user.id,
                title=_conversation_title(prompt),
                created_at=now,
                updated_at=now,
            )
            session.add(conversation)
            session.flush()
        else:
            conversation.updated_at = now
            if not conversation.title or conversation.title == "新的运营会话":
                conversation.title = _conversation_title(prompt)
        task = AgentTask(
            id=task_id,
            conversation_id=conversation.id,
            user_id=user.id,
            title=prompt[:120],
            prompt=prompt,
            status="queued",
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        session.flush()
        record = _serialize_task(task)
    asyncio.create_task(_execute(task_id, prompt))
    return record


def reset_stale_tasks(max_age_minutes: int = 15) -> None:
    cutoff = _now() - timedelta(minutes=max_age_minutes)
    with db_session() as session:
        stale_tasks = (
            session.query(AgentTask)
            .filter(AgentTask.status.in_(["queued", "running"]), AgentTask.updated_at < cutoff)
            .all()
        )
        for task in stale_tasks:
            task.status = "failed"
            task.error_message = "Task was left queued/running after a server restart or scheduler interruption."
            task.finished_at = _now()
            task.updated_at = task.finished_at


def get_task(task_id: str) -> dict[str, Any] | None:
    with db_session() as session:
        task = session.query(AgentTask).filter(AgentTask.id == task_id).one_or_none()
        return _serialize_task(task) if task is not None else None


def list_tasks() -> list[dict[str, Any]]:
    with db_session() as session:
        tasks = session.query(AgentTask).order_by(AgentTask.created_at.desc()).all()
        return [_serialize_task(task) for task in tasks]


async def _execute(task_id: str, prompt: str) -> None:
    now = _now()
    with db_session() as session:
        task = session.get(AgentTask, task_id)
        if task is None:
            return
        task.status = "running"
        task.started_at = now
        task.updated_at = now
    try:
        result = _json_safe(await run_task(_build_agent_prompt(task_id, prompt)))
        with db_session() as session:
            task = session.get(AgentTask, task_id)
            if task is None:
                return
            task.result = result
            task.status = "succeeded"
            task.finished_at = _now()
            task.updated_at = task.finished_at
    except Exception as exc:
        with db_session() as session:
            task = session.get(AgentTask, task_id)
            if task is None:
                return
            task.error_message = str(exc)
            task.status = "failed"
            task.finished_at = _now()
            task.updated_at = task.finished_at


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_task(task: AgentTask) -> dict[str, Any]:
    return {
        "task_id": task.id,
        "conversation_id": task.conversation_id,
        "conversation_title": task.conversation.title if task.conversation is not None else None,
        "prompt": task.prompt,
        "status": task.status,
        "created_by": task.user.username,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "result": task.result,
        "error": task.error_message,
    }


def _conversation_title(prompt: str) -> str:
    title = " ".join(prompt.replace("\n", " ").split()).strip()
    for prefix in ("请帮我", "帮我", "分析", "查询", "生成一份", "生成"):
        if title.startswith(prefix):
            title = title[len(prefix) :].strip()
    for marker in ("只分析", "不要修改", "。", "！", "？", "，", ",", "；", ";", "、"):
        if marker in title:
            title = title.split(marker, 1)[0].strip()
    return (title[:24] + "...") if len(title) > 24 else title or "新的运营会话"


def _json_safe(value: Any) -> Any:
    import json

    return json.loads(json.dumps(_to_jsonable(value), ensure_ascii=False, default=str))


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _to_jsonable(_redact_reasoning(key, item)) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "content") and (hasattr(value, "type") or value.__class__.__name__.endswith("Message")):
        return {
            "type": getattr(value, "type", value.__class__.__name__),
            "name": getattr(value, "name", None),
            "content": getattr(value, "content", ""),
            "tool_calls": _to_jsonable(getattr(value, "tool_calls", [])),
            "invalid_tool_calls": _to_jsonable(getattr(value, "invalid_tool_calls", [])),
        }
    return value


def _redact_reasoning(key: Any, value: Any) -> Any:
    if str(key) in {"reasoning_content", "reasoning", "additional_kwargs", "response_metadata", "usage_metadata"}:
        return None
    return value


def _build_agent_prompt(task_id: str, prompt: str) -> str:
    with db_session() as session:
        current = session.get(AgentTask, task_id)
        if current is None or not current.conversation_id:
            return prompt
        previous_tasks = (
            session.query(AgentTask)
            .filter(
                AgentTask.conversation_id == current.conversation_id,
                AgentTask.id != current.id,
                AgentTask.created_at < current.created_at,
            )
            .order_by(AgentTask.created_at.desc())
            .limit(4)
            .all()
        )
        if not previous_tasks:
            return prompt
        rows = []
        for index, task in enumerate(reversed(previous_tasks), start=1):
            rows.append(
                f"{index}. 用户任务：{task.prompt}\n"
                f"   状态：{task.status}\n"
                f"   结果摘要：{_extract_result_summary(task.result, task.error_message)}"
            )
    return (
        "以下是同一会话内的近期上下文，请只把它作为业务背景，不要重复执行旧任务。\n\n"
        + "\n\n".join(rows)
        + "\n\n当前用户的新任务：\n"
        + prompt
    )


def _extract_result_summary(result: Any, error_message: str | None) -> str:
    if error_message:
        return error_message[:500]
    if not result:
        return "暂无结果"
    if isinstance(result, dict) and result.get("messages"):
        last = result["messages"][-1]
        content = last.get("content") if isinstance(last, dict) else getattr(last, "content", "")
        return str(content)[:800] if content else "暂无结果"
    return str(result)[:800]

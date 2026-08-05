from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from agent_console.agents.main_agent import run_task
from agent_console.backend.db import db_session
from agent_console.backend.db_models import AgentApproval, AgentConversation, AgentMemory, AgentTask, User
from agent_console.mcp_server.erp_client import erp_client


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
            .filter(AgentTask.status.in_(["queued", "running", "needs_input"]), AgentTask.updated_at < cutoff)
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
            approval_payload = _find_approval_payload(result)
            if approval_payload:
                approval = _create_approval(session, task, approval_payload)
                task.result = result
                task.status = "waiting_approval"
                task.updated_at = _now()
                task.plan = {"pending_approval_id": approval.id}
                return
            human_input_payload = _find_human_input_payload(result)
            if human_input_payload:
                task.result = result
                task.status = "needs_input"
                task.updated_at = _now()
                task.plan = {"pending_human_input": human_input_payload}
                return
            task.result = result
            task.status = "succeeded"
            task.finished_at = _now()
            task.updated_at = task.finished_at
            _update_conversation_memory(session, task)
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
        "conversation_summary": task.conversation.summary if task.conversation is not None else None,
        "prompt": task.prompt,
        "status": task.status,
        "created_by": task.user.username,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
        "result": task.result,
        "approval": _serialize_approval(_latest_approval_for_task(task.id)),
        "input_request": task.plan.get("pending_human_input") if isinstance(task.plan, dict) else None,
        "error": task.error_message,
    }


def approve_task(task_id: str, username: str, note: str | None = None) -> dict[str, Any]:
    with db_session() as session:
        approval = _get_pending_approval(session, task_id, username)
        approval.status = "approved"
        approval.decision_note = note
        approval.decided_at = _now()
        task = session.get(AgentTask, task_id)
        if task is None:
            raise LookupError("Task not found")
        task.status = "running"
        task.updated_at = _now()
        record = _serialize_approval(approval)
    asyncio.create_task(_continue_after_approval(task_id))
    return record


def reject_task(task_id: str, username: str, note: str | None = None) -> dict[str, Any]:
    with db_session() as session:
        approval = _get_pending_approval(session, task_id, username)
        approval.status = "rejected"
        approval.decision_note = note
        approval.decided_at = _now()
        task = session.get(AgentTask, task_id)
        if task is None:
            raise LookupError("Task not found")
        task.status = "cancelled"
        task.error_message = "User rejected the pending high-risk ERP operation."
        task.finished_at = _now()
        task.updated_at = task.finished_at
        task.result = {
            "messages": [
                {
                    "type": "ai",
                    "content": f"用户已拒绝执行高风险操作 `{approval.tool_name}`。ERP 数据未修改。",
                }
            ]
        }
        return _serialize_approval(approval)


def provide_task_input(task_id: str, username: str, response: str) -> dict[str, Any]:
    with db_session() as session:
        task = (
            session.query(AgentTask)
            .join(User, AgentTask.user_id == User.id)
            .filter(AgentTask.id == task_id, User.username == username, AgentTask.status == "needs_input")
            .one_or_none()
        )
        if task is None:
            raise LookupError("Task waiting for input not found")
        input_request = task.plan.get("pending_human_input") if isinstance(task.plan, dict) else None
        task.plan = {**(task.plan or {}), "human_input_response": response, "pending_human_input": None}
        task.status = "running"
        task.updated_at = _now()
        record = _serialize_task(task)
    asyncio.create_task(_continue_after_human_input(task_id, response, input_request))
    return record


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


async def _continue_after_approval(task_id: str) -> None:
    try:
        with db_session() as session:
            approval = (
                session.query(AgentApproval)
                .filter(AgentApproval.task_id == task_id, AgentApproval.status == "approved")
                .order_by(AgentApproval.decided_at.desc())
                .first()
            )
            task = session.get(AgentTask, task_id)
            if approval is None or task is None:
                return
            execution_result = _json_safe(_execute_approved_tool(approval.tool_name, approval.tool_args))
            approval.execution_result = execution_result
            task.updated_at = _now()
            continuation_prompt = _build_approval_continuation_prompt(task.prompt, approval, execution_result)
        result = _json_safe(await run_task(continuation_prompt))
        with db_session() as session:
            task = session.get(AgentTask, task_id)
            approval = (
                session.query(AgentApproval)
                .filter(AgentApproval.task_id == task_id, AgentApproval.status == "approved")
                .order_by(AgentApproval.decided_at.desc())
                .first()
            )
            if task is None:
                return
            task.result = result
            task.status = "succeeded"
            task.finished_at = _now()
            task.updated_at = task.finished_at
            if approval is not None:
                approval.status = "executed"
                approval.execution_result = approval.execution_result or {}
            _update_conversation_memory(session, task)
    except Exception as exc:
        with db_session() as session:
            task = session.get(AgentTask, task_id)
            if task is None:
                return
            task.error_message = str(exc)
            task.status = "failed"
            task.finished_at = _now()
            task.updated_at = task.finished_at


def _redact_reasoning(key: Any, value: Any) -> Any:
    if str(key) in {"reasoning_content", "reasoning", "additional_kwargs", "response_metadata", "usage_metadata"}:
        return None
    return value


def _find_approval_payload(value: Any) -> dict[str, Any] | None:
    import json

    if isinstance(value, dict):
        if value.get("approval_required") is True:
            return value
        for item in value.values():
            found = _find_approval_payload(item)
            if found:
                return found
    if isinstance(value, list | tuple):
        for item in value:
            found = _find_approval_payload(item)
            if found:
                return found
    if isinstance(value, str) and "approval_required" in value:
        try:
            parsed = json.loads(value)
        except ValueError:
            return None
        return _find_approval_payload(parsed)
    return None


def _find_human_input_payload(value: Any) -> dict[str, Any] | None:
    import json

    if isinstance(value, dict):
        if value.get("human_input_required") is True:
            return value
        for item in value.values():
            found = _find_human_input_payload(item)
            if found:
                return found
    if isinstance(value, list | tuple):
        for item in value:
            found = _find_human_input_payload(item)
            if found:
                return found
    if isinstance(value, str) and "human_input_required" in value:
        try:
            parsed = json.loads(value)
        except ValueError:
            return None
        return _find_human_input_payload(parsed)
    return None


async def _continue_after_human_input(task_id: str, response: str, input_request: dict[str, Any] | None) -> None:
    try:
        with db_session() as session:
            task = session.get(AgentTask, task_id)
            if task is None:
                return
            continuation_prompt = _build_human_input_continuation_prompt(task.prompt, response, input_request)
        result = _json_safe(await run_task(continuation_prompt))
        with db_session() as session:
            task = session.get(AgentTask, task_id)
            if task is None:
                return
            approval_payload = _find_approval_payload(result)
            if approval_payload:
                approval = _create_approval(session, task, approval_payload)
                task.result = result
                task.status = "waiting_approval"
                task.updated_at = _now()
                task.plan = {**(task.plan or {}), "pending_approval_id": approval.id}
                return
            next_input_payload = _find_human_input_payload(result)
            if next_input_payload:
                task.result = result
                task.status = "needs_input"
                task.updated_at = _now()
                task.plan = {**(task.plan or {}), "pending_human_input": next_input_payload}
                return
            task.result = result
            task.status = "succeeded"
            task.finished_at = _now()
            task.updated_at = task.finished_at
            _update_conversation_memory(session, task)
    except Exception as exc:
        with db_session() as session:
            task = session.get(AgentTask, task_id)
            if task is None:
                return
            task.error_message = str(exc)
            task.status = "failed"
            task.finished_at = _now()
            task.updated_at = task.finished_at


def _create_approval(session, task: AgentTask, payload: dict[str, Any]) -> AgentApproval:
    existing = (
        session.query(AgentApproval)
        .filter(AgentApproval.task_id == task.id, AgentApproval.status == "pending")
        .one_or_none()
    )
    if existing is not None:
        return existing
    approval = AgentApproval(
        id=str(uuid.uuid4()),
        task_id=task.id,
        user_id=task.user_id,
        status="pending",
        action=str(payload.get("action") or payload.get("tool_name") or "unknown"),
        risk=str(payload.get("risk") or "High-risk ERP operation."),
        details=str(payload.get("details") or ""),
        tool_name=str(payload.get("tool_name") or payload.get("action") or ""),
        tool_args=payload.get("tool_args") or {},
        created_at=_now(),
    )
    session.add(approval)
    session.flush()
    return approval


def _latest_approval_for_task(task_id: str) -> dict[str, Any] | None:
    with db_session() as session:
        approval = (
            session.query(AgentApproval)
            .filter(AgentApproval.task_id == task_id)
            .order_by(AgentApproval.created_at.desc())
            .first()
        )
        return _serialize_approval(approval) if approval is not None else None


def _get_pending_approval(session, task_id: str, username: str) -> AgentApproval:
    user = session.query(User).filter(User.username == username, User.status == "active").one_or_none()
    if user is None:
        raise LookupError("User not found")
    approval = (
        session.query(AgentApproval)
        .filter(AgentApproval.task_id == task_id, AgentApproval.user_id == user.id, AgentApproval.status == "pending")
        .one_or_none()
    )
    if approval is None:
        raise LookupError("Pending approval not found")
    return approval


def _serialize_approval(approval: AgentApproval | dict[str, Any] | None) -> dict[str, Any] | None:
    if approval is None:
        return None
    if isinstance(approval, dict):
        return approval
    return {
        "id": approval.id,
        "task_id": approval.task_id,
        "status": approval.status,
        "action": approval.action,
        "risk": approval.risk,
        "details": approval.details,
        "tool_name": approval.tool_name,
        "tool_args": approval.tool_args,
        "decision_note": approval.decision_note,
        "execution_result": approval.execution_result,
        "created_at": approval.created_at.isoformat(),
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
    }


def _execute_approved_tool(tool_name: str, tool_args: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "erp_create_doc":
        return erp_client.create_doc(tool_args["doctype"], tool_args["doc"])
    if tool_name == "erp_update_doc":
        return erp_client.update_doc(tool_args["doctype"], tool_args["name"], tool_args["updates"])
    if tool_name == "update_item_price":
        matches = erp_client.list_docs(
            "Item Price",
            fields=["name", "item_code", "price_list", "price_list_rate", "currency"],
            filters={"item_code": tool_args["item_code"], "price_list": tool_args["price_list"]},
            limit=1,
            order_by="modified desc",
        )
        if not matches:
            raise ValueError("No Item Price found for approved price update.")
        return erp_client.update_doc("Item Price", matches[0]["name"], {"price_list_rate": tool_args["new_rate"]})
    if tool_name == "set_product_disabled":
        return erp_client.update_doc("Item", tool_args["item_code"], {"disabled": 1 if tool_args["disabled"] else 0})
    if tool_name == "create_campaign":
        return erp_client.create_doc(
            "Campaign",
            {"campaign_name": tool_args["campaign_name"], "description": tool_args["description"]},
        )
    raise ValueError(f"Unsupported approved tool: {tool_name}")


def _build_approval_continuation_prompt(prompt: str, approval: AgentApproval, execution_result: dict[str, Any]) -> str:
    return (
        "用户已经在 Web 界面批准了以下高风险 ERP 操作，并且系统已经执行完成。\n"
        "请不要再次调用同一个写入工具，只基于执行结果给用户最终答复。\n\n"
        f"原始任务：{prompt}\n"
        f"已批准工具：{approval.tool_name}\n"
        f"批准原因/备注：{approval.decision_note or '无'}\n"
        f"执行结果：{execution_result}\n"
    )


def _build_human_input_continuation_prompt(prompt: str, response: str, input_request: dict[str, Any] | None) -> str:
    return (
        "用户已经在 Web 界面补充了继续执行任务所需的信息。\n"
        "请结合这些补充信息继续完成原始任务；如果后续需要高风险 ERP 写操作，仍然必须走审批。\n\n"
        f"原始任务：{prompt}\n"
        f"Agent 刚才请求的信息：{input_request or {}}\n"
        f"用户补充：{response}\n"
    )


def _build_agent_prompt(task_id: str, prompt: str) -> str:
    with db_session() as session:
        current = session.get(AgentTask, task_id)
        if current is None or not current.conversation_id:
            return prompt
        conversation = current.conversation
        memory_rows = (
            session.query(AgentMemory)
            .filter(
                AgentMemory.user_id == current.user_id,
                (AgentMemory.conversation_id == current.conversation_id) | (AgentMemory.conversation_id.is_(None)),
            )
            .order_by(AgentMemory.updated_at.desc())
            .limit(8)
            .all()
        )
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
        if not previous_tasks and not conversation.summary and not memory_rows:
            return prompt
        rows = []
        for index, task in enumerate(reversed(previous_tasks), start=1):
            rows.append(
                f"{index}. 用户任务：{task.prompt}\n"
                f"   状态：{task.status}\n"
                f"   结果摘要：{_extract_result_summary(task.result, task.error_message)}"
            )
        memory_lines = [
            f"- [{memory.memory_type}] {memory.content[:500]}" for memory in memory_rows if memory.content.strip()
        ]
        sections = ["以下是同一会话内的长期记忆和近期上下文，请只把它作为业务背景，不要重复执行旧任务。"]
        if conversation.summary:
            sections.append("会话摘要：\n" + conversation.summary)
        if memory_lines:
            sections.append("可用长期记忆：\n" + "\n".join(memory_lines))
        if rows:
            sections.append("近期任务记录：\n" + "\n\n".join(rows))
    return (
        "\n\n".join(sections)
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


def _update_conversation_memory(session, task: AgentTask) -> None:
    if task.conversation is None:
        return
    summary = _extract_result_summary(task.result, task.error_message)
    if not summary or summary == "暂无结果":
        return
    task_memory = f"用户任务：{task.prompt}\n结果摘要：{summary[:1200]}"
    session.add(
        AgentMemory(
            id=str(uuid.uuid4()),
            user_id=task.user_id,
            conversation_id=task.conversation_id,
            source_task_id=task.id,
            memory_type="task_summary",
            content=task_memory[:1800],
            memory_metadata={"auto_generated": True},
            created_at=_now(),
            updated_at=_now(),
        )
    )
    task.conversation.summary = _merge_summary(task.conversation.summary, task.prompt, summary)
    task.conversation.updated_at = _now()


def _merge_summary(existing: str | None, prompt: str, result_summary: str, max_length: int = 2800) -> str:
    entry = f"- 用户问：{prompt[:220]}\n  结论：{result_summary[:700]}"
    if not existing:
        return entry
    merged = f"{existing.strip()}\n{entry}"
    if len(merged) <= max_length:
        return merged
    lines = [line for line in merged.splitlines() if line.strip()]
    kept: list[str] = []
    total = 0
    for line in reversed(lines):
        total += len(line) + 1
        if total > max_length:
            break
        kept.append(line)
    return "\n".join(reversed(kept))

from __future__ import annotations

import uuid
from typing import Any

from agent_console.backend.db import db_session
from agent_console.backend.db_models import AgentConversation, AgentMemory, User


def list_memories(username: str, conversation_id: str | None = None) -> list[dict[str, Any]]:
    with db_session() as session:
        user = _get_user(session, username)
        query = session.query(AgentMemory).filter(AgentMemory.user_id == user.id)
        if conversation_id:
            query = query.filter(AgentMemory.conversation_id == conversation_id)
        memories = query.order_by(AgentMemory.updated_at.desc()).all()
        return [_serialize_memory(memory) for memory in memories]


def create_memory(
    username: str,
    content: str,
    memory_type: str = "manual_note",
    conversation_id: str | None = None,
) -> dict[str, Any]:
    with db_session() as session:
        user = _get_user(session, username)
        _validate_conversation(session, user.id, conversation_id)
        memory = AgentMemory(
            id=str(uuid.uuid4()),
            user_id=user.id,
            conversation_id=conversation_id,
            memory_type=memory_type,
            content=content.strip(),
            memory_metadata={"auto_generated": False},
        )
        session.add(memory)
        session.flush()
        return _serialize_memory(memory)


def update_memory(username: str, memory_id: str, content: str, memory_type: str | None = None) -> dict[str, Any]:
    with db_session() as session:
        user = _get_user(session, username)
        memory = (
            session.query(AgentMemory)
            .filter(AgentMemory.id == memory_id, AgentMemory.user_id == user.id)
            .one_or_none()
        )
        if memory is None:
            raise LookupError("Memory not found")
        memory.content = content.strip()
        if memory_type:
            memory.memory_type = memory_type
        session.flush()
        return _serialize_memory(memory)


def delete_memory(username: str, memory_id: str) -> None:
    with db_session() as session:
        user = _get_user(session, username)
        memory = (
            session.query(AgentMemory)
            .filter(AgentMemory.id == memory_id, AgentMemory.user_id == user.id)
            .one_or_none()
        )
        if memory is None:
            raise LookupError("Memory not found")
        session.delete(memory)


def _get_user(session, username: str) -> User:
    user = session.query(User).filter(User.username == username, User.status == "active").one_or_none()
    if user is None:
        raise LookupError(f"User not found: {username}")
    return user


def _validate_conversation(session, user_id: int, conversation_id: str | None) -> None:
    if not conversation_id:
        return
    conversation = (
        session.query(AgentConversation)
        .filter(AgentConversation.id == conversation_id, AgentConversation.user_id == user_id)
        .one_or_none()
    )
    if conversation is None:
        raise LookupError("Conversation not found")


def _serialize_memory(memory: AgentMemory) -> dict[str, Any]:
    return {
        "id": memory.id,
        "conversation_id": memory.conversation_id,
        "source_task_id": memory.source_task_id,
        "memory_type": memory.memory_type,
        "content": memory.content,
        "metadata": memory.memory_metadata,
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.updated_at.isoformat(),
    }

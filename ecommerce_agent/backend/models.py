from __future__ import annotations

import hashlib
import os
import secrets
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ecommerce_agent.backend.db import Base


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)

    users: Mapped[list["User"]] = relationship(secondary=user_roles, back_populates="roles")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    roles: Mapped[list[Role]] = relationship(secondary=user_roles, back_populates="users")


class AgentConversation(Base):
    __tablename__ = "agent_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped[User] = relationship()
    tasks: Mapped[list["AgentTask"]] = relationship(back_populates="conversation")


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    input_context: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()
    conversation: Mapped[AgentConversation | None] = relationship(back_populates="tasks")

    __table_args__ = (
        UniqueConstraint("id", name="uq_agent_tasks_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("agent_tasks.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def hash_password(password: str, *, iterations: int = 120_000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_str, salt, digest_hex = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    iterations = int(iterations_str)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
    return secrets.compare_digest(digest, digest_hex)


def seed_default_users(session) -> None:
    defaults = [
        ("operator", os.getenv("AGENT_OPERATOR_PASSWORD", "operator123"), ["operator"]),
        ("manager", os.getenv("AGENT_MANAGER_PASSWORD", "manager123"), ["operator", "manager"]),
        ("admin", os.getenv("AGENT_ADMIN_PASSWORD", "admin123"), ["admin"]),
    ]

    role_map = {role.name: role for role in session.query(Role).all()}
    for role_name in {"operator", "manager", "admin"}:
        if role_name not in role_map:
            role = Role(name=role_name, description=f"{role_name} role")
            session.add(role)
            role_map[role_name] = role
    session.flush()

    for username, password, role_names in defaults:
        existing = session.query(User).filter(User.username == username).one_or_none()
        if existing is not None:
            continue
        session.add(
            User(
                username=username,
                password_hash=hash_password(password),
                display_name=username,
                status="active",
                roles=[role_map[role_name] for role_name in role_names],
            )
        )


def backfill_legacy_conversations(session) -> None:
    tasks = session.query(AgentTask).filter(AgentTask.conversation_id.is_(None)).all()
    for task in tasks:
        conversation_id = str(uuid.uuid4())
        conversation = AgentConversation(
            id=conversation_id,
            user_id=task.user_id,
            title=_summarize_title(task.prompt),
            created_at=task.created_at,
            updated_at=task.updated_at,
        )
        session.add(conversation)
        task.conversation_id = conversation_id


def _summarize_title(prompt: str, max_length: int = 24) -> str:
    normalized = " ".join(prompt.replace("\n", " ").split()).strip()
    for prefix in ("请帮我", "帮我", "分析", "查询", "生成一份", "生成"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :].strip()
    for marker in ("只分析", "不要修改", "。", "！", "？", "，", ",", "；", ";", "、"):
        if marker in normalized:
            normalized = normalized.split(marker, 1)[0].strip()
    return (normalized[:max_length] + "...") if len(normalized) > max_length else normalized or "新的运营会话"

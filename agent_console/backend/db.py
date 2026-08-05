from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://agent:agent123@localhost:5432/ecommerce_agent")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


@contextmanager
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_db() -> None:
    from agent_console.backend.db_models import backfill_legacy_conversations, seed_default_users

    Base.metadata.create_all(bind=engine)
    _ensure_legacy_schema()
    with db_session() as session:
        seed_default_users(session)
        backfill_legacy_conversations(session)


def _ensure_legacy_schema() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "agent_conversations" in table_names:
        conversation_columns = {column["name"] for column in inspector.get_columns("agent_conversations")}
        if "summary" not in conversation_columns:
            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE agent_conversations ADD COLUMN summary TEXT"))
    if "agent_tasks" not in table_names:
        return
    columns = {column["name"] for column in inspector.get_columns("agent_tasks")}
    if "conversation_id" in columns:
        return
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            connection.execute(text("ALTER TABLE agent_tasks ADD COLUMN IF NOT EXISTS conversation_id VARCHAR(36)"))
            connection.execute(text("CREATE INDEX IF NOT EXISTS ix_agent_tasks_conversation_id ON agent_tasks (conversation_id)"))
        else:
            connection.execute(text("ALTER TABLE agent_tasks ADD COLUMN conversation_id VARCHAR(36)"))

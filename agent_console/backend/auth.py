from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agent_console.backend.db import db_session
from agent_console.backend.db_models import User, verify_password


AUTH_SECRET = os.getenv("AGENT_AUTH_SECRET", "dev-agent-secret-change-me")
TOKEN_TTL_SECONDS = int(os.getenv("AGENT_TOKEN_TTL_SECONDS", "86400"))

security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    username: str
    roles: list[str]


def authenticate(username: str, password: str) -> CurrentUser | None:
    with db_session() as session:
        user = session.query(User).filter(User.username == username, User.status == "active").one_or_none()
        if user is None or not verify_password(password, user.password_hash):
            return None
        return CurrentUser(username=user.username, roles=[role.name for role in user.roles])


def create_token(user: CurrentUser) -> str:
    payload = {
        "sub": user.username,
        "roles": user.roles,
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    encoded_payload = _b64(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    signature = _sign(encoded_payload)
    return f"{encoded_payload}.{signature}"


def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)]) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        payload_part, signature = credentials.credentials.split(".", 1)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    if not hmac.compare_digest(_sign(payload_part), signature):
        raise HTTPException(status_code=401, detail="Invalid token signature")
    payload = json.loads(base64.urlsafe_b64decode(_pad(payload_part)).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=401, detail="Token expired")
    username = str(payload["sub"])
    with db_session() as session:
        user = session.query(User).filter(User.username == username, User.status == "active").one_or_none()
        if user is None:
            raise HTTPException(status_code=401, detail="User disabled or not found")
        return CurrentUser(username=user.username, roles=[role.name for role in user.roles])


def require_role(user: CurrentUser, role: str) -> None:
    if role not in user.roles and "admin" not in user.roles:
        raise HTTPException(status_code=403, detail=f"Missing role: {role}")


def _sign(payload: str) -> str:
    digest = hmac.new(AUTH_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64(digest)


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _pad(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode("ascii")

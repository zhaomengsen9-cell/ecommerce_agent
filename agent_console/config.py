from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer.") from exc
    if value < 1:
        raise ValueError(f"{name} must be a positive integer.")
    return value


_load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    frappe_base_url: str = os.getenv("FRAPPE_BASE_URL", "http://localhost:8080")
    frappe_site: str = os.getenv("FRAPPE_SITE", "frontend")
    frappe_api_key: str | None = os.getenv("FRAPPE_API_KEY") or None
    frappe_api_secret: str | None = os.getenv("FRAPPE_API_SECRET") or None
    frappe_username: str = os.getenv("FRAPPE_USERNAME", "Administrator")
    frappe_password: str = os.getenv("FRAPPE_PASSWORD", "admin")

    agent_model: str = os.getenv("AGENT_MODEL", "openai:gpt-4.1")
    human_approval_mode: str = os.getenv("HUMAN_APPROVAL_MODE", "web")
    erp_mcp_transport: str = os.getenv("ERP_MCP_TRANSPORT", "stdio")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    agent_queue_name: str = os.getenv("AGENT_QUEUE_NAME", "ecommerce-agent")
    agent_job_timeout: int = int(os.getenv("AGENT_JOB_TIMEOUT", "3600"))
    agent_max_tool_calls: int = _positive_int_env("AGENT_MAX_TOOL_CALLS", 30)


settings = Settings()

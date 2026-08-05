from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - helps smoke checks before dependency install.
    requests = None

from agent_console.config import settings


class ERPClientError(RuntimeError):
    pass


@dataclass
class ERPClient:
    """Thin Frappe/ERPNext HTTP client used by the MCP server."""

    base_url: str = settings.frappe_base_url
    site: str = settings.frappe_site
    api_key: str | None = settings.frappe_api_key
    api_secret: str | None = settings.frappe_api_secret
    username: str = settings.frappe_username
    password: str = settings.frappe_password

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        if requests is None:
            self.session = None
            return
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json", "X-Frappe-Site-Name": self.site})
        if self.api_key and self.api_secret:
            self.session.headers.update({"Authorization": f"token {self.api_key}:{self.api_secret}"})
        self._logged_in = False

    def login_if_needed(self) -> None:
        if self.session is None:
            raise ERPClientError("Missing dependency: install requests or run `pip install -e .` first.")
        if self.api_key and self.api_secret and not self._logged_in:
            return
        if self._logged_in:
            return
        self.login_with_password()

    def login_with_password(self) -> None:
        if self.session is None:
            raise ERPClientError("Missing dependency: install requests or run `pip install -e .` first.")
        self.session.headers.pop("Authorization", None)
        response = self.session.post(
            f"{self.base_url}/api/method/login",
            json={"usr": self.username, "pwd": self.password},
            timeout=30,
        )
        self._raise_for_status(response)
        self._logged_in = True

    def ping(self) -> dict[str, Any]:
        self.login_if_needed()
        response = self.session.get(f"{self.base_url}/api/method/frappe.auth.get_logged_user", timeout=10)
        if response.status_code == 401 and self.api_key and self.api_secret:
            self.login_with_password()
            response = self.session.get(f"{self.base_url}/api/method/frappe.auth.get_logged_user", timeout=10)
        return self._json_response(response)

    def list_docs(
        self,
        doctype: str,
        fields: list[str] | None = None,
        filters: dict[str, Any] | list[Any] | None = None,
        limit: int = 20,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        self.login_if_needed()
        params: dict[str, Any] = {"limit_page_length": limit}
        if fields:
            params["fields"] = self._json(fields)
        if filters:
            params["filters"] = self._json(filters)
        if order_by:
            params["order_by"] = order_by
        response = self.session.get(f"{self.base_url}/api/resource/{doctype}", params=params, timeout=30)
        if response.status_code == 401 and self.api_key and self.api_secret:
            self.login_with_password()
            response = self.session.get(f"{self.base_url}/api/resource/{doctype}", params=params, timeout=30)
        return self._json_response(response).get("data", [])

    def get_doc(self, doctype: str, name: str) -> dict[str, Any]:
        self.login_if_needed()
        response = self.session.get(f"{self.base_url}/api/resource/{doctype}/{name}", timeout=30)
        if response.status_code == 401 and self.api_key and self.api_secret:
            self.login_with_password()
            response = self.session.get(f"{self.base_url}/api/resource/{doctype}/{name}", timeout=30)
        return self._json_response(response).get("data", {})

    def create_doc(self, doctype: str, doc: dict[str, Any]) -> dict[str, Any]:
        self.login_if_needed()
        response = self.session.post(f"{self.base_url}/api/resource/{doctype}", json=doc, timeout=30)
        if response.status_code == 401 and self.api_key and self.api_secret:
            self.login_with_password()
            response = self.session.post(f"{self.base_url}/api/resource/{doctype}", json=doc, timeout=30)
        return self._json_response(response).get("data", {})

    def update_doc(self, doctype: str, name: str, updates: dict[str, Any]) -> dict[str, Any]:
        self.login_if_needed()
        response = self.session.put(f"{self.base_url}/api/resource/{doctype}/{name}", json=updates, timeout=30)
        if response.status_code == 401 and self.api_key and self.api_secret:
            self.login_with_password()
            response = self.session.put(f"{self.base_url}/api/resource/{doctype}/{name}", json=updates, timeout=30)
        return self._json_response(response).get("data", {})

    def call_method(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.login_if_needed()
        response = self.session.post(f"{self.base_url}/api/method/{method}", json=payload or {}, timeout=30)
        if response.status_code == 401 and self.api_key and self.api_secret:
            self.login_with_password()
            response = self.session.post(f"{self.base_url}/api/method/{method}", json=payload or {}, timeout=30)
        return self._json_response(response)

    @staticmethod
    def _json(value: Any) -> str:
        import json

        return json.dumps(value, ensure_ascii=False)

    def _json_response(self, response: Any) -> dict[str, Any]:
        self._raise_for_status(response)
        try:
            return response.json()
        except ValueError as exc:
            raise ERPClientError(f"ERP returned non-JSON response: {response.text[:300]}") from exc

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        if response.ok:
            return
        raise ERPClientError(f"ERP API error {response.status_code}: {response.text[:500]}")


erp_client = ERPClient()

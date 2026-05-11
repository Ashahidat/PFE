from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests
from requests import exceptions as requests_exceptions

from grafana.settings import GrafanaSettings

logger = logging.getLogger("grafana")


@dataclass(frozen=True)
class GrafanaAuth:
    bearer_token: str | None = None
    basic_user: str | None = None
    basic_password: str | None = None


class GrafanaClient:
    def __init__(self, settings: GrafanaSettings, *, extra_headers: dict[str, str] | None = None):
        self.settings = settings
        self.base_url = settings.url
        self.auth = GrafanaAuth(
            bearer_token=settings.service_token,
            basic_user=settings.admin_user,
            basic_password=settings.admin_password,
        )
        self.extra_headers = dict(extra_headers or {})

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.auth.bearer_token:
            headers["Authorization"] = f"Bearer {self.auth.bearer_token}"
        if self.extra_headers:
            headers.update(self.extra_headers)
        return headers

    def _request(self, method: str, path: str, *, json: Any | None = None, allow_404: bool = False):
        url = f"{self.base_url}{path}"
        auth = None
        if not self.auth.bearer_token and self.auth.basic_user and self.auth.basic_password:
            auth = (self.auth.basic_user, self.auth.basic_password)

        try:
            resp = requests.request(method, url, headers=self._headers(), json=json, auth=auth, timeout=15)
        except requests_exceptions.RequestException as e:
            hint = ""
            if "localhost" in (self.base_url or "") or "127.0.0.1" in (self.base_url or ""):
                hint = (
                    " (hint: if Grafana runs on your host but this backend runs in Docker, "
                    "http://localhost:3000 points to the container itself; use the Docker service name "
                    "or host.docker.internal instead)"
                )
            raise RuntimeError(f"Grafana API request failed {method} {url}: {e}{hint}") from e
        if allow_404 and resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise RuntimeError(f"Grafana API error {resp.status_code} {method} {path}: {resp.text[:500]}")
        if resp.text:
            return resp.json()
        return None

    # -------------------------
    # Folders
    # -------------------------
    def get_folder_by_uid(self, uid: str) -> dict[str, Any] | None:
        return self._request("GET", f"/api/folders/uid/{uid}", allow_404=True)

    def create_folder(self, title: str, uid: str) -> dict[str, Any]:
        return self._request("POST", "/api/folders", json={"title": title, "uid": uid})

    def ensure_folder(self, *, title: str, uid: str) -> dict[str, Any]:
        folder = self.get_folder_by_uid(uid)
        if folder:
            return folder
        logger.info("📁 [Grafana] create folder uid=%s title=%s", uid, title)
        return self.create_folder(title=title, uid=uid)

    def set_folder_permissions(self, folder_uid: str, items: list[dict[str, Any]]) -> None:
        """
        items: list of permissions with keys:
        - teamId + permission (1=view, 2=edit, 4=admin)
        - userId + permission
        - role ("Viewer"/"Editor"/"Admin") + permission
        """
        self._request("POST", f"/api/folders/{folder_uid}/permissions", json={"items": items})

    # -------------------------
    # Dashboards
    # -------------------------
    def upsert_dashboard(self, dashboard: dict[str, Any], *, folder_id: int, overwrite: bool = True) -> dict[str, Any]:
        payload = {"dashboard": dashboard, "folderId": folder_id, "overwrite": overwrite}
        return self._request("POST", "/api/dashboards/db", json=payload)

    # -------------------------
    # Teams / Users (optional but useful for RBAC)
    # -------------------------
    def find_team_by_name(self, name: str) -> dict[str, Any] | None:
        data = self._request("GET", f"/api/teams/search?name={requests.utils.quote(name)}")
        teams = (data or {}).get("teams") or []
        for team in teams:
            if (team.get("name") or "").strip().lower() == name.strip().lower():
                return team
        return None

    def create_team(self, name: str) -> dict[str, Any]:
        data = self._request("POST", "/api/teams", json={"name": name}) or {}
        # Grafana commonly returns {"teamId": <int>, "message": "..."} for this endpoint.
        if isinstance(data, dict) and data.get("id") is None and data.get("teamId") is not None:
            data = {**data, "id": data.get("teamId"), "name": name}
        return data

    def ensure_team(self, name: str) -> dict[str, Any]:
        existing = self.find_team_by_name(name)
        if existing:
            return existing
        logger.info("👥 [Grafana] create team name=%s", name)
        created = self.create_team(name)
        # Best-effort: return a full team object (with "id") if Grafana didn't.
        if (created or {}).get("id") is None:
            looked_up = self.find_team_by_name(name)
            if looked_up:
                return looked_up
        return created

    def lookup_user(self, login_or_email: str) -> dict[str, Any] | None:
        return self._request(
            "GET",
            f"/api/users/lookup?loginOrEmail={requests.utils.quote(login_or_email)}",
            allow_404=True,
        )

    def admin_create_user(self, *, login: str, name: str, email: str, password: str) -> dict[str, Any]:
        """
        Requires Grafana server-admin basic auth.
        """
        return self._request(
            "POST",
            "/api/admin/users",
            json={"name": name, "email": email, "login": login, "password": password},
        )

    def ensure_user_exists(self, *, login: str, name: str) -> dict[str, Any] | None:
        """
        Best-effort. If admin creds are not configured, we skip user creation.
        """
        user = self.lookup_user(login)
        if user:
            return user
        if not (self.settings.admin_user and self.settings.admin_password):
            logger.warning("⚠️ [Grafana] user %s not found and no admin creds configured; skipping create", login)
            return None
        email = f"{login}@local"
        password = f"pfe-{login}-proxy"
        logger.info("👤 [Grafana] create user login=%s (auth-proxy will own login)", login)
        self.admin_create_user(login=login, name=name, email=email, password=password)
        return self.lookup_user(login)

    def add_user_to_team(self, *, team_id: int, user_id: int) -> None:
        self._request("POST", f"/api/teams/{team_id}/members", json={"userId": user_id})

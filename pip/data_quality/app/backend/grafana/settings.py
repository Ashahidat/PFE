from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for _ in range(15):
        if (current / "AGENTS.md").exists() or (current / ".git").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return start.resolve()


@dataclass(frozen=True)
class GrafanaSettings:
    url: str
    service_token: str | None
    admin_user: str | None
    admin_password: str | None
    org_id: int
    templates_dir: Path
    enabled: bool


def get_grafana_settings() -> GrafanaSettings:
    """
    Minimal configuration. Keep it environment-driven so deployments stay simple.

    - `GRAFANA_URL`: base URL (default: http://127.0.0.1:3300)
    - `GRAFANA_SERVICE_TOKEN`: optional Bearer token (recommended for normal org APIs)
    - `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`: optional basic auth for admin endpoints
    - `GRAFANA_ORG_ID`: default 1
    - `GRAFANA_DASHBOARD_TEMPLATES_DIR`: default grafana/dashboard_templates (repo-root relative)
    - `GRAFANA_PROVISIONING_ENABLED`: default true
    """

    repo_root = _find_repo_root(Path(__file__).resolve())
    templates_dir = os.getenv("GRAFANA_DASHBOARD_TEMPLATES_DIR", "grafana/dashboard_templates")
    templates_path = (repo_root / templates_dir).resolve()

    enabled = os.getenv("GRAFANA_PROVISIONING_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}

    return GrafanaSettings(
        url=os.getenv("GRAFANA_URL", "http://127.0.0.1:3300").rstrip("/"),
        service_token=os.getenv("GRAFANA_SERVICE_TOKEN"),
        admin_user=os.getenv("GRAFANA_ADMIN_USER", "admin"),
        admin_password=os.getenv("GRAFANA_ADMIN_PASSWORD", "admin"),
        org_id=int(os.getenv("GRAFANA_ORG_ID", "1")),
        templates_dir=templates_path,
        enabled=enabled,
    )

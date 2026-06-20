from __future__ import annotations

import re


def _slug(value: str) -> str:
    v = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip()).strip("-").lower()
    return v or "project"


def folder_uid_for_project(project_id: str) -> str:
    compact = (project_id or "").replace("-", "")
    return f"pfe-project-{compact[:24]}"


def dashboard_uid_for_project(code: str, project_id: str) -> str:
    compact = (project_id or "").replace("-", "")
    return f"pfe-{code}-{compact[:20]}"


def build_project_grafana_links(
    *, project_id: str, project_name: str, base_path: str = "/api/grafana", org_id: int | None = None
) -> dict:
    """
    Build URLs that must be opened through the app reverse-proxy (base_path),
    not directly on the Grafana port.
    """
    base = (base_path or "/api/grafana").rstrip("/")
    folder_uid = folder_uid_for_project(project_id)
    folder_slug = _slug(f"pfe-{project_name}")
    folder_url = f"{base}/dashboards/f/{folder_uid}/{folder_slug}"
    if org_id is not None:
        folder_url = f"{folder_url}/?orgId={int(org_id)}"

    dashboards: dict[str, dict[str, str]] = {}
    for code in ("quality", "pipeline", "lineage", "governance"):
        uid = dashboard_uid_for_project(code, project_id)
        dash_slug = _slug(f"pfe-{project_name}-{code}")
        url = f"{base}/d/{uid}/{dash_slug}"
        if org_id is not None:
            url = f"{url}?orgId={int(org_id)}"
        dashboards[code] = {"uid": uid, "url": url}

    return {
        "folder": {"uid": folder_uid, "url": folder_url},
        "dashboards": dashboards,
    }

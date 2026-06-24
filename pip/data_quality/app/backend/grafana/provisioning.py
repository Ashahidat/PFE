from __future__ import annotations

import logging
import re
from typing import Any

from core.roles import ADMINISTRATORS, AUDIT, DATA_OWNER
from grafana.client import GrafanaClient
from grafana.settings import GrafanaSettings
from grafana.templates import instantiate_template, load_dashboard_templates

logger = logging.getLogger("grafana-provisioning")


def _maybe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _team_id(team: dict[str, Any] | None) -> int | None:
    """
    Grafana team objects typically contain "id".
    The create team endpoint often returns "teamId" instead.
    """
    if not team:
        return None
    return _maybe_int(team.get("id") if team.get("id") is not None else team.get("teamId"))


def _slug(value: str) -> str:
    v = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip()).strip("-").lower()
    return v or "project"


def _folder_uid(project_id: str) -> str:
    compact = project_id.replace("-", "")
    return f"pfe-project-{compact[:24]}"


def _dashboard_uid(code: str, project_id: str) -> str:
    compact = project_id.replace("-", "")
    return f"pfe-{code}-{compact[:20]}"


def _team_name_for_department(dept_code: str) -> str:
    normalized = (dept_code or "UNKNOWN").strip().upper()
    normalized = re.sub(r"\s+", "_", normalized)
    return f"dept_{normalized}"


def _team_name_for_role(role_code: str) -> str:
    return f"role_{role_code}".lower()


def _permission_items(*, visibility: str, dept_team_id: int | None, audit_team_id: int | None, admin_team_id: int | None):
    items: list[dict[str, Any]] = []

    # Always allow org-wide viewer access for PUBLIC projects.
    if (visibility or "").upper() == "PUBLIC":
        items.append({"role": "Viewer", "permission": 1})
    else:
        if dept_team_id is not None:
            items.append({"teamId": dept_team_id, "permission": 1})

    # Always allow audit/admin consolidated viewing.
    if audit_team_id is not None:
        items.append({"teamId": audit_team_id, "permission": 1})
    if admin_team_id is not None:
        items.append({"teamId": admin_team_id, "permission": 1})

    return items


def provision_project_dashboards(
    settings: GrafanaSettings,
    *,
    project_id: str,
    project_name: str,
    project_visibility: str,
    owner_department: str,
    identity_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Creates/updates:
    - folder per project
    - folder permissions (Viewer for PUBLIC, dept team for DEPARTMENT, plus audit/admin teams)
    - 4 dashboards (quality/pipeline/lineage/governance) cloned from repo templates
    """
    if not settings.enabled:
        logger.info("⏭️ [Grafana] provisioning disabled by env")
        return {"enabled": False}

    auth_mode = "none"
    if settings.service_token:
        auth_mode = "bearer"
    elif settings.admin_user and settings.admin_password:
        auth_mode = "basic"
    elif identity_headers:
        auth_mode = "auth-proxy"
    logger.info(
        "🚀 [Grafana] provisioning start project_id=%s folder=%s url=%s auth=%s templates_dir=%s",
        project_id,
        f"PFE - {project_name}",
        settings.url,
        auth_mode,
        str(settings.templates_dir),
    )
    if auth_mode == "none":
        logger.warning("⏭️ [Grafana] provisioning skipped: no Grafana credentials configured")
        return {"enabled": True, "skipped": True, "reason": "no-auth"}

    client = GrafanaClient(settings, extra_headers=identity_headers)
    client.ensure_postgres_datasource()
    templates = load_dashboard_templates(settings)

    folder_title = f"PFE - {project_name}"
    folder_uid = _folder_uid(project_id)
    folder = client.ensure_folder(title=folder_title, uid=folder_uid)
    folder_id = int(folder.get("id"))

    dept_team = client.ensure_team(_team_name_for_department(owner_department))
    audit_team = client.ensure_team(_team_name_for_role("audit"))
    admin_team = client.ensure_team(_team_name_for_role("admin"))

    dept_team_id = _team_id(dept_team)
    audit_team_id = _team_id(audit_team)
    admin_team_id = _team_id(admin_team)
    if (project_visibility or "").upper() != "PUBLIC" and dept_team_id is None:
        logger.warning("⚠️ [Grafana] department team id missing; name=%s raw=%s", _team_name_for_department(owner_department), dept_team)

    items = _permission_items(
        visibility=project_visibility,
        dept_team_id=dept_team_id,
        audit_team_id=audit_team_id,
        admin_team_id=admin_team_id,
    )
    client.set_folder_permissions(folder_uid, items)

    results: dict[str, Any] = {"folder": {"uid": folder_uid, "id": folder_id}, "dashboards": {}}
    for code, template in templates.items():
        uid = _dashboard_uid(code, project_id)
        dashboard = instantiate_template(template, project_id=project_id, project_name=project_name, uid=uid)
        dashboard["title"] = f"PFE - {project_name} - {code.capitalize()}"
        try:
            res = client.upsert_dashboard(dashboard, folder_id=folder_id, overwrite=True)
            results["dashboards"][code] = res
        except Exception as e:
            # Keep provisioning resilient: one broken template/dashboard should not prevent the
            # others from being created. Log the error and keep going.
            logger.exception("⚠️ [Grafana] dashboard upsert failed code=%s uid=%s: %s", code, uid, e)
            results["dashboards"][code] = {"uid": uid, "error": str(e)}

    return results


def sync_user_to_grafana(settings: GrafanaSettings, *, employee_id: str, username: str, department: str, role: str) -> None:
    """
    Best-effort:
    - ensure Grafana user exists (requires admin creds)
    - add user to department team (all users) so DEPARTMENT folders work
    - add user to role teams (AUDIT / ADMIN*) for consolidated access
    """
    if not settings.enabled:
        return

    client = GrafanaClient(settings)
    user = client.ensure_user_exists(login=employee_id, name=username)
    if not user:
        return

    user_id = int(user.get("id"))

    # Always map a user to their department team so folder permissions based on department apply
    # to all members of the department (not only DATA_OWNER).
    dept_value = (department or "").strip()
    if dept_value:
        team = client.ensure_team(_team_name_for_department(dept_value))
        team_id = _team_id(team)
        if team_id is not None:
            client.add_user_to_team(team_id=team_id, user_id=user_id)

    role_value = (role or "").upper()
    if role_value == AUDIT:
        team = client.ensure_team(_team_name_for_role("audit"))
        team_id = _team_id(team)
        if team_id is not None:
            client.add_user_to_team(team_id=team_id, user_id=user_id)

    if role_value in ADMINISTRATORS:
        team = client.ensure_team(_team_name_for_role("admin"))
        team_id = _team_id(team)
        if team_id is not None:
            client.add_user_to_team(team_id=team_id, user_id=user_id)

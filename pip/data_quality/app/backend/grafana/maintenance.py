from __future__ import annotations

import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from db.projects import Project
from db.users import User
from grafana.client import GrafanaClient
from grafana.provisioning import provision_project_dashboards
from grafana.settings import GrafanaSettings

logger = logging.getLogger("grafana-maintenance")

_GENERATED_TITLE_PREFIX = "PFE - "
_PROJECT_TAG_PREFIX = "project:"
_PROJECT_FOLDER_UID_RE = re.compile(r"^pfe-project-([a-z0-9]+)$")
_PROJECT_DASHBOARD_UID_RE = re.compile(r"^pfe-(?:quality|pipeline|lineage|governance)-([a-z0-9]+)$")


def _compact_project_id(project_id: str) -> str:
    return (project_id or "").replace("-", "").strip().lower()


def _folder_prefix_from_uid(uid: str | None) -> str | None:
    if not uid:
        return None
    match = _PROJECT_FOLDER_UID_RE.fullmatch(uid.strip().lower())
    if not match:
        return None
    return match.group(1)


def _dashboard_prefix_from_uid(uid: str | None) -> str | None:
    if not uid:
        return None
    match = _PROJECT_DASHBOARD_UID_RE.fullmatch(uid.strip().lower())
    if not match:
        return None
    return match.group(1)


def _matches_any_project(prefix: str | None, current_project_ids: set[str]) -> bool:
    if not prefix:
        return False
    return any(project_id.startswith(prefix) for project_id in current_project_ids)


def _item_title(item: dict[str, Any]) -> str:
    return str(item.get("title") or "").strip()


def _item_tags(item: dict[str, Any]) -> set[str]:
    raw_tags = item.get("tags") or []
    return {str(tag).strip().lower() for tag in raw_tags if str(tag).strip()}


def _item_project_tags(item: dict[str, Any]) -> set[str]:
    project_tags: set[str] = set()
    for tag in _item_tags(item):
        if not tag.startswith(_PROJECT_TAG_PREFIX):
            continue
        project_id = tag[len(_PROJECT_TAG_PREFIX) :].replace("-", "").strip().lower()
        if project_id:
            project_tags.add(project_id)
    return project_tags


def _is_generated_grafana_item(item: dict[str, Any]) -> bool:
    uid = str(item.get("uid") or "").strip().lower()
    title = _item_title(item).lower()
    tags = _item_tags(item)

    return bool(
        title.startswith(_GENERATED_TITLE_PREFIX.lower())
        or any(tag.startswith(_PROJECT_TAG_PREFIX) for tag in tags)
        or _folder_prefix_from_uid(uid)
        or _dashboard_prefix_from_uid(uid)
    )


def _generated_item_matches_projects(item: dict[str, Any], current_project_ids: set[str]) -> bool:
    if not current_project_ids:
        return False

    uid = str(item.get("uid") or "").strip().lower()
    folder_prefix = _folder_prefix_from_uid(uid)
    dashboard_prefix = _dashboard_prefix_from_uid(uid)
    if folder_prefix and _matches_any_project(folder_prefix, current_project_ids):
        return True
    if dashboard_prefix and _matches_any_project(dashboard_prefix, current_project_ids):
        return True

    return bool(_item_project_tags(item) & current_project_ids)


def _project_visibility_value(project: Any) -> str:
    return str(getattr(project, "visibility", "") or "DEPARTMENT")


def _project_department_value(db: Session, project: Any, fallback: str = "UNKNOWN") -> str:
    owner_employee_id = str(getattr(project, "owner_employee_id", "") or "")
    if owner_employee_id:
        owner = db.query(User).filter(User.employee_id == owner_employee_id).first()
        if owner and owner.department:
            return str(owner.department)
    return fallback


def _delete_dashboard_artifacts(client: GrafanaClient, dashboard_uid: str) -> None:
    try:
        client.delete_dashboard_by_uid(dashboard_uid)
        logger.info("🧹 [Grafana] deleted dashboard uid=%s", dashboard_uid)
    except Exception:
        logger.exception("⚠️ [Grafana] failed to delete dashboard uid=%s", dashboard_uid)


def _delete_folder_artifacts(client: GrafanaClient, folder_uid: str) -> None:
    try:
        client.delete_folder_by_uid(folder_uid)
        logger.info("🧹 [Grafana] deleted folder uid=%s", folder_uid)
    except Exception:
        logger.exception("⚠️ [Grafana] failed to delete folder uid=%s", folder_uid)


def _purge_all_grafana_content(client: GrafanaClient) -> dict[str, int]:
    """
    Remove every dashboard and folder from Grafana before reprovisioning.

    The instance is dedicated to this app, so we prefer a deterministic
    current-state mirror over preserving old Grafana content.
    """
    dashboards_deleted = 0
    folders_deleted = 0

    for item in client.search(type="dash-db"):
        uid = str(item.get("uid") or "")
        if not uid:
            continue
        _delete_dashboard_artifacts(client, uid)
        dashboards_deleted += 1

    for item in client.search(type="dash-folder"):
        uid = str(item.get("uid") or "")
        if not uid:
            continue
        _delete_folder_artifacts(client, uid)
        folders_deleted += 1

    return {"dashboards_deleted": dashboards_deleted, "folders_deleted": folders_deleted}


def cleanup_project_artifacts(settings: GrafanaSettings, *, project_id: str) -> dict[str, int]:
    """
    Remove Grafana folders/dashboards for one project.
    Useful when a project is deleted from PostgreSQL.
    """
    if not settings.enabled:
        return {"dashboards_deleted": 0, "folders_deleted": 0}

    client = GrafanaClient(settings)
    compact = _compact_project_id(project_id)
    if not compact:
        return {"dashboards_deleted": 0, "folders_deleted": 0}

    dashboards_deleted = 0
    folders_deleted = 0

    for item in client.search(type="dash-db"):
        uid = str(item.get("uid") or "")
        if not _is_generated_grafana_item(item):
            continue
        if _generated_item_matches_projects(item, {compact}):
            continue
        _delete_dashboard_artifacts(client, uid)
        dashboards_deleted += 1

    for item in client.search(type="dash-folder"):
        uid = str(item.get("uid") or "")
        if not _is_generated_grafana_item(item):
            continue
        if _generated_item_matches_projects(item, {compact}):
            continue
        _delete_folder_artifacts(client, uid)
        folders_deleted += 1

    return {"dashboards_deleted": dashboards_deleted, "folders_deleted": folders_deleted}


def sync_projects_from_db(settings: GrafanaSettings, db: Session) -> dict[str, Any]:
    """
    Bring Grafana back in sync with the current PostgreSQL projects table.

    - refresh the Postgres datasource
    - provision dashboards/folders for current projects
    - delete stale project folders/dashboards that no longer exist in DB
    """
    if not settings.enabled:
        return {"enabled": False, "skipped": True, "reason": "provisioning-disabled"}

    sync_identity_headers = {
        "X-WEBAUTH-USER": "grafana-sync",
        "X-WEBAUTH-NAME": "Grafana Sync",
        "X-WEBAUTH-ROLE": "Admin",
    }

    client = GrafanaClient(settings, extra_headers=sync_identity_headers)
    purge = _purge_all_grafana_content(client)
    datasource = client.ensure_postgres_datasource()
    projects = db.query(Project).order_by(Project.created_at.asc()).all()

    current_project_ids: set[str] = set()
    provisioned: list[dict[str, Any]] = []

    for project in projects:
        project_id = str(project.id)
        current_project_ids.add(_compact_project_id(project_id))
        try:
            result = provision_project_dashboards(
                settings,
                project_id=project_id,
                project_name=project.name,
                project_visibility=_project_visibility_value(project),
                owner_department=_project_department_value(db, project),
                identity_headers=sync_identity_headers,
            )
            provisioned.append(
                {
                    "project_id": project_id,
                    "project_name": project.name,
                    "folder_uid": (result.get("folder") or {}).get("uid"),
                    "result": result,
                }
            )
        except Exception as exc:
            logger.exception("⚠️ [Grafana] provisioning failed for project %s: %s", project_id, exc)
            provisioned.append(
                {
                    "project_id": project_id,
                    "project_name": project.name,
                    "error": str(exc),
                }
            )

    dashboards_deleted = 0
    folders_deleted = 0

    for item in client.search(type="dash-db"):
        uid = str(item.get("uid") or "")
        if not _is_generated_grafana_item(item):
            continue
        if _generated_item_matches_projects(item, current_project_ids):
            continue
        _delete_dashboard_artifacts(client, uid)
        dashboards_deleted += 1

    for item in client.search(type="dash-folder"):
        uid = str(item.get("uid") or "")
        if not _is_generated_grafana_item(item):
            continue
        if _generated_item_matches_projects(item, current_project_ids):
            continue
        _delete_folder_artifacts(client, uid)
        folders_deleted += 1

    return {
        "enabled": True,
        "purge": purge,
        "datasource": datasource,
        "projects": provisioned,
        "cleanup": {
            "dashboards_deleted": dashboards_deleted,
            "folders_deleted": folders_deleted,
        },
    }

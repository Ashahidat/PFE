from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from grafana.settings import GrafanaSettings


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_dashboard_templates(settings: GrafanaSettings) -> dict[str, dict[str, Any]]:
    """
    Returns templates keyed by a stable short code: quality/pipeline/lineage/governance.
    """
    base = settings.templates_dir
    mapping = {
        "quality": base / "pfe-template-quality.json",
        "pipeline": base / "pfe-template-pipeline.json",
        "lineage": base / "pfe-template-lineage.json",
        "governance": base / "pfe-template-governance.json",
    }
    templates: dict[str, dict[str, Any]] = {}
    for key, path in mapping.items():
        templates[key] = _load_json(path)
    return templates


def instantiate_template(template: dict[str, Any], *, project_id: str, project_name: str, uid: str) -> dict[str, Any]:
    """
    Clone a template and replace placeholders.
    """
    raw = json.dumps(template, ensure_ascii=False)
    raw = raw.replace("__PROJECT_ID__", project_id)
    raw = raw.replace("__PROJECT_NAME__", project_name)
    dashboard = json.loads(raw)

    dashboard["id"] = None
    dashboard["uid"] = uid
    dashboard["editable"] = False
    dashboard["version"] = 1

    # Keep tags, add a stable project tag.
    tags = dashboard.get("tags") or []
    if f"project:{project_id}" not in tags:
        tags.append(f"project:{project_id}")
    dashboard["tags"] = tags

    return dashboard


from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "pip" / "data_quality" / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from grafana.maintenance import (
    _generated_item_matches_projects,
    _is_generated_grafana_item,
    _purge_all_grafana_content,
)
from grafana.client import GrafanaClient
from grafana.settings import GrafanaSettings


class GrafanaMaintenanceTests(unittest.TestCase):
    def test_generated_dashboard_with_legacy_title_is_recognized(self) -> None:
        item = {"uid": "legacy-123", "title": "PFE - Old Project - Quality"}

        self.assertTrue(_is_generated_grafana_item(item))
        self.assertFalse(_generated_item_matches_projects(item, {"abc"}))

    def test_generated_dashboard_with_project_tag_matches_current_project(self) -> None:
        item = {
            "uid": "custom-uid",
            "title": "Something else",
            "tags": ["project:3d962fd2f26047dc861a23b887f4c7d8"],
        }

        self.assertTrue(_is_generated_grafana_item(item))
        self.assertTrue(_generated_item_matches_projects(item, {"3d962fd2f26047dc861a23b887f4c7d8"}))

    def test_non_generated_item_is_ignored(self) -> None:
        item = {"uid": "community-dashboard", "title": "Operations Overview", "tags": ["shared"]}

        self.assertFalse(_is_generated_grafana_item(item))
        self.assertFalse(_generated_item_matches_projects(item, {"abc"}))

    def test_full_purge_removes_all_dashboards_and_folders(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.deleted_dashboards: list[str] = []
                self.deleted_folders: list[str] = []

            def search(self, *, type: str | None = None):  # noqa: A003
                if type == "dash-db":
                    return [
                        {"uid": "legacy-one"},
                        {"uid": "legacy-two"},
                    ]
                if type == "dash-folder":
                    return [
                        {"uid": "folder-one"},
                    ]
                return []

            def delete_dashboard_by_uid(self, uid: str) -> None:
                self.deleted_dashboards.append(uid)

            def delete_folder_by_uid(self, uid: str) -> None:
                self.deleted_folders.append(uid)

        client = FakeClient()
        result = _purge_all_grafana_content(client)

        self.assertEqual(result, {"dashboards_deleted": 2, "folders_deleted": 1})
        self.assertEqual(client.deleted_dashboards, ["legacy-one", "legacy-two"])
        self.assertEqual(client.deleted_folders, ["folder-one"])

    def test_auth_proxy_headers_keep_basic_auth_when_admin_credentials_exist(self) -> None:
        settings = GrafanaSettings(
            url="http://localhost:3000",
            service_token=None,
            admin_user="admin",
            admin_password="admin",
            org_id=1,
            templates_dir=Path("/tmp"),
            enabled=True,
        )

        client = GrafanaClient(
            settings,
            extra_headers={
                "X-WEBAUTH-USER": "grafana-sync",
                "X-WEBAUTH-NAME": "Grafana Sync",
                "X-WEBAUTH-ROLE": "Admin",
            },
        )

        self.assertEqual(client.auth.basic_user, "admin")
        self.assertEqual(client.auth.basic_password, "admin")

    def test_auth_proxy_headers_disable_basic_auth_without_admin_credentials(self) -> None:
        settings = GrafanaSettings(
            url="http://localhost:3000",
            service_token=None,
            admin_user=None,
            admin_password=None,
            org_id=1,
            templates_dir=Path("/tmp"),
            enabled=True,
        )

        client = GrafanaClient(
            settings,
            extra_headers={
                "X-WEBAUTH-USER": "grafana-sync",
                "X-WEBAUTH-NAME": "Grafana Sync",
                "X-WEBAUTH-ROLE": "Admin",
            },
        )

        self.assertIsNone(client.auth.basic_user)
        self.assertIsNone(client.auth.basic_password)


if __name__ == "__main__":
    unittest.main()

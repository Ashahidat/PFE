from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "pip" / "data_quality" / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from core.roles import DATA_OWNER, AUDIT
from routes.projects import _grafana_identity_headers


class ProjectsGrafanaHeadersTests(unittest.TestCase):
    def test_project_creator_gets_auth_proxy_headers(self) -> None:
        user = {
            "role": DATA_OWNER,
            "employee_id": "E123",
            "username": "alice",
            "sub": "alice-sub",
        }

        headers = _grafana_identity_headers(user, for_project_creator=True)

        self.assertEqual(
            headers,
            {
                "X-WEBAUTH-USER": "E123",
                "X-WEBAUTH-NAME": "alice",
                "X-WEBAUTH-ROLE": "Admin",
            },
        )

    def test_non_project_creator_is_not_allowed(self) -> None:
        user = {
            "role": AUDIT,
            "employee_id": "E999",
            "username": "auditor",
        }

        headers = _grafana_identity_headers(user, for_project_creator=True)

        self.assertIsNone(headers)


if __name__ == "__main__":
    unittest.main()

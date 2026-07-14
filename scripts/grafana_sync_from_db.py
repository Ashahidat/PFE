#!/usr/bin/env python3
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _backend_path() -> Path:
    return _repo_root() / "pip" / "data_quality" / "app" / "backend"


def _wait_for_grafana(url: str, *, attempts: int = 30, delay: float = 1.0) -> None:
    import requests

    health_url = f"{url.rstrip('/')}/api/health"
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            resp = requests.get(health_url, timeout=3)
            if resp.ok:
                return
            last_error = RuntimeError(f"Grafana health check failed: {resp.status_code} {resp.text[:120]}")
        except Exception as exc:
            last_error = exc
        time.sleep(delay)
    if last_error:
        raise RuntimeError(f"Grafana is not reachable at {health_url}: {last_error}") from last_error


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    root = _repo_root()
    backend = _backend_path()
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from db.connexion_db import SessionLocal  # noqa: WPS433
    from grafana.maintenance import sync_projects_from_db  # noqa: WPS433
    from grafana.settings import get_grafana_settings  # noqa: WPS433

    settings = get_grafana_settings()
    _wait_for_grafana(settings.url)

    db = SessionLocal()
    try:
        result = sync_projects_from_db(settings, db)
    finally:
        db.close()

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

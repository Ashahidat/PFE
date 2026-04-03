"""
DAG Airflow minimal pour déclencher le push Atlas de manière asynchrone.
"""

from airflow import DAG
from airflow.decorators import task
from datetime import datetime, timedelta
from typing import Dict, Any
import os
import sys
from pathlib import Path

# Configuration des chemins (alignée sur les autres DAGs)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
paths_to_add = [
    str(PROJECT_ROOT),
    str(PROJECT_ROOT / "app/backend"),
    str(PROJECT_ROOT / "orchestration"),
    str(PROJECT_ROOT / "utils"),
]
for path in paths_to_add:
    if path not in sys.path:
        sys.path.insert(0, path)

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}


@task
def init_context(**context) -> Dict[str, Any]:
    """Lit les paramètres transmis au DAG."""
    dag_run = context.get("dag_run")
    conf = dag_run.conf or {}

    dataset_id = conf.get("dataset_id")
    is_public = conf.get("is_public", False)

    if not dataset_id:
        raise ValueError("dataset_id manquant pour push_atlas_pipeline")

    return {
        "dataset_id": dataset_id,
        "is_public": is_public,
    }


@task
def run_push(init_data: Dict[str, Any]) -> Dict[str, Any]:
    """Exécute le push Atlas en réutilisant la logique backend existante."""
    # Imports retardés pour éviter un import DAG trop lourd côté scheduler/webserver.
    from db.connexion_db import SessionLocal
    import db.projects  # noqa: F401
    import db.users  # noqa: F401
    from db.users import User
    from routes.push_atlas import run_push_atlas_service

    db = SessionLocal()
    try:
        configured_user = os.getenv("AIRFLOW_SERVICE_USER_ID")
        if configured_user:
            service_user = configured_user
        else:
            first_user = db.query(User.employee_id).first()
            service_user = first_user[0] if first_user else "airflow_service"

        result = run_push_atlas_service(
            dataset_id=init_data["dataset_id"],
            is_public=init_data.get("is_public", False),
            db=db,
            user={"sub": service_user, "employee_id": service_user},
        )
        return result
    finally:
        db.close()


with DAG(
    dag_id="push_atlas_pipeline",
    description="Push Atlas orchestré via Airflow",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["atlas", "quality"],
) as dag:
    ctx = init_context()
    run_push(ctx)

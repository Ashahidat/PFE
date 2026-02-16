# db/crud/data_quality_results.py
import sys
import os

PROJECT_ROOT = "/home/ashahi/PFE/pip/data_quality/app/backend"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy.orm import Session
from db.models.data_quality_results import DataQualityResult

# -----------------------------
# CREATE
# -----------------------------
def create_result(db: Session, dag_run_uuid: str, dataset_version_id: str, validator_name: str, res: dict):
    result = DataQualityResult(
        dag_run_uuid=dag_run_uuid,
        dataset_version_id=dataset_version_id,
        validator_name=validator_name,
        check_type=res.get("type de test"),
        column_name=res.get("colonne testée"),
        status=res.get("statut"),
        error_count=res.get("nombre"),
        ratio=res.get("ratio"),
        alert=res.get("alerte"),
        examples=res.get("exemples", [])
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result

# -----------------------------
# READ
# -----------------------------
def get_results_by_dag_run(db: Session, dag_run_uuid: str):
    return db.query(DataQualityResult).filter(DataQualityResult.dag_run_uuid == dag_run_uuid).all()

def get_results_by_dataset_version(db: Session, dataset_version_id: str):
    return db.query(DataQualityResult).filter(DataQualityResult.dataset_version_id == dataset_version_id).all()

def get_result_by_id(db: Session, result_id: str):
    return db.query(DataQualityResult).filter(DataQualityResult.id == result_id).first()

# -----------------------------
# UPDATE
# -----------------------------
def update_result_status(db: Session, result_id: str, status: str, alert: bool = None):
    result = db.query(DataQualityResult).filter(DataQualityResult.id == result_id).first()
    if not result:
        return None
    result.status = status
    if alert is not None:
        result.alert = alert
    db.commit()
    db.refresh(result)
    return result

def add_examples_to_result(db: Session, result_id: str, examples: list):
    result = db.query(DataQualityResult).filter(DataQualityResult.id == result_id).first()
    if not result:
        return None
    current_examples = result.examples or []
    current_examples.extend(examples)
    result.examples = current_examples
    db.commit()
    db.refresh(result)
    return result

# -----------------------------
# DELETE
# -----------------------------
def delete_result(db: Session, result_id: str):
    result = db.query(DataQualityResult).filter(DataQualityResult.id == result_id).first()
    if not result:
        return False
    db.delete(result)
    db.commit()
    return True

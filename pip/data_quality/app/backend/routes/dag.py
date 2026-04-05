from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import uuid
from db.connexion_db import get_db
from db.datasets import Dataset
from db.dag_runs import DAGRun
import sys
import os

# Ajouter le chemin correct vers le dossier utils
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..'))
from utils.airflow_utils import trigger_dag, get_dag_status
from jwt_dependencies import get_current_user
from fastapi import Request
from pydantic import BaseModel
from typing import Dict, Any

class DAGRunRequest(BaseModel):
    rules: Dict[str, Any]
    dataset_id: str


router = APIRouter()

@router.post("/run-dag")
async def run_dag(request: DAGRunRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    dataset = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    dag_id = "modular_validation_dag"
    config = {"file_path": dataset.file_path, "rules": request.rules}
    dag_run_id, resp = trigger_dag(dag_id, config)
    if not dag_run_id:
        raise HTTPException(status_code=500, detail="Erreur lancement DAG")

    dag_run = DAGRun(
        id=str(uuid.uuid4()),
        dataset_id=dataset.id,
        dag_run_id=dag_run_id,
        rules={"dag_id": dag_id, "payload": request.rules},
        status="running"
    )
    db.add(dag_run)
    db.commit()
    db.refresh(dag_run)

    return {"message": "DAG lancé", "dag_run_id": dag_run_id}


@router.post("/run-dag-v2")
async def run_dag_v2(
    request: DAGRunRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Version 2 du DAG avec orchestration modulaire
    """
    dataset = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    config = {
        "file_path": dataset.file_path,
        "rules": request.rules,
        "dataset_version_id": None
    }
    
    dag_run_id, resp = trigger_dag("data_quality_pipeline_v2", config)
    
    if not dag_run_id:
        raise HTTPException(status_code=500, detail="Erreur lancement DAG")

    dag_id = "data_quality_pipeline_v2"
    dag_run = DAGRun(
        id=str(uuid.uuid4()),
        dataset_id=dataset.id,
        dag_run_id=dag_run_id,
        rules={"dag_id": dag_id, "payload": request.rules},
        status="running"
    )
    db.add(dag_run)
    db.commit()

    return {"message": "DAG v2 lancé", "dag_run_id": dag_run_id}


@router.get("/dag-status/{dag_run_id}")
async def dag_status(dag_run_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    dag_run = db.query(DAGRun).filter(DAGRun.dag_run_id == dag_run_id).first()
    if not dag_run:
        raise HTTPException(status_code=404, detail="DAG Run introuvable")

    dag_rules = dag_run.rules or {}
    dag_id = dag_rules.get("dag_id") if isinstance(dag_rules, dict) else None
    state = get_dag_status(dag_run.dag_run_id, dag_id=dag_id)
    dag_run.status = state
    db.commit()
    return {"state": state}

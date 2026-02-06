# routes/dag.py

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import uuid
from db.connexion_db import get_db
from db.datasets import Dataset
from db.dag_runs import DAGRun
import sys
import os
from datetime import datetime

# Ajouter le chemin correct vers le dossier utils
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..'))
from utils.airflow_utils import trigger_dag, get_dag_status
from jwt_dependencies import get_current_user
from fastapi import Request
from pydantic import BaseModel
from typing import Dict, Any
from atlas.client import atlas_post, ATLAS_ENTITY_BULK_URL, ATLAS_RELATIONSHIP_URL
import logging

logger = logging.getLogger(__name__)

class DAGRunRequest(BaseModel):
    rules: Dict[str, Any]
    dataset_id: str

router = APIRouter()

def create_validation_lineage_in_atlas(dataset_guid: str, dag_run_id: str, user: dict):
    """
    Crée un lineage de validation dans Atlas
    """
    try:
        logger.info(f"🎯 Création lineage validation pour {dataset_guid}")
        
        # 1. Créer un processus de validation dans Atlas
        validation_process_id = f"validation_{dag_run_id}"
        
        validation_process_payload = {
            "entities": [{
                "typeName": "ValidationProcess",
                "attributes": {
                    "qualifiedName": validation_process_id,
                    "name": f"Validation: {dag_run_id}",
                    "dagRunId": dag_run_id,
                    "status": "running",
                    "executedBy": user.get("sub", "unknown"),
                    "executionTimestamp": datetime.now().isoformat()
                },
                "guid": f"-validation-{dag_run_id}"
            }]
        }
        
        logger.info(f"📤 Création processus validation: {validation_process_payload}")
        
        res = atlas_post(ATLAS_ENTITY_BULK_URL, validation_process_payload)
        
        if res.status_code != 200:
            logger.error(f"❌ Erreur création processus validation: {res.status_code} - {res.text}")
            return None
        
        res_data = res.json()
        validation_guid = res_data.get("guidAssignments", {}).get(f"-validation-{dag_run_id}")
        
        if not validation_guid:
            logger.error(f"❌ Pas de GUID assigné pour le processus validation")
            logger.error(f"Réponse: {res_data}")
            return None
        
        logger.info(f"✅ Processus validation créé: {validation_guid}")
        
        # 2. Lier au dataset
        relationship_payload = {
            "typeName": "dataset_validated_by",
            "end1": {
                "guid": validation_guid,
                "typeName": "ValidationProcess",
                "uniqueAttributes": {"qualifiedName": validation_process_id}
            },
            "end2": {
                "guid": dataset_guid,
                "typeName": "DataSet",
                "uniqueAttributes": {"qualifiedName": ""}  # Remplacer par le qualifiedName réel si disponible
            },
            "label": "validated_by",
            "attributes": {}
        }
        
        logger.info(f"🔗 Création relation validation: {relationship_payload}")
        
        rel_res = atlas_post(ATLAS_RELATIONSHIP_URL, relationship_payload)
        
        if rel_res.status_code in [200, 204]:
            logger.info(f"✅ Relation validation créée: {validation_guid} → {dataset_guid}")
            return validation_guid
        else:
            logger.error(f"❌ Erreur création relation validation: {rel_res.status_code} - {rel_res.text}")
            return None
            
    except Exception as e:
        logger.error(f"❌ Erreur création lineage validation: {e}", exc_info=True)
        return None

@router.post("/run-dag")
async def run_dag(request: DAGRunRequest, db: Session = Depends(get_db), user=Depends(get_current_user)):
    dataset = db.query(Dataset).filter(Dataset.id == request.dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    config = {"file_path": dataset.file_path, "rules": request.rules}
    dag_run_id, resp = trigger_dag(config)
    if not dag_run_id:
        raise HTTPException(status_code=500, detail="Erreur lancement DAG")

    dag_run = DAGRun(
        id=str(uuid.uuid4()),
        dataset_id=dataset.id,
        dag_run_id=dag_run_id,
        rules=request.rules,
        status="running"
    )
    db.add(dag_run)
    db.commit()
    db.refresh(dag_run)

    # Créer le lineage dans Atlas
    if dataset.atlas_guid:
        validation_guid = create_validation_lineage_in_atlas(
            dataset.atlas_guid,
            dag_run_id,
            user
        )
        if validation_guid:
            logger.info(f"✅ Lineage validation créé: {validation_guid}")
    
    return {"message": "DAG lancé", "dag_run_id": dag_run_id}

@router.get("/dag-status/{dag_run_id}")
async def dag_status(dag_run_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    dag_run = db.query(DAGRun).filter(DAGRun.dag_run_id == dag_run_id).first()
    if not dag_run:
        raise HTTPException(status_code=404, detail="DAG Run introuvable")

    state = get_dag_status(dag_run.dag_run_id)
    dag_run.status = state
    db.commit()
    
    # Mettre à jour le statut dans Atlas si besoin
    if dag_run.dataset_id:
        dataset = db.query(Dataset).filter(Dataset.id == dag_run.dataset_id).first()
        if dataset and dataset.atlas_guid and state in ["success", "failed"]:
            # Ici tu pourrais mettre à jour l'attribut status du ValidationProcess
            pass
    
    return {"state": state}
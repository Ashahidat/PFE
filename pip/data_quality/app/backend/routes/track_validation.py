# routes/track_validation.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.connexion_db import get_db
from jwt_dependencies import get_current_user
from atlas.client import atlas_post, ATLAS_ENTITY_BULK_URL, ATLAS_RELATIONSHIP_URL
from db.datasets import Dataset
import logging
from datetime import datetime

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/track-validation/{dataset_id}")
async def track_validation(
    dataset_id: str,
    dag_run_id: str,
    status: str = "running",
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Crée un lineage de validation dans Atlas
    À appeler après chaque exécution de DAG
    """
    try:
        # 1. Récupérer le dataset et son GUID Atlas
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset or not dataset.atlas_guid:
            raise HTTPException(404, "Dataset non trouvé dans Atlas")
        
        dataset_guid = dataset.atlas_guid
        
        # 2. Créer un processus de validation dans Atlas
        validation_process_payload = {
            "entities": [{
                "typeName": "ValidationProcess",
                "attributes": {
                    "qualifiedName": f"validation_{dag_run_id}",
                    "name": f"Validation: {dag_run_id}",
                    "dagRunId": dag_run_id,
                    "status": status,
                    "executedBy": user.get("sub", "unknown"),
                    "executionTimestamp": datetime.now().isoformat()
                },
                "guid": f"-validation-{dag_run_id}"
            }]
        }
        
        res = atlas_post(ATLAS_ENTITY_BULK_URL, validation_process_payload)
        validation_guid = res.json().get("guidAssignments", {}).get(f"-validation-{dag_run_id}")
        
        if not validation_guid:
            raise HTTPException(500, "Impossible de créer le processus de validation")
        
        # 3. Lier au dataset
        relationship_payload = {
            "typeName": "dataset_validated_by",
            "end1": {"guid": validation_guid, "typeName": "ValidationProcess"},
            "end2": {"guid": dataset_guid, "typeName": "DataSet"},
            "attributes": {}
        }
        
        atlas_post(ATLAS_RELATIONSHIP_URL, relationship_payload)
        
        logger.info(f"✅ Lineage validation créé: {dataset_guid} ← {validation_guid}")
        
        return {
            "success": True,
            "validation_process_guid": validation_guid,
            "message": "Validation trackée dans Atlas"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur tracking validation: {e}")
        raise HTTPException(500, f"Erreur: {str(e)}")
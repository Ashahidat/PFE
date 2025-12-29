from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.connexion_db import get_db
from jwt_dependencies import get_current_user
import logging

# IMPORT CORRECT du use case
try:
    from db.classifications_use_case import apply_classification_use_case
except ImportError:
    # Essayez un autre chemin si nécessaire
    from services.classifications_service import apply_classification_use_case

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/apply-classification")
def apply_classification(payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Payload envoyé par le frontend :
    {
        "entity_type": "DATASET" | "COLUMN",
        "entity_id": "...",
        "atlas_guid": "...",
        "classification_name": "PUBLIC" | "INTERNAL" | "CONFIDENTIAL" | "PII"
        "attributes": { "level": "high" }  # pour CONFIDENTIAL
    }
    """
    logger.info("📨 Requête de classification reçue")
    logger.info(f"Payload: {payload}")
    
    # Validation du payload
    required_fields = ["entity_type", "entity_id", "atlas_guid", "classification_name"]
    for field in required_fields:
        if field not in payload:
            logger.error(f"Champ manquant: {field}")
            raise HTTPException(status_code=400, detail=f"Champ manquant: {field}")

    # Validation de la classification
    valid_classifications = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
    if payload["classification_name"] not in valid_classifications:
        logger.error(f"Classification invalide: {payload['classification_name']}")
        raise HTTPException(status_code=400, detail=f"Classification invalide. Valides: {valid_classifications}")

    try:
        result = apply_classification_use_case(
            db=db,
            entity_type=payload["entity_type"],
            entity_id=payload["entity_id"],
            atlas_guid=payload["atlas_guid"],
            classification_name=payload["classification_name"],
            attributes=payload.get("attributes"),
            user=user
        )
        
        logger.info(f"✅ Classification appliquée avec succès. ID: {result.id}")
        return {
            "success": True, 
            "classification_id": str(result.id),
            "message": "Classification appliquée"
        }
        
    except ValueError as e:
        logger.error(f"❌ Erreur de validation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'application de la classification: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
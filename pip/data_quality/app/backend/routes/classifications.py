from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.connexion_db import get_db
from jwt_dependencies import get_current_user
import logging
from db.classifications_use_case import apply_classification_use_case


router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/apply-classification")
def apply_classification(payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Payload pour datasets:
    {
        "entity_type": "DATASET",
        "entity_id": "...",
        "atlas_guid": "...",
        "classification_name": "PUBLIC" | "INTERNAL" | "CONFIDENTIAL" | "RESTRICTED"
        "attributes": { "level": "high" }  # pour CONFIDENTIAL
    }
    
    Payload pour colonnes:
    {
        "entity_type": "COLUMN",
        "entity_id": "dataset_id",  # ID du dataset parent
        "atlas_guid": "...",  # GUID de la colonne dans Atlas
        "classification_name": "PII_DIRECT" | "PII_QUASI" | "SENSITIVE" | "ENCRYPTED"
        "column_name": "nom_de_la_colonne",
        "attributes": {}
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
    
    # Validation spécifique pour les colonnes
    if payload["entity_type"] == "COLUMN" and "column_name" not in payload:
        logger.error("Champ manquant: column_name (requis pour les colonnes)")
        raise HTTPException(status_code=400, detail="column_name est requis pour les classifications de colonne")

    try:
        result = apply_classification_use_case(
            db=db,
            entity_type=payload["entity_type"],
            entity_id=payload["entity_id"],
            atlas_guid=payload["atlas_guid"],
            classification_name=payload["classification_name"],
            attributes=payload.get("attributes", {}),
            user=user,
            column_name=payload.get("column_name")  # Nouveau paramètre
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
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from db.connexion_db import get_db
from jwt_dependencies import get_current_user
from db.classifications_use_case import apply_classification_use_case

router = APIRouter()

import logging

print("-----------------------------------------------------------------------------------------------")
print("⚠️  Route 'classifications.py' utilisé - Vérifiez la version Atlas (V2) pour la compatibilité ⚠️")
print("-----------------------------------------------------------------------------------------------")

@router.post("/apply-classification")
def apply_classification(payload: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Payload envoyé par le frontend :
    {
        "entity_type": "DATASET" | "COLUMN",
        "entity_id": "...",
        "atlas_guid": "...",
        "classification_name": "PII" | "CONFIDENTIAL" | ...
        "attributes": { "type": "EMAIL" }
    }
    """
    logger.info("📨 Requête de classification reçue")
    logger.info(f"Payload: {payload}")
    logger.info(f"User: {user.employee_id if user else 'None'}")

    # Validation du payload
    required_fields = ["entity_type", "entity_id", "atlas_guid", "classification_name"]
    for field in required_fields:
        if field not in payload:
            logger.error(f"Champ manquant: {field}")
            raise HTTPException(status_code=400, detail=f"Champ manquant: {field}")

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
        return {"success": True, "classification_id": str(result.id)}
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'application de la classification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
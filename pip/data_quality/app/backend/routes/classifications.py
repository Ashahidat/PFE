from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.connexion_db import get_db
from jwt_dependencies import get_current_user
import logging
import sys
import os
from db.classifications_use_case import apply_classification_use_case
from typing import Optional


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


# Ajoutez cette route APRES la route apply-classification
@router.post("/sync-classifications")
def sync_classifications_endpoint(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Endpoint pour synchroniser manuellement les classifications
    Options:
    - Sans paramètres: synchronise tout
    - Avec entity_type et entity_id: synchronise une entité spécifique
    """
    # Vérifier les permissions (seuls les admins)
    if not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Permission refusée")
    
    try:
        from sync_atlas_classifications import sync_all_classifications, sync_specific_entity
        
        if entity_type and entity_id:
            # Synchronisation d'une entité spécifique
            logger.info(f"🔄 Synchronisation manuelle de {entity_type}:{entity_id}")
            result = sync_specific_entity(entity_type, entity_id, db)
            
            if result:
                return {
                    "success": True,
                    "message": "Synchronisation spécifique terminée",
                    "results": result
                }
            else:
                raise HTTPException(status_code=404, detail="Entité non trouvée ou erreur de synchronisation")
        else:
            # Synchronisation globale
            logger.info("🔄 Synchronisation manuelle globale déclenchée")
            sync_all_classifications(db)
            
            return {
                "success": True,
                "message": "Synchronisation globale terminée"
            }
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la synchronisation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sync-status")
def get_sync_status(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Vérifie l'état de synchronisation d'une entité
    """
    try:
        from sync_atlas_classifications import get_atlas_classifications
        
        if not entity_type or not entity_id:
            raise HTTPException(status_code=400, detail="entity_type et entity_id requis")
        
        # Trouver l'entité et son GUID
        if entity_type.upper() == "DATASET":
            entity = db.query(Dataset).filter(Dataset.id == entity_id).first()
        elif entity_type.upper() == "COLUMN":
            entity = db.query(Column).filter(Column.id == entity_id).first()
        else:
            raise HTTPException(status_code=400, detail="Type d'entité non supporté")
        
        if not entity:
            raise HTTPException(status_code=404, detail="Entité non trouvée")
        
        if not entity.atlas_guid:
            return {
                "has_atlas_guid": False,
                "message": "L'entité n'a pas de GUID Atlas"
            }
        
        # Récupérer les classifications depuis Atlas
        atlas_classifications = get_atlas_classifications(entity.atlas_guid)
        
        # Récupérer les classifications depuis notre base
        from db.classifications_crud import get_classifications_by_entity
        db_classifications = get_classifications_by_entity(
            db, 
            entity_type=entity_type,
            entity_id=entity_id,
            active_only=True
        )
        
        return {
            "has_atlas_guid": True,
            "atlas_guid": entity.atlas_guid,
            "atlas_classifications": [
                {
                    "name": c.get("typeName"),
                    "attributes": c.get("attributes", {})
                }
                for c in atlas_classifications
            ],
            "database_classifications": [
                {
                    "id": str(c.id),
                    "name": c.classification_name,
                    "attributes": c.classification_attributes,
                    "applied_by": c.applied_by,
                    "applied_at": c.applied_at.isoformat() if c.applied_at else None
                }
                for c in db_classifications
            ],
            "in_sync": len(atlas_classifications) == len(db_classifications)
        }
        
    except Exception as e:
        logger.error(f"Erreur vérification statut: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
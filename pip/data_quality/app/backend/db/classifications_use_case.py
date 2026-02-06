# db/classification_use_case.py

from atlas.classifications import add_classification
from db.classifications_crud import (
    disable_active_classifications,
    create_entity_classification
)
from db.users_crud import get_user_department_bu  # Import de la nouvelle fonction
import logging

logger = logging.getLogger(__name__)

from sqlalchemy.exc import IntegrityError

from atlas.classifications_validations import (
    validate_entity_classification,
    validate_dataset_columns_consistency,
    ClassificationValidationError
)
from datetime import datetime 
from atlas.client import atlas_post, ATLAS_ENTITY_BULK_URL, ATLAS_RELATIONSHIP_URL
import sys
sys.path.append("/home/ashahi/PFE/pip/data_quality/app/backend")
from atlas.classifications import track_classification_lineage


def track_classification_event(entity_type, entity_atlas_guid, classification_name, user_id):
    """
    Fonction simple pour tracker une classification dans Atlas
    """
    try:
        # Créer un ID unique pour le processus
        process_id = f"classification_{entity_atlas_guid}_{int(datetime.now().timestamp())}"
        
        # 1. Créer le processus de classification
        process_payload = {
            "entities": [{
                "typeName": "ClassificationProcess",
                "attributes": {
                    "qualifiedName": process_id,
                    "name": f"Classification: {classification_name}",
                    "classificationType": entity_type,
                    "classificationName": classification_name,
                    "executedBy": user_id,
                    "executionTimestamp": datetime.now().isoformat()
                },
                "guid": f"-{process_id}"
            }]
        }
        
        # Envoyer à Atlas
        res = atlas_post(ATLAS_ENTITY_BULK_URL, process_payload)
        process_guid = res.json().get("guidAssignments", {}).get(f"-{process_id}")
        
        if not process_guid:
            logger.warning("❌ Impossible de créer le processus de classification")
            return None
        
        # 2. Lier le processus à l'entité (dataset ou colonne)
        # Déterminer le type Atlas
        if entity_type == "DATASET":
            atlas_entity_type = "DataSet"
        else:  # COLUMN
            atlas_entity_type = "Column"
        
        # Créer la relation
        relationship_payload = {
            "typeName": "entity_classified_by",
            "end1": {"guid": process_guid, "typeName": "ClassificationProcess"},
            "end2": {"guid": entity_atlas_guid, "typeName": atlas_entity_type},
            "attributes": {}
        }
        
        atlas_post(ATLAS_RELATIONSHIP_URL, relationship_payload)
        
        # logger.info(f"✅ Classification trackée: {entity_atlas_guid} ← {process_guid}")
        return process_guid
        
    except Exception as e:
        logger.warning(f"⚠️ Tracking classification échoué (non bloquant): {str(e)[:100]}")
        return None


# db/classification_use_case.py - MODIFIER la fonction apply_classification_use_case

def apply_classification_use_case(
    db,
    *,
    entity_type,
    entity_id,
    atlas_guid,
    classification_name,
    attributes,
    user,
    column_name: str = None
):
    logger.info(f"🚀 Début use_case - {entity_type}:{entity_id} -> {classification_name}")
    
    try:
        # Validation de la classification
        validate_entity_classification(entity_type, classification_name)
        
        # Si c'est une classification de colonne, valider la cohérence avec le dataset
        if entity_type == "COLUMN" and column_name:
            validate_dataset_columns_consistency(
                db, 
                entity_id,  # dataset_id
                {column_name: classification_name}
            )
        
        # Vérifier et nettoyer la transaction
        if db.in_transaction():
            # logger.warning("⚠️ Transaction déjà active - rollback")
            db.rollback()
        
        # Récupérer l'employee_id depuis le token
        employee_id = user.get("employee_id") or user.get("sub")
        
        if not employee_id:
            raise ValueError("Identifiant utilisateur manquant dans le token")
        
        # Récupérer department et business_unit
        dept_bu = get_user_department_bu(db, employee_id)
        
        if not dept_bu:
            logger.error(f"❌ Utilisateur {employee_id} non trouvé dans la base de données")
            raise ValueError(f"Utilisateur {employee_id} non trouvé dans la base de données")
        
        department, business_unit = dept_bu
        # logger.info(f"Utilisateur trouvé: {employee_id}, Département: {department}, Business Unit: {business_unit}")
        
        # 1️⃣ Désactiver anciennes classifications
        rows_updated = disable_active_classifications(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            column_name=column_name
        )
        # logger.info(f"Anciennes classifications désactivées en base: {rows_updated}")

        # 2️⃣ Créer nouvelle classification EN BASE
        classification = create_entity_classification(
            db=db,
            entity_type=entity_type,
            entity_id=entity_id,
            atlas_guid=atlas_guid,
            classification_name=classification_name,
            classification_attributes=attributes,
            applied_by=employee_id,
            department=department,
            business_unit=business_unit,
            column_name=column_name
        )

        db.flush()

        # 3️⃣ Ajouter à ATLAS (si pas déjà présent)
        atlas_response = add_classification(
            atlas_guid,
            classification_name,
            attributes
        )
        
        /logger.info(f"Atlas response: {atlas_response}")
        
        # 4️⃣ CRÉER LE LINEAGE DANS ATLAS
        user_id = user.get("sub", "unknown") if user else "system"
        process_guid = track_classification_lineage(
            entity_type=entity_type,
            entity_atlas_guid=atlas_guid,
            classification_name=classification_name,
            user_id=user_id
        )
        
        if process_guid:
            # logger.info(f"✅ Lineage classification créé: {process_guid}")
        
        # Commit
        db.commit()

        return classification

    except ClassificationValidationError as e:
        logger.error(f"❌ Erreur de validation: {str(e)}")
        if db.in_transaction():
            db.rollback()
        raise ValueError(str(e)) from e
    except IntegrityError as e:
        logger.error("❌ Violation unicité classification active", exc_info=True)
        if db.in_transaction():
            db.rollback()
        raise ValueError(
            "Une classification active existe déjà pour cette entité."
        ) from e
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'application de la classification: {str(e)}")
        if db.in_transaction():
            db.rollback()
        raise
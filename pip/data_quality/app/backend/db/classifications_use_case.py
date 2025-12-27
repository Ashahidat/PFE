from atlas.classifications import add_classification
from db.classifications_crud import (
    disable_active_classifications,
    create_entity_classification
)
from db.users_crud import get_user_department_bu  # Import de la nouvelle fonction
import logging

logger = logging.getLogger(__name__)

from sqlalchemy.exc import IntegrityError

def apply_classification_use_case(
    db,
    *,
    entity_type,
    entity_id,
    atlas_guid,
    classification_name,
    attributes,
    user
):
    logger.info(f"🚀 Début use_case - {entity_type}:{entity_id} -> {classification_name}")
    
    try:
        with db.begin():
            # Récupérer l'employee_id depuis le token
            employee_id = user.get("employee_id") or user.get("sub")
            
            if not employee_id:
                raise ValueError("Identifiant utilisateur manquant dans le token")
            
            # Récupérer department et business_unit depuis la table users
            dept_bu = get_user_department_bu(db, employee_id)
            
            if not dept_bu:
                logger.error(f"❌ Utilisateur {employee_id} non trouvé dans la base de données")
                raise ValueError(f"Utilisateur {employee_id} non trouvé dans la base de données")
            
            department, business_unit = dept_bu
            logger.info(f"Utilisateur trouvé: {employee_id}, Département: {department}, Business Unit: {business_unit}")
            
            # 1️⃣ Désactiver anciennes classifications EN BASE
            rows_updated = disable_active_classifications(
                db,
                entity_type=entity_type,
                entity_id=entity_id
            )
            logger.info(f"Anciennes classifications désactivées en base: {rows_updated}")

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
                business_unit=business_unit
            )

            db.flush()

            # 3️⃣ Ajouter à ATLAS (si pas déjà présent)
            atlas_response = add_classification(
                atlas_guid,
                classification_name,
                attributes
            )
            
            logger.info(f"Atlas response: {atlas_response}")
            
            # 4️⃣ Si la classification existait déjà dans Atlas, c'est OK
            if atlas_response and atlas_response.get("status") == "already_exists":
                logger.info("Classification déjà présente dans Atlas - Enregistrement en base OK")
            
        return classification

    except IntegrityError as e:
        logger.error("❌ Violation unicité classification active", exc_info=True)
        raise ValueError(
            "Une classification active existe déjà pour cette entité."
        ) from e
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'application de la classification: {str(e)}")
        raise
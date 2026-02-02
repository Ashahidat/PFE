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


def apply_classification_use_case(
    db,
    *,
    entity_type,
    entity_id,
    atlas_guid,
    classification_name,
    attributes,
    user,
    column_name: str = None  # Nouveau paramètre optionnel
):
    logger.info(f"🚀 Début use_case - {entity_type}:{entity_id} -> {classification_name}")
    
    try:
        # Validation de la classification
        validate_entity_classification(entity_type, classification_name)
        
        # Si c'est une classification de colonne, valider la cohérence avec le dataset
        if entity_type == "COLUMN" and column_name:
            # Pour une colonne, entity_id est le dataset_id
            # Valider la cohérence
            validate_dataset_columns_consistency(
                db, 
                entity_id,  # dataset_id
                {column_name: classification_name}
            )
        
        # ⚠️ SUPPRIMER: with db.begin(): 
        # ✅ AJOUTER: Vérifier et nettoyer la transaction
        if db.in_transaction():
            logger.warning("⚠️ Transaction déjà active - rollback")
            db.rollback()
        
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
            entity_id=entity_id,
            column_name=column_name  # Nouveau paramètre
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
            business_unit=business_unit,
            column_name=column_name  # Nouveau paramètre
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
        
        # ✅ AJOUTER: Commit manuel
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
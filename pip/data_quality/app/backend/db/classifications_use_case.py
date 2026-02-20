# db/classification_use_case.py

from atlas.classifications import add_classification
from db.classifications_crud import (
    disable_active_classifications,
    create_entity_classification
)
from db.users_crud import get_user_department
import logging

from sqlalchemy.exc import IntegrityError

from atlas.classifications_validations import (
    validate_entity_classification,
    validate_dataset_columns_consistency,
    ClassificationValidationError
)

logger = logging.getLogger(__name__)


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
        # 1️⃣ Validation de la classification
        validate_entity_classification(entity_type, classification_name)

        # 2️⃣ Validation cohérence colonne/dataset si nécessaire
        if entity_type == "COLUMN" and column_name:
            validate_dataset_columns_consistency(
                db,
                entity_id,  # dataset_id
                {column_name: classification_name}
            )

        # 3️⃣ Nettoyage transaction si déjà active
        if db.in_transaction():
            logger.warning("⚠️ Transaction déjà active - rollback")
            db.rollback()

        # 4️⃣ Récupération employee_id depuis le token
        employee_id = user.get("employee_id") or user.get("sub")

        if not employee_id:
            raise ValueError("Identifiant utilisateur manquant dans le token")

        # 5️⃣ Récupération du département uniquement
        department = get_user_department(db, employee_id)

        if not department:
            logger.error(f"❌ Utilisateur {employee_id} non trouvé dans la base de données")
            raise ValueError(f"Utilisateur {employee_id} non trouvé dans la base de données")

        logger.info(f"Utilisateur trouvé: {employee_id}, Département: {department}")

        # 6️⃣ Désactiver anciennes classifications EN BASE
        rows_updated = disable_active_classifications(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            column_name=column_name
        )
        logger.info(f"Anciennes classifications désactivées en base: {rows_updated}")

        # 7️⃣ Créer nouvelle classification EN BASE
        classification = create_entity_classification(
            db=db,
            entity_type=entity_type,
            entity_id=entity_id,
            atlas_guid=atlas_guid,
            classification_name=classification_name,
            classification_attributes=attributes,
            applied_by=employee_id,
            department=department,
            column_name=column_name
        )

        db.flush()

        # 8️⃣ Ajouter à ATLAS
        atlas_response = add_classification(
            atlas_guid,
            classification_name,
            attributes
        )

        logger.info(f"Atlas response: {atlas_response}")

        if atlas_response and atlas_response.get("status") == "already_exists":
            logger.info("Classification déjà présente dans Atlas - Enregistrement en base OK")

        # 9️⃣ Commit final
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
        logger.error(f"❌ Erreur lors de l'application de la classification: {str(e)}", exc_info=True)
        if db.in_transaction():
            db.rollback()
        raise
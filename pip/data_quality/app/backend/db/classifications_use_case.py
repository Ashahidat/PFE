from atlas.classifications import add_classification
from db.classifications_crud import (
    disable_active_classifications,
    create_entity_classification
)

import logging

logger = logging.getLogger(__name__)

from sqlalchemy.exc import IntegrityError
from atlas.classifications import add_classification
from db.classifications_crud import (
    disable_active_classifications,
    create_entity_classification
)
import logging

logger = logging.getLogger(__name__)

def apply_classification_use_case(
    db,
    *,
    entity_type,
    entity_id,
    atlas_guid,
    classification_name,
    attributes,
    user  # ← user est maintenant un dict
):
    logger.info(f"🚀 Début use_case - {entity_type}:{entity_id} -> {classification_name}")
    logger.info(f"User dict: {user}")  # Pour debug

    try:
        with db.begin():
            # 1️⃣ Désactiver anciennes classifications
            rows_updated = disable_active_classifications(
                db,
                entity_type=entity_type,
                entity_id=entity_id
            )
            logger.info(f"Anciennes classifications désactivées: {rows_updated}")

            # 2️⃣ Créer nouvelle classification
            # EXTRACTION DES INFOS USER DU DICT
            applied_by = user.get("employee_id") or user.get("sub")  # selon votre structure
            department = user.get("department", "Unknown")
            business_unit = user.get("business_unit", "Unknown")
            
            classification = create_entity_classification(
                db=db,
                entity_type=entity_type,
                entity_id=entity_id,
                atlas_guid=atlas_guid,
                classification_name=classification_name,
                classification_attributes=attributes,
                applied_by=applied_by,
                department=department,
                business_unit=business_unit
            )

            db.flush()

            # 3️⃣ Atlas
            atlas_response = add_classification(
                atlas_guid,
                classification_name,
                attributes
            )
            logger.info(f"Atlas response: {atlas_response}")

        return classification

    except IntegrityError as e:
        logger.error("❌ Violation unicité classification active", exc_info=True)
        raise ValueError(
            "Une classification active existe déjà pour cette entité."
        ) from e
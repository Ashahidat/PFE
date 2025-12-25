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
    user
):
    logger.info(f"🚀 Début use_case - {entity_type}:{entity_id} -> {classification_name}")

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
            classification = create_entity_classification(
                db=db,
                entity_type=entity_type,
                entity_id=entity_id,
                atlas_guid=atlas_guid,
                classification_name=classification_name,
                classification_attributes=attributes,
                applied_by=user.employee_id,
                department=user.department,
                business_unit=user.business_unit
            )

            db.flush()  # force insertion

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

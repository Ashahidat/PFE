# db/classifications_crud.py

from sqlalchemy.orm import Session
from db.classifications import EntityClassification

def disable_active_classifications(
    db: Session,
    entity_type: str,
    entity_id
):
    rows = db.query(EntityClassification).filter(
        EntityClassification.entity_type == entity_type,
        EntityClassification.entity_id == entity_id,
        EntityClassification.is_active.is_(True)
    ).update(
        {"is_active": False},
        synchronize_session=False
    )
    return rows



def create_entity_classification(
    db: Session,
    entity_type: str,
    entity_id,
    atlas_guid: str,
    classification_name: str,
    classification_attributes: dict,
    applied_by: str,
    department: str,
    business_unit: str
):
    classification = EntityClassification(
        entity_type=entity_type,
        entity_id=entity_id,
        atlas_guid=atlas_guid,
        classification_name=classification_name,
        classification_attributes=classification_attributes,
        applied_by=applied_by,
        department=department,
        business_unit=business_unit
    )

    db.add(classification)
    return classification

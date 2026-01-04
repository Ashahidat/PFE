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

def get_classifications_by_entity(
    db: Session,
    *,
    entity_type: str,
    atlas_guid: str,  # ← Changez ce paramètre
    active_only: bool = True
):
    query = db.query(EntityClassification).filter(
        EntityClassification.entity_type == entity_type,
        EntityClassification.atlas_guid == atlas_guid  # ← Filtrer par atlas_guid
    )

    if active_only:
        query = query.filter(EntityClassification.is_active.is_(True))

    return query.all()


def disable_classification_by_id(
    db: Session,
    classification_id
):
    rows = db.query(EntityClassification).filter(
        EntityClassification.id == classification_id,
        EntityClassification.is_active.is_(True)
    ).update(
        {"is_active": False},
        synchronize_session=False
    )
    return rows

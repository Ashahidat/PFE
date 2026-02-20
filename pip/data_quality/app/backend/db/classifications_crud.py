# db/classifications_crud.py

from sqlalchemy.orm import Session
from db.classifications import EntityClassification

def disable_active_classifications(
    db: Session,
    entity_type: str,
    entity_id: str,
    column_name: str = None  # Nouveau paramètre optionnel
):
    """
    Désactive les classifications actives pour une entité
    Si column_name est fourni, filtre également par nom de colonne
    """
    query = db.query(EntityClassification).filter(
        EntityClassification.entity_type == entity_type,
        EntityClassification.entity_id == entity_id,
        EntityClassification.is_active.is_(True)
    )
    
    if column_name is not None:
        query = query.filter(EntityClassification.column_name == column_name)
    
    rows = query.update(
        {"is_active": False},
        synchronize_session=False
    )
    return rows

def create_entity_classification(
    db: Session,
    entity_type: str,
    entity_id: str,
    atlas_guid: str,
    classification_name: str,
    classification_attributes: dict,
    applied_by: str,
    department: str,
    column_name: str = None  # Nouveau paramètre optionnel
):
    """
    Crée une nouvelle classification d'entité
    """
    classification = EntityClassification(
        entity_type=entity_type,
        entity_id=entity_id,
        atlas_guid=atlas_guid,
        classification_name=classification_name,
        classification_attributes=classification_attributes,
        applied_by=applied_by,
        department=department,
        column_name=column_name  # Nouveau
    )

    db.add(classification)
    return classification
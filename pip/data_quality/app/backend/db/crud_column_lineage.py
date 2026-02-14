# db/crud_column_lineage.py
from sqlalchemy.orm import Session
from db.column_lineage import ColumnLineage
import uuid

def create_column_lineage(
    db: Session,
    logical_column_id: str,
    column_name: str,
    dataset_version_id: str,
    parent_column_id: str = None,
    data_type: str = None
):
    lineage = ColumnLineage(
        id=uuid.uuid4(),
        logical_column_id=logical_column_id,
        column_name=column_name,
        dataset_version_id=dataset_version_id,
        parent_column_id=parent_column_id,
        data_type=data_type
    )
    db.add(lineage)
    return lineage

def bulk_create_column_lineage(db: Session, lineages: list):
    for lineage in lineages:
        db.add(lineage)
    db.commit()
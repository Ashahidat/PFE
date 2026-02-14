# db/crud_dataset_versions.py
from sqlalchemy.orm import Session
from db.dataset_versions import DatasetVersion
import uuid

def create_dataset_version(
    db: Session,
    dataset_id: str,
    version_number: int,
    atlas_guid: str,
    parent_version_id: str = None,
    created_by: str = None,
    change_comment: str = None,
    source_file: str = None
):
    version = DatasetVersion(
        id=uuid.uuid4(),
        dataset_id=dataset_id,
        version_number=version_number,
        atlas_guid=atlas_guid,
        parent_version_id=parent_version_id,
        created_by=created_by,
        change_comment=change_comment,
        source_file=source_file
    )
    db.add(version)
    db.flush()  # Pour obtenir l'ID sans commit
    return version

def get_latest_version(db: Session, dataset_id: str):
    return db.query(DatasetVersion)\
        .filter(DatasetVersion.dataset_id == dataset_id)\
        .order_by(DatasetVersion.version_number.desc())\
        .first()

def get_version_by_atlas_guid(db: Session, atlas_guid: str):
    return db.query(DatasetVersion)\
        .filter(DatasetVersion.atlas_guid == atlas_guid)\
        .first()
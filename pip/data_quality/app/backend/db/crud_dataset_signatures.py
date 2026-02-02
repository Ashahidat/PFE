from sqlalchemy.orm import Session
from db.dataset_signatures import DatasetSignature
import uuid

def create_dataset_signature(
    db: Session,
    dataset_id: str,
    structure_hash: str,
    signature: dict,
    columns_count: int = None,
    rows_count: int = None,
    algo_version: str = "v1"
):
    ds_sig = DatasetSignature(
        id=uuid.uuid4(),
        dataset_id=dataset_id,
        structure_hash=structure_hash,
        signature=signature,
        columns_count=columns_count,
        rows_count=rows_count,
        algo_version=algo_version
    )
    db.add(ds_sig)
    db.commit()
    db.refresh(ds_sig)
    return ds_sig

def get_dataset_signatures(db: Session, dataset_id: str):
    return db.query(DatasetSignature).filter(DatasetSignature.dataset_id == dataset_id).all()

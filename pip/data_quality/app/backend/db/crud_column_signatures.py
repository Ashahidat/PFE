from sqlalchemy.orm import Session
from db.column_signatures import ColumnSignature
import uuid

def create_column_signature(
    db: Session,
    dataset_signature_id: str,
    column_name: str,
    data_type: str,
    mean: float = None,
    std: float = None,
    distinct_count: int = None,
    sample_hash: str = None
):
    col_sig = ColumnSignature(
        id=uuid.uuid4(),
        dataset_signature_id=dataset_signature_id,
        column_name=column_name,
        data_type=data_type,
        mean=mean,
        std=std,
        distinct_count=distinct_count,
        sample_hash=sample_hash
    )
    db.add(col_sig)
    db.commit()
    db.refresh(col_sig)
    return col_sig

def get_column_signatures(db: Session, dataset_signature_id: str):
    return db.query(ColumnSignature).filter(ColumnSignature.dataset_signature_id == dataset_signature_id).all()

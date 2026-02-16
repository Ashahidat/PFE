# db/crud_push_history.py
from sqlalchemy.orm import Session
from db.push_history import PushHistory
import uuid

def create_push_history(
    db: Session,
    dataset_id: str,
    pushed_by: str,
    status: str = "SUCCESS",
    error_message: str = None,
    execution_time_ms: int = None,
    columns_count: int = None,
    rows_count: int = None,
    parent_found: bool = False,
    similarity_score: float = None,
    propagated_columns_count: int = None
):
    push = PushHistory(
        id=uuid.uuid4(),
        dataset_id=dataset_id,
        pushed_by=pushed_by,
        status=status,
        error_message=error_message,
        execution_time_ms=execution_time_ms,
        columns_count=columns_count,
        rows_count=rows_count,
        parent_found=parent_found,
        similarity_score=similarity_score,
        propagated_columns_count=propagated_columns_count
    )
    db.add(push)
    db.commit()
    return push
# db/crud_processes.py
from sqlalchemy.orm import Session
from db.processes import Process
import uuid

def create_process_record(
    db: Session,
    atlas_process_guid: str,
    process_name: str,
    operation_type: str,
    output_dataset_version_id: str,
    input_dataset_version_id: str = None,
    created_by: str = None,
    execution_time_ms: int = None,
    status: str = "SUCCESS",
    metadata: dict = None
):
    process = Process(
        id=uuid.uuid4(),
        atlas_process_guid=atlas_process_guid,
        process_name=process_name,
        operation_type=operation_type,
        input_dataset_version_id=input_dataset_version_id,
        output_dataset_version_id=output_dataset_version_id,
        created_by=created_by,
        execution_time_ms=execution_time_ms,
        status=status,
        process_metadata=metadata
    )

    db.add(process)
    db.commit()
    return process

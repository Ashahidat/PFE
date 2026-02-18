from sqlalchemy.orm import Session
from db.data_quality_results import DataQualityResult

def create_data_quality_result(
    db: Session,
    dag_run_uuid,
    dataset_version_id,
    validator_name,
    check_type,
    column_name,
    status,
    error_count,
    ratio,
    alert,
    examples
):
    result = DataQualityResult(
        dag_run_uuid=dag_run_uuid,
        dataset_version_id=dataset_version_id,
        validator_name=validator_name,
        check_type=check_type,
        column_name=column_name,
        status=status,
        error_count=error_count,
        ratio=ratio,
        alert=alert,
        examples=examples
    )

    db.add(result)
    db.commit()
    db.refresh(result)

    return result

import json
from typing import List
from sqlalchemy.orm import Session
from db.crud_data_quality_results import create_data_quality_result

def save_data_quality_results_from_json(
    db: Session,
    dataset_version_id,
    dag_run_uuid,
    json_path: str
) -> List[str]:

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    checks = data["checks"]

    created_ids = []

    for check in checks:

        # parser ratio
        ratio_float = 0.0
        try:
            if "/" in check["ratio"]:
                num, denom = check["ratio"].split("/")
                ratio_float = float(num) / float(denom) if float(denom) != 0 else 0.0
            else:
                ratio_float = float(check["ratio"])
        except:
            ratio_float = 0.0

        result = create_data_quality_result(
            db=db,
            dag_run_uuid=dag_run_uuid,
            dataset_version_id=dataset_version_id,
            validator_name=check.get("validator_name", "unknown"),
            check_type=check["rule_type"],
            column_name=check.get("column_name"),
            status=check["status"],
            error_count=check.get("error_count", 0),
            ratio=ratio_float,
            alert=(check["status"].lower() == "failed"),
            examples=check.get("examples", [])
        )

        created_ids.append(str(result.id))

    return created_ids

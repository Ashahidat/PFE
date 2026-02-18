# atlas/data_quality.py
import datetime
import logging
import json
from typing import List, Dict, Any, Optional

from atlas.client import atlas_post, ATLAS_ENTITY_BULK_URL

logger = logging.getLogger("atlas.dataquality")

def create_data_quality_check(
    dataset_version_guid: str,
    check_type: str,
    column_name: Optional[str],
    status: str,
    error_count: int,
    ratio: str,
    dag_run_id: str,
    examples: Optional[List[Any]] = None
) -> str:
    """
    Crée une entité DataQualityCheck dans Atlas.
    
    1 résultat = 1 entité Atlas
    """
    execution_date = int(datetime.datetime.utcnow().timestamp() * 1000)
    
    # Construction du qualifiedName unique
    if column_name:
        qualified_name = f"{dataset_version_guid}.{check_type}.{column_name}.{dag_run_id}"
        name = f"{check_type} - {column_name}"
    else:
        qualified_name = f"{dataset_version_guid}.{check_type}.dataset.{dag_run_id}"
        name = f"{check_type} - dataset"
    
    # Parser le ratio (format "X/Y")
    try:
        if "/" in ratio:
            num, denom = ratio.split("/")
            ratio_float = float(num) / float(denom) if float(denom) > 0 else 0.0
        else:
            ratio_float = float(ratio)
    except:
        ratio_float = 0.0
    
    payload = {
        "entities": [{
            "typeName": "DataQualityCheck",
            "attributes": {
                "qualifiedName": qualified_name,
                "name": name,
                "checkType": check_type.upper(),
                "columnName": column_name,
                "status": status,
                "errorCount": error_count,
                "ratio": ratio_float,
                "executionDate": execution_date,
                "dagRunId": dag_run_id,
                "examples": json.dumps(examples) if examples else None,
                "datasetVersion": {
                    "typeName": "DataSet",
                    "guid": dataset_version_guid
                }
            },
            "guid": "-200"
        }]
    }
    
    try:
        res = atlas_post(ATLAS_ENTITY_BULK_URL, payload)
        guid = res.json().get("guidAssignments", {}).get("-200")
        logger.info(f"✅ DataQualityCheck créé: {guid} - {name} ({status})")
        return guid
    except Exception as e:
        logger.error(f"❌ Erreur création DataQualityCheck: {e}")
        raise


def create_data_quality_checks_from_json(
    dataset_version_guid: str,
    json_path: str
) -> List[str]:
    """
    Crée toutes les entités DataQualityCheck à partir du JSON généré par Airflow.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    dag_run_id = data["dag_run_id"]
    checks = data["checks"]
    
    guids = []
    for check in checks:
        guid = create_data_quality_check(
            dataset_version_guid=dataset_version_guid,
            check_type=check["rule_type"],
            column_name=check.get("column_name"),
            status=check["status"],
            error_count=check["error_count"],
            ratio=check["ratio"],
            dag_run_id=dag_run_id,
            examples=check.get("examples", [])
        )
        guids.append(guid)
    
    logger.info(f"📊 {len(guids)} checks de qualité créés dans Atlas")
    return guids
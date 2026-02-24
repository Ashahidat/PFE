# atlas/data_quality.py
import datetime
import logging
import json
from typing import List, Dict, Any, Optional

from atlas.client import atlas_post, ATLAS_ENTITY_BULK_URL
from atlas.classifications import add_quality_classification

logger = logging.getLogger("atlas.dataquality")

def create_data_quality_check(
    dataset_version_guid: str,
    column_guid: Optional[str],
    check_type: str,
    column_name: Optional[str],
    status: str,
    error_count: int,
    ratio: str,
    dag_run_id: str,
    examples: Optional[List[Any]] = None
) -> str:
    """
    Crée une entité DataQualityCheck dans Atlas avec :
    - Lien vers la colonne (si fourni)
    - Classification basée sur le statut
    """
    execution_date = int(datetime.datetime.utcnow().timestamp() * 1000)
    
    # Construction du qualifiedName unique
    if column_name:
        qualified_name = f"{dataset_version_guid}.{column_name}.{check_type}.{dag_run_id}"
        name = f"{check_type} - {column_name}"
    else:
        qualified_name = f"{dataset_version_guid}.dataset.{check_type}.{dag_run_id}"
        name = f"{check_type} - dataset"
    
    # Parser le ratio
    try:
        if "/" in ratio:
            num, denom = ratio.split("/")
            ratio_float = float(num) / float(denom) if float(denom) > 0 else 0.0
        else:
            ratio_float = float(ratio)
    except:
        ratio_float = 0.0
    
    # Construction des attributs
    attributes = {
        "qualifiedName": qualified_name,
        "name": name,
        "checkType": check_type.upper(),
        "columnName": column_name,
        "errorCount": error_count,
        "ratio": ratio_float,
        "executionDate": execution_date,
        "dagRunId": dag_run_id,
        "examples": json.dumps(examples, ensure_ascii=False) if examples else None,
        "datasetVersion": {
            "typeName": "DataSet",
            "guid": dataset_version_guid
        }
    }
    
    # Ajout du lien vers la colonne si disponible
    if column_guid:
        attributes["column"] = {
            "typeName": "Column",
            "guid": column_guid
        }
    
    payload = {
        "entities": [{
            "typeName": "DataQualityCheck",
            "attributes": attributes,
            "guid": "-200"
        }]
    }
    
    try:
        # Création de l'entité
        res = atlas_post(ATLAS_ENTITY_BULK_URL, payload)
        guid = res.json().get("guidAssignments", {}).get("-200")
        
        # Ajout de la classification basée sur le statut
        add_quality_classification(guid, status)
        
        # Log enrichi
        if column_guid:
            logger.info(f"✅ DataQualityCheck créé: {guid} - {name} sur colonne {column_name} ({status})")
        else:
            logger.info(f"✅ DataQualityCheck créé: {guid} - {name} au niveau dataset ({status})")
        
        return guid
    except Exception as e:
        logger.error(f"❌ Erreur création DataQualityCheck: {e}")
        raise


def create_data_quality_checks_from_json(
    dataset_version_guid: str,
    column_mapping: Dict[str, str],
    json_path: str
) -> List[str]:
    """
    Crée toutes les entités DataQualityCheck à partir du JSON généré par Airflow.
    Maintenant avec lien vers les colonnes et classifications.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    dag_run_id = data["dag_run_id"]
    checks = data["checks"]
    
    guids = []
    stats = {"avec_colonne": 0, "sans_colonne": 0}
    
    for check in checks:
        # Récupérer le GUID de la colonne si disponible
        column_guid = None
        column_name = check.get("column_name")
        
        if column_name and column_name in column_mapping:
            column_guid = column_mapping[column_name]
            stats["avec_colonne"] += 1
        else:
            stats["sans_colonne"] += 1
        
        guid = create_data_quality_check(
            dataset_version_guid=dataset_version_guid,
            column_guid=column_guid,
            check_type=check["rule_type"],
            column_name=column_name,
            status=check["status"],
            error_count=check["error_count"],
            ratio=check["ratio"],
            dag_run_id=dag_run_id,
            examples=check.get("examples", [])
        )
        guids.append(guid)
    
    logger.info(f"📊 {len(guids)} checks de qualité créés dans Atlas")
    logger.info(f"   - {stats['avec_colonne']} liés à une colonne spécifique")
    logger.info(f"   - {stats['sans_colonne']} au niveau dataset")
    
    return guids
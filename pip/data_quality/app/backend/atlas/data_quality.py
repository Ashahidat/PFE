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
    status: str,  # Peut être "réussi", "échoué", etc.
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
    
    # 🔥 MAPPER LE STATUT FRANÇAIS VERS ANGLAIS POUR LA CLASSIFICATION
    status_for_classification = status.lower()
    if status_for_classification in ["réussi", "réussie", "succès", "success", "pass"]:
        atlas_status = "SUCCESS"
    elif status_for_classification in ["échoué", "échouée", "échec", "failed", "fail"]:
        atlas_status = "FAILED"
    elif status_for_classification in ["avertissement", "warning"]:
        atlas_status = "WARNING"
    else:
        atlas_status = "WARNING"  # Par défaut
    
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
        
        # Ajout de la classification basée sur le statut (version anglaise)
        add_quality_classification(guid, atlas_status)
        
        # Log enrichi (garder le statut français pour la lisibilité)
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
    Supporte les noms de champs en français.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    dag_run_id = data["dag_run_id"]
    checks = data["checks"]
    
    guids = []
    stats = {"avec_colonne": 0, "sans_colonne": 0}
    
    for check in checks:
        # 🔥 MAPPING DES CLÉS FRANÇAISES VERS CE QU'ATLAS ATTEND
        rule_type = check.get("rule_type") or check.get("type de test", "UNKNOWN")
        column_name = check.get("column_name") or check.get("colonne testée")
        status = check.get("status") or check.get("statut", "inconnu")
        error_count = check.get("error_count") or check.get("nombre", 0)
        ratio = check.get("ratio", "0/0")
        examples = check.get("examples") or check.get("exemples", [])
        
        # Récupérer le GUID de la colonne si disponible
        column_guid = None
        
        if column_name and column_name in column_mapping:
            column_guid = column_mapping[column_name]
            stats["avec_colonne"] += 1
        else:
            stats["sans_colonne"] += 1
        
        guid = create_data_quality_check(
            dataset_version_guid=dataset_version_guid,
            column_guid=column_guid,
            check_type=rule_type,
            column_name=column_name,
            status=status,
            error_count=error_count,
            ratio=ratio,
            dag_run_id=dag_run_id,
            examples=examples
        )
        guids.append(guid)
    
    logger.info(f"📊 {len(guids)} checks de qualité créés dans Atlas")
    logger.info(f"   - {stats['avec_colonne']} liés à une colonne spécifique")
    logger.info(f"   - {stats['sans_colonne']} au niveau dataset")
    
    return guids
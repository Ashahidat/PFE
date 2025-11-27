import os
import json
import requests
import sys
sys.path.append("/home/ashahi/PFE/pip/data_quality/utils")
from atlas_entities import get_or_create_dataset, get_or_create_column

ATLAS_URL = "http://localhost:21000/api/atlas/v2"
AUTH = ("admin", "admin")

def publish_quality_results(dag_run_conf, dag_run_id):
    """
    Publie dans Atlas les résultats qualité produits par Airflow,
    gère rechargement du même CSV et garde l'historique via dag_run_id.
    """
    file_path = dag_run_conf.get("file_path")
    if not file_path:
        raise ValueError("❌ Aucun file_path trouvé dans dag_run.conf")

    dataset_name = os.path.basename(file_path)
    dataset_guid = get_or_create_dataset(dataset_name, file_path=file_path, format="csv")

    # Charger les résultats
    results_path = "/home/ashahi/PFE/pip/data_quality/results/validation.json"
    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    entities = []

    for test_type, test_results in results.items():
        if isinstance(test_results, list):
            iterable = test_results
        elif isinstance(test_results, dict):
            iterable = []
            for sub_list in test_results.values():
                if isinstance(sub_list, list):
                    iterable.extend(sub_list)
        else:
            continue

        for test in iterable:
            col_name = test.get("colonne testée", "unknown")
            col_guid = get_or_create_column(col_name, dataset_name)

            # Unique pour chaque run
            quality_qualified_name = f"{dataset_name}.{col_name}@pfe.{dag_run_id}"

            entity = {
                "typeName": "QualityResult",
                "attributes": {
                    "qualifiedName": quality_qualified_name,
                    "test_type": test.get("type de test"),
                    "status": test.get("statut"),
                    "metrics": {
                        "count": str(test.get("nombre", "")),
                        "ratio": str(test.get("ratio", ""))
                    },
                    "examples": test.get("exemples", []),
                    "dag_run_id": dag_run_id
                },
                "relationshipAttributes": {
                    "column": {"guid": col_guid}
                }
            }
            entities.append(entity)

    if entities:
        resp = requests.post(f"{ATLAS_URL}/entity/bulk", json={"entities": entities}, auth=AUTH)
        print(f"Atlas response: {resp.status_code} {resp.text}")

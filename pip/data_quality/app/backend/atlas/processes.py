import time
import logging
from atlas.client import atlas_post, ATLAS_ENTITY_BULK_URL

logger = logging.getLogger("atlas.processes")

def create_import_process(dataset_inputs, dataset_output, operation="CSV_TO_PARQUET", description=None):
    """
    Crée un Process Atlas propre :
    DataSet(s) existants → Process → DataSet final
    """
    if not isinstance(dataset_inputs, list):
        dataset_inputs = [dataset_inputs]

    process_qn = f"process_{dataset_output}_{int(time.time())}"

    payload = {
        "entities": [{
            "typeName": "Process",
            "attributes": {
                "qualifiedName": process_qn,
                "name": f"Process {dataset_output}",
                "description": description or f"Transformation vers {dataset_output}",
                "inputs": [{"guid": guid, "typeName": "DataSet"} for guid in dataset_inputs],
                "outputs": [{"guid": dataset_output, "typeName": "DataSet"}],
                "operation": operation,
                "importDate": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        }]
    }

    logger.info(f"Création du Process Atlas: {payload}")

    res = atlas_post(ATLAS_ENTITY_BULK_URL, payload)
    response_data = res.json()

    process_guid = None
    if "mutatedEntities" in response_data and "CREATE" in response_data["mutatedEntities"]:
        process_guid = response_data["mutatedEntities"]["CREATE"][0]["guid"]

    if not process_guid:
        raise Exception(f"Pas de GUID pour Process: {response_data}")

    logger.info(f"✅ Process créé avec lineage correct: {process_guid}")
    return process_guid

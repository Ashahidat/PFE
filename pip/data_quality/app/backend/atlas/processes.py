import time
import logging
from atlas.client import atlas_post, ATLAS_ENTITY_BULK_URL, atlas_get, ATLAS_SEARCH_URL

logger = logging.getLogger("atlas.processes")

def get_next_process_version(dataset_guid: str) -> int:
    """
    Compte le nombre de Process existants liés à ce dataset
    pour déterminer la prochaine version.
    """
    base_url = ATLAS_SEARCH_URL.split("/search")[0]
    res = atlas_get(f"{base_url}/entity/guid/{dataset_guid}")
    entity = res.json().get("entity", {})

    relations = entity.get("relationshipAttributes", {})
    processes = relations.get("outputs", []) or relations.get("inputs", [])

    return len(processes) + 1


def build_process_name(version: int):
    """
    Nomme simplement le process "reupload version X".
    """
    return f"Reupload version {version}"


def create_import_process(
    dataset_inputs,
    dataset_output_guid,
    operation="Reupload",
    description=None
):
    if not isinstance(dataset_inputs, list):
        dataset_inputs = [dataset_inputs]

    version = get_next_process_version(dataset_output_guid)
    process_name = build_process_name(version)

    payload = {
        "entities": [{
            "typeName": "Process",
            "attributes": {
                "qualifiedName": process_name,
                "name": process_name,
                "description": description or f"{process_name}",
                "inputs": [{"guid": g, "typeName": "DataSet"} for g in dataset_inputs],
                "outputs": [{"guid": dataset_output_guid, "typeName": "DataSet"}],
                "operation": operation,
                "importDate": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        }]
    }

    res = atlas_post(ATLAS_ENTITY_BULK_URL, payload)
    data = res.json()

    guid = data["mutatedEntities"]["CREATE"][0]["guid"]
    logger.info(f"✅ Process créé: {process_name}")
    return guid

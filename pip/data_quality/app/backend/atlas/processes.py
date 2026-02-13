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


def create_import_process(dataset_inputs, dataset_output_guid, operation="Reupload", description=None):
    if not isinstance(dataset_inputs, list):
        dataset_inputs = [dataset_inputs]

    parent_guid = dataset_inputs[0]

    version = get_next_process_version(parent_guid)

    process_qn = f"{parent_guid}_to_{dataset_output_guid}_v{version}"
    process_name = f"Reupload v{version}"

    payload = {
        "entities": [{
            "typeName": "Process",
            "attributes": {
                "qualifiedName": process_qn,
                "name": process_name,
                "description": description or process_name,
                "inputs": [{"guid": parent_guid, "typeName": "DataSet"}],
                "outputs": [{"guid": dataset_output_guid, "typeName": "DataSet"}],
                "operation": operation,
                "importDate": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        }]
    }

    res = atlas_post(ATLAS_ENTITY_BULK_URL, payload)
    data = res.json()

    mutated = data.get("mutatedEntities", {})

    if "CREATE" in mutated and mutated["CREATE"]:
        return mutated["CREATE"][0]["guid"]

    raise Exception(f"Process non créé correctement: {data}")

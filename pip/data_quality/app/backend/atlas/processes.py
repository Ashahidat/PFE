import time
import logging
from atlas.client import atlas_post, ATLAS_ENTITY_BULK_URL, atlas_get, ATLAS_SEARCH_URL
from atlas.versioning import find_latest_version

logger = logging.getLogger("atlas.processes")
logger.setLevel(logging.DEBUG)


def get_next_process_version(parent_guid: str) -> int:
    """
    Détermine le numéro de version pour le prochain process
    lié au dataset parent, en se basant sur la dernière version.
    """
    try:
        # Remonter jusqu'à la dernière version du dataset
        latest_guid = find_latest_version(parent_guid)
        if latest_guid == parent_guid:
            # Pas de version précédente
            return 1

        # Sinon, compter combien de versions existent depuis le parent initial
        base_url = ATLAS_SEARCH_URL.split("/search")[0]
        current_guid = latest_guid
        version_count = 1
        visited = set()
        while True:
            if current_guid in visited:
                break
            visited.add(current_guid)

            res = atlas_get(f"{base_url}/entity/guid/{current_guid}")
            entity = res.json().get("entity", {})
            relationships = entity.get("relationshipAttributes", {})

            prev = relationships.get("previous")
            if not prev:
                break
            current_guid = prev["guid"]
            version_count += 1

        return version_count + 1  # prochaine version
    except Exception as e:
        logger.warning(f"⚠️ get_next_process_version fallback to 1 due to error: {e}")
        return 1


def build_process_name(version: int) -> str:
    """
    Crée le nom du process à partir du numéro de version
    """
    return f"Reupload V{version}"


def create_import_process(dataset_inputs, dataset_output_guid, operation="Reupload", description=None):
    """
    Crée un Process Atlas pour l'import/transformation d'un dataset.
    """
    if not isinstance(dataset_inputs, list):
        dataset_inputs = [dataset_inputs]

    parent_guid = dataset_inputs[0]

    # 🔹 Récupérer le prochain numéro de version
    version = get_next_process_version(parent_guid)
    process_name = build_process_name(version)
    process_qn = f"{parent_guid}_to_{dataset_output_guid}_v{version}"

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
        logger.info(f"✅ Process créé: {process_name}")
        return mutated["CREATE"][0]["guid"]

    raise Exception(f"Process non créé correctement: {data}")

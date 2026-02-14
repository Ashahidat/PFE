import time
import logging
from atlas.client import atlas_post, ATLAS_ENTITY_BULK_URL, atlas_get, ATLAS_SEARCH_URL

logger = logging.getLogger("atlas.processes")

def count_versions_in_chain(dataset_guid: str) -> int:
    """
    Parcourt la chaîne de versioning pour compter combien de datasets existent
    """
    if not dataset_guid:
        return 0
        
    base_url = ATLAS_SEARCH_URL.split("/search")[0]
    current = dataset_guid
    count = 1
    visited = set()  # Pour éviter les cycles
    
    # Remonter jusqu'à la première version
    while True:
        if current in visited:
            logger.warning(f"Cycle détecté dans versioning: {current}")
            break
        visited.add(current)
        
        try:
            res = atlas_get(f"{base_url}/entity/guid/{current}")
            entity = res.json().get("entity", {})
            relationships = entity.get("relationshipAttributes", {})
            
            # Chercher le parent (previous)
            previous = relationships.get("previous")
            if not previous:
                break
                
            current = previous.get("guid")
            if not current:
                break
                
            count += 1
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de l'entité {current}: {e}")
            break
    
    return count

def get_next_process_version(parent_guid: str) -> int:
    """
    La prochaine version = nombre de datasets existants + 1
    Si pas de parent (premier dataset), retourne 1
    """
    if not parent_guid:
        return 1
        
    versions_count = count_versions_in_chain(parent_guid)
    return versions_count + 1


def create_import_process(dataset_inputs, dataset_output_guid, operation="Reupload", description=None):
    if not isinstance(dataset_inputs, list):
        dataset_inputs = [dataset_inputs]

    parent_guid = dataset_inputs[0] if dataset_inputs else None

    version = get_next_process_version(parent_guid)

    process_qn = f"{parent_guid}_to_{dataset_output_guid}_v{version}" if parent_guid else f"root_to_{dataset_output_guid}_v{version}"
    process_name = f"Reupload v{version}"

    payload = {
        "entities": [{
            "typeName": "Process",
            "attributes": {
                "qualifiedName": process_qn,
                "name": process_name,
                "description": description or process_name,
                "inputs": [{"guid": parent_guid, "typeName": "DataSet"}] if parent_guid else [],
                "outputs": [{"guid": dataset_output_guid, "typeName": "DataSet"}],
                "operation": operation,
                "importDate": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        }]
    }

    logger.info(f"Création du Process version {version} : {process_name}")
    
    res = atlas_post(ATLAS_ENTITY_BULK_URL, payload)
    data = res.json()

    mutated = data.get("mutatedEntities", {})

    if "CREATE" in mutated and mutated["CREATE"]:
        process_guid = mutated["CREATE"][0]["guid"]
        logger.info(f"✅ Process créé avec GUID: {process_guid}, version: {version}")
        return process_guid

    raise Exception(f"Process non créé correctement: {data}")
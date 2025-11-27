import logging
import json
from atlas.client import atlas_get, ATLAS_SEARCH_URL
from atlas.client import atlas_post, atlas_put, ATLAS_TYPEDEF_URL, ATLAS_RELATIONSHIP_URL, ATLAS_ENTITY_BULK_URL
from atlas.signatures import calculate_dataset_signature, compute_similarity_score

logger = logging.getLogger("atlas.datasets")
logger.setLevel(logging.DEBUG)

def create_dataset(hash_value, original_name, file_path, parent_qualified_name, df, signature=None):
    signature_json = json.dumps(signature) if signature else None

    payload = {
        "entities": [{
            "typeName": "DataSet",
            "attributes": {
                "qualifiedName": hash_value,
                "name": original_name,
                "description": f"Dataset importé depuis {file_path}",
                "versionComment": f"Version dérivée de {parent_qualified_name}" if parent_qualified_name else "Version initiale",
                "signature": signature_json,
                "columnsCount": len(df.columns),
                "columnsList": list(df.columns)
            },
            "guid": "-100"
        }]
    }

    # ✅ CORRECTION : utiliser l’URL des ENTITÉS
    res = atlas_post(ATLAS_ENTITY_BULK_URL, payload)

    return res.json().get("guidAssignments", {}).get("-100")

def link_versioning(parent_guid, child_guid):
    relationship_payload = {
        "typeName": "dataset_versioning",
        "end1": {"guid": child_guid, "typeName": "DataSet"},
        "end2": {"guid": parent_guid, "typeName": "DataSet"},
        "attributes": {"versionDate": "now()"}
    }
    # ✅ CORRECTION : ajouter l'URL
    res = atlas_post(ATLAS_RELATIONSHIP_URL, relationship_payload)
    return res.json()
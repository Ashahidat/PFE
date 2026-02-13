from atlas.client import atlas_get, ATLAS_SEARCH_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("atlas.versioning")

def find_latest_version(start_guid: str) -> str:
    """
    Remonte la chaîne dataset_versioning pour trouver la dernière version
    """
    base_url = ATLAS_SEARCH_URL.split("/search")[0]
    current_guid = start_guid
    visited = set()  # Éviter les cycles
    
    logger = logging.getLogger("atlas.versioning")

    while True:
        if current_guid in visited:
            logger.warning(f"⚠️ Cycle détecté dans versioning: {current_guid}")
            return current_guid
        visited.add(current_guid)
        
        # Requête Atlas pour récupérer l'entité actuelle
        res = atlas_get(f"{base_url}/entity/guid/{current_guid}")
        entity = res.json().get("entity", {})
        relationships = entity.get("relationshipAttributes", {})

        # Vérifier si un dataset "next" existe
        next_ds = relationships.get("next")
        if not next_ds:
            return current_guid  # dernière version trouvée

        # Passer au GUID suivant
        current_guid = next_ds["guid"]


def find_column_lineage(column_guid: str):
    """
    Trouve toute la lignée d'une colonne via logicalColumnId
    """
    from atlas.columns import trace_column_lineage
    return trace_column_lineage(column_guid)
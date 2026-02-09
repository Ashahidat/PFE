from atlas.client import atlas_get, ATLAS_SEARCH_URL

def find_latest_version(start_guid: str) -> str:
    """
    Remonte la chaîne dataset_versioning pour trouver la dernière version
    """
    base_url = ATLAS_SEARCH_URL.split("/search")[0]  # ex: http://localhost:21000/api/atlas/v2
    current_guid = start_guid

    while True:
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

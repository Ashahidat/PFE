from atlas.client import atlas_get, ATLAS_SEARCH_URL

def find_latest_version(start_guid: str):
    """
    Remonte la chaîne dataset_versioning pour trouver la dernière version
    """
    base_url = ATLAS_SEARCH_URL.split("/search")[0]
    current_guid = start_guid

    while True:
        res = atlas_get(f"{base_url}/entity/guid/{current_guid}").json()
        entity = res.get("entity", {})
        rels = entity.get("relationshipAttributes", {})

        next_ds = rels.get("next")
        if not next_ds:
            return current_guid  # ✅ dernière version

        current_guid = next_ds["guid"]

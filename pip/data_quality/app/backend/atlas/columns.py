from .client import atlas_post, ATLAS_ENTITY_BULK_URL

def create_columns(df, dataset_guid, dataset_qualified_name):
    """
    Crée les colonnes dans Atlas et retourne un dictionnaire {nom_colonne: guid}
    """
    entities = []
    temp_to_name = {}  # Mapping temporaire {temp_guid: column_name}
    
    for idx, (col_name, dtype) in enumerate(zip(df.columns, df.dtypes)):
        temp_guid = f"-col-{idx}"
        entities.append({
            "typeName": "Column",
            "attributes": {
                "name": col_name,
                "qualifiedName": f"{dataset_qualified_name}.{col_name}",
                "type": str(dtype),
                "dataset": {"typeName": "DataSet", "guid": dataset_guid}
            },
            "guid": temp_guid
        })
        temp_to_name[temp_guid] = col_name  # Sauvegarder le mapping

    if not entities:
        return {}

    # Envoyer à Atlas
    res = atlas_post(ATLAS_ENTITY_BULK_URL, {"entities": entities})
    assignments = res.json().get("guidAssignments", {})

    # Construire le dictionnaire final {nom_colonne: guid_atlas}
    column_mapping = {}
    for temp_guid, atlas_guid in assignments.items():
        if temp_guid in temp_to_name:
            column_name = temp_to_name[temp_guid]
            column_mapping[column_name] = atlas_guid
    
    return column_mapping  # Format: {"email": "abc123", "phone": "def456"}
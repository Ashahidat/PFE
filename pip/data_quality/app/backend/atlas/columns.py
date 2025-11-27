from .client import atlas_post, ATLAS_ENTITY_BULK_URL

def create_columns(df, dataset_guid, dataset_qualified_name):
    entities = []
    for idx, (col_name, dtype) in enumerate(zip(df.columns, df.dtypes)):
        entities.append({
            "typeName": "Column",
            "attributes": {
                "name": col_name,
                "qualifiedName": f"{dataset_qualified_name}.{col_name}",
                "type": str(dtype),
                "dataset": {"typeName": "DataSet", "guid": dataset_guid}
            },
            "guid": f"-col-{idx}"
        })

    if not entities:
        return []

    res = atlas_post(ATLAS_ENTITY_BULK_URL, {"entities": entities})
    assignments = res.json().get("guidAssignments", {})

    return [assignments[g] for g in assignments if g.startswith("-col-")]

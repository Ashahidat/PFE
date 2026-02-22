import logging
import time
import json
from atlas.client import atlas_get, ATLAS_SEARCH_URL
from atlas.client import atlas_post, ATLAS_TYPEDEF_URL, ATLAS_RELATIONSHIP_URL, ATLAS_ENTITY_BULK_URL
from atlas.signatures import calculate_dataset_signature, compute_similarity_score
from urllib.parse import quote

logger = logging.getLogger("atlas.datasets")
logger.setLevel(logging.DEBUG)


def create_dataset(
    hash_value,
    original_name,
    file_path,
    parent_qualified_name,
    df,
    signature=None,
    force_unique=False,
    owner_employee_id=None,
    project_id=None,
    description=None  # ✅ NOUVEAU PARAMÈTRE
):
    """
    Crée un DataSet dans Atlas. 
    Si un dataset avec le même qualifiedName existe → renvoie son GUID et existed=True.
    Sinon → crée le dataset et existed=False.
    """

    signature_json = json.dumps(signature) if signature else None

    # Le qualifiedName inclut le projet pour isoler les datasets entre projets
    qn = f"{project_id}_{hash_value}" if project_id else hash_value
    if force_unique:
        qn = f"{qn}_{int(time.time())}"

    # ---------------------------------------------------------------------
    # 0) Vérifier si un dataset existe déjà (via qualifiedName)
    # ---------------------------------------------------------------------
    try:
        base_url = ATLAS_SEARCH_URL.split("/search")[0]
        entity_url = f"{base_url}/entity/uniqueAttribute/type/DataSet/attribute/qualifiedName"
        encoded_qn = quote(qn, safe='')
        res = atlas_get(f"{entity_url}?value={encoded_qn}")

        # Si on arrive ici, l'entité existe
        existing_guid = res.json()["entity"]["guid"]
        logger.info(f"create_dataset: dataset already exists -> {existing_guid}")
        return existing_guid, True

    except Exception as e:
        # Si c'est une 404, le dataset n'existe pas -> on continue pour créer
        if "404" in str(e):
            logger.debug("create_dataset: dataset does not exist, creating...")
        else:
            # Autre erreur, on log mais on tente la création quand même
            logger.warning(f"create_dataset: unexpected error checking existence: {e}")

    # ---------------------------------------------------------------------
    # 1) Création du dataset avec description personnalisée
    # ---------------------------------------------------------------------

    # ✅ Utiliser la description personnalisée si fournie
    description_text = description if description else f"Dataset importé depuis {file_path}"

    payload = {
        "entities": [{
            "typeName": "DataSet",
            "attributes": {
                "qualifiedName": qn,
                "name": original_name,
                "description": description_text,  # ✅ DESCRIPTION DYNAMIQUE
                "versionComment": (
                    f"Version dérivée de {parent_qualified_name}"
                    if parent_qualified_name
                    else "Version initiale"
                ),
                "signature": signature_json,
                "columnsCount": len(df.columns),
                "columnsList": list(df.columns),
                "owner": owner_employee_id,
                "project": project_id
            },
            "guid": "-100"
        }]
    }

    try:
        res = atlas_post(ATLAS_ENTITY_BULK_URL, payload)

        # Debug
        try:
            logger.debug(f"create_dataset: atlas response json: {res.json()}")
        except:
            logger.debug(f"create_dataset: atlas response text: {res.text}")

        guid = res.json().get("guidAssignments", {}).get("-100")
        if not guid:
            logger.error(f"create_dataset: no guidAssignments returned, response: {res.text}")
            raise Exception("Atlas did not return GUID.")

        # 👉 Dataset créé maintenant
        return guid, False

    except Exception as e:
        logger.error(f"create_dataset: error creating dataset: {e}")
        raise

def link_versioning(parent_guid, child_guid):
    """
    Crée une relation de versioning entre parent et child.
    Ne crée rien si les deux GUID sont égaux ou manquants.
    """

    if not parent_guid or not child_guid:
        logger.warning("link_versioning: parent_guid or child_guid missing, skipping link.")
        return None

    if parent_guid == child_guid:
        logger.warning(f"link_versioning: parent_guid == child_guid ({parent_guid}), skipping to avoid self-link.")
        return None

    relationship_payload = {
        "typeName": "dataset_versioning",
        "end1": {"guid": child_guid, "typeName": "DataSet"},
        "end2": {"guid": parent_guid, "typeName": "DataSet"},
        "attributes": {"versionDate": "now()"}
    }

    try:
        res = atlas_post(ATLAS_RELATIONSHIP_URL, relationship_payload)
        try:
            res_json = res.json()
            logger.debug(f"link_versioning: atlas response json: {res_json}")
            return res_json
        except Exception:
            logger.debug(f"link_versioning: atlas response text: {res.text}")
            return {"raw": res.text}
    except Exception as e:
        logger.error(f"link_versioning: failed to create relationship: {e}")
        raise
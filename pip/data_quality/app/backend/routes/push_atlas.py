from fastapi import APIRouter, HTTPException
import logging
import sys
sys.path.append("/home/ashahi/PFE/pip/data_quality/app/backend")

from session import session_data
from atlas.client import atlas_post, atlas_put, ATLAS_TYPEDEF_URL, ATLAS_RELATIONSHIP_URL
from atlas.typedefs import typedefs_payload
from atlas.datasets import create_dataset, link_versioning
from atlas.columns import create_columns
from atlas.signatures import find_smart_parent, calculate_dataset_signature

router = APIRouter()
logger = logging.getLogger("push-atlas")
logger.setLevel(logging.DEBUG)

@router.post("/push-atlas")
def push_atlas():
    try:
        # --- 0️⃣ Vérifier session_data ---
        if "df" not in session_data:
            raise HTTPException(status_code=400, detail="Aucun dataset chargé en session.")
        
        df = session_data["df"]
        hash_value = session_data["hash"]
        file_path = session_data["file_path"]
        original_name = session_data["original_name"]

        # --- 1️⃣ Étendre DataSet natif avec PUT ---
        try:
            logger.debug("Étendre DataSet natif avec PUT")
            atlas_put(ATLAS_TYPEDEF_URL, {"entityDefs": [typedefs_payload["entityDefs"][0]]})
        except Exception as e:
            logger.error(f"Erreur PUT DataSet: {e}")
            raise

        # --- 2️⃣ Créer Column et relations si non existants ---
        try:
            logger.debug("Créer Column si non existant")
            atlas_post(ATLAS_TYPEDEF_URL, {"entityDefs": [typedefs_payload["entityDefs"][1]]})
        except Exception as e:
            if "409" not in str(e):
                raise
            logger.debug("Column existe déjà, ignoré")

        for rel_def in typedefs_payload["relationshipDefs"]:
            try:
                logger.debug(f"Créer relation {rel_def['name']} si non existante")
                atlas_post(ATLAS_TYPEDEF_URL, {"relationshipDefs": [rel_def]})
            except Exception as e:
                if "409" not in str(e):
                    raise
                logger.debug(f"Relation {rel_def['name']} existe déjà, ignorée")

        # --- 3️⃣ Calculer la signature Big Data Spark ---
        signature = calculate_dataset_signature(df, original_name)

        # --- 4️⃣ Recherche intelligente du parent ---
        logger.info(f"Recherche parent pour dataset: {original_name}")
        parent_guid, parent_qn = find_smart_parent(df, original_name)

        # --- 5️⃣ Créer dataset avec signature Spark ---
        dataset_guid = create_dataset(
            hash_value, original_name, file_path, parent_qn, df, signature
        )

        # --- 6️⃣ Versioning si parent trouvé ---
        if parent_guid:
            link_versioning(parent_guid, dataset_guid)

        # --- 7️⃣ Création colonnes ---
        col_guids = create_columns(df, dataset_guid, hash_value)

        logger.info(f"Dataset créé: {dataset_guid}, Parent: {parent_guid}, Colonnes: {len(col_guids)}")

        return {
            "message": f"Dataset + {len(col_guids)} colonnes créés.",
            "dataset_guid": dataset_guid,
            "parent_guid": parent_guid,
            "column_guids": col_guids
        }

    except Exception as e:
        logger.error(f"Erreur push-atlas: {e}")
        raise HTTPException(status_code=500, detail=str(e))

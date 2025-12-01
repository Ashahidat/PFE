from fastapi import APIRouter, HTTPException
import logging
import os
import sys
sys.path.append("/home/ashahi/PFE/pip/data_quality/app/backend")

from session import session_data
from atlas.client import atlas_post, atlas_put, ATLAS_TYPEDEF_URL, ATLAS_RELATIONSHIP_URL
from atlas.typedefs import typedefs_payload
from atlas.datasets import create_dataset, link_versioning
from atlas.columns import create_columns
from atlas.signatures import find_smart_parent, calculate_dataset_signature
from jwt_dependencies import get_current_user
from fastapi import Request, HTTPException, Depends

router = APIRouter()
logger = logging.getLogger("push-atlas")
logger.setLevel(logging.DEBUG)

@router.post("/push-atlas")
def push_atlas(user=Depends(get_current_user)):
    file_path = None   # <-- IMPORTANT : on initialise AVANT tout

    try:
        # --- 0️⃣ Vérifier session_data ---
        if "df" not in session_data:
            raise HTTPException(status_code=400, detail="Aucun dataset chargé en session.")
        
        df = session_data["df"]
        hash_value = session_data["hash"]
        file_path = session_data["file_path"]     # <-- défini ici
        original_name = session_data["original_name"]

        # --- 1️⃣ Étendre DataSet natif ---
        try:
            atlas_put(ATLAS_TYPEDEF_URL, {"entityDefs": [typedefs_payload["entityDefs"][0]]})
        except Exception as e:
            raise

        # --- 2️⃣ Column + relations ---
        try:
            atlas_post(ATLAS_TYPEDEF_URL, {"entityDefs": [typedefs_payload["entityDefs"][1]]})
        except Exception as e:
            if "409" not in str(e):
                raise

        for rel_def in typedefs_payload["relationshipDefs"]:
            try:
                atlas_post(ATLAS_TYPEDEF_URL, {"relationshipDefs": [rel_def]})
            except Exception as e:
                if "409" not in str(e):
                    raise

        # --- 3️⃣ Signature ---
        signature = calculate_dataset_signature(df, original_name)

        # --- 4️⃣ Parent ---
        parent_guid, parent_qn = find_smart_parent(df, original_name)

        # --- 5️⃣ Créer dataset ---
        dataset_guid = create_dataset(
            hash_value, original_name, file_path, parent_qn, df, signature
        )

        # --- 6️⃣ Versioning ---
        if parent_guid:
            link_versioning(parent_guid, dataset_guid)

        # --- 7️⃣ Colonnes ---
        col_guids = create_columns(df, dataset_guid, hash_value)

        return {
            "message": f"Dataset + {len(col_guids)} colonnes créés.",
            "dataset_guid": dataset_guid,
            "parent_guid": parent_guid,
            "column_guids": col_guids
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        TMP_DIR = "/home/ashahi/PFE/pip/data_quality/tmp"

        try:
            for f in os.listdir(TMP_DIR):
                full = os.path.join(TMP_DIR, f)
                if os.path.isfile(full):
                    os.remove(full)
                    logger.info(f"🗑️ Fichier TMP supprimé : {full}")
        except Exception as err:
            logger.error(f"Impossible de nettoyer TMP : {err}")


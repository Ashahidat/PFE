from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import logging
import os

from config import spark
from db.connexion_db import get_db
from db.datasets import Dataset
from atlas.client import atlas_post, atlas_put, ATLAS_TYPEDEF_URL
from atlas.typedefs import typedefs_payload
from atlas.datasets import create_dataset, link_versioning
from atlas.columns import create_columns
from atlas.signatures import find_smart_parent, calculate_dataset_signature
from jwt_dependencies import get_current_user

router = APIRouter()
logger = logging.getLogger("push-atlas")
logger.setLevel(logging.DEBUG)

TMP_DIR = "/home/ashahi/PFE/pip/data_quality/tmp"
os.makedirs(TMP_DIR, exist_ok=True)


@router.post("/push-atlas/{dataset_id}")
def push_atlas(dataset_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        # 1️⃣ Récupérer le dataset depuis PostgreSQL
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset introuvable")

        file_path = dataset.file_path
        hash_value = dataset.hash
        original_name = dataset.name

        # 2️⃣ Lire le CSV avec Spark
        df = spark.read.option("header", True).option("inferSchema", True).csv(file_path)

        # 3️⃣ Étendre DataSet natif + Colonnes + Relations
        try:
            atlas_put(ATLAS_TYPEDEF_URL, {"entityDefs": [typedefs_payload["entityDefs"][0]]})
            atlas_post(ATLAS_TYPEDEF_URL, {"entityDefs": [typedefs_payload["entityDefs"][1]]})
            for rel_def in typedefs_payload["relationshipDefs"]:
                try:
                    atlas_post(ATLAS_TYPEDEF_URL, {"relationshipDefs": [rel_def]})
                except Exception as e:
                    if "409" not in str(e):
                        raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur extension Atlas : {e}")

        # 4️⃣ Signature Atlas (utilise df)
        signature = calculate_dataset_signature(df, original_name)

        # 5️⃣ Parent
        parent_guid, parent_qn = find_smart_parent(df, original_name)

        # 6️⃣ Créer dataset dans Atlas
        dataset_guid, existed = create_dataset(
            hash_value,
            original_name,
            file_path,
            parent_qn,
            df,
            signature
        )

        # 7️⃣ Versioning
        if parent_guid and parent_guid != dataset_guid:
            link_versioning(parent_guid, dataset_guid)
        else:
            logger.warning(f"[push_atlas] Skipping versioning. parent_guid={parent_guid}, dataset_guid={dataset_guid}")

        # 8️⃣ Colonnes
        col_guids = create_columns(df, dataset_guid, hash_value)

        # 9️⃣ Message user-friendly
        message = "Ce dataset existe déjà dans Atlas." if existed else "Dataset ajouté à Atlas avec succès !"

        return {
            "message": message,
            "dataset_guid": dataset_guid,
            "parent_guid": parent_guid,
            "column_guids": col_guids
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # Nettoyage TMP si nécessaire
        try:
            for f in os.listdir(TMP_DIR):
                full = os.path.join(TMP_DIR, f)
                if os.path.isfile(full):
                    os.remove(full)
                    logger.info(f"🗑️ Fichier TMP supprimé : {full}")
        except Exception as err:
            logger.error(f"Impossible de nettoyer TMP : {err}")

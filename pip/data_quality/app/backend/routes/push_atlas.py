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
from atlas.signatures import persist_signature_to_db



router = APIRouter()
logger = logging.getLogger("push-atlas")
logger.setLevel(logging.DEBUG)

TMP_DIR = "/home/ashahi/PFE/pip/data_quality/tmp"
os.makedirs(TMP_DIR, exist_ok=True)



@router.post("/push-atlas/{dataset_id}")
def push_atlas(dataset_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    try:
        # 1️⃣ Récupérer dataset
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset introuvable")

        file_path = dataset.file_path   # ⚠️ Parquet maintenant
        hash_value = dataset.hash
        original_name = dataset.name

        # 2️⃣ Lire le PARQUET
        df = spark.read.parquet(file_path)

        # 3️⃣ Déployer typedefs Atlas (ignorer 409)
        for idx, entityDef in enumerate(typedefs_payload["entityDefs"]):
            try:
                if idx == 0:
                    atlas_put(ATLAS_TYPEDEF_URL, {"entityDefs": [entityDef]})
                else:
                    atlas_post(ATLAS_TYPEDEF_URL, {"entityDefs": [entityDef]})
            except Exception as e:
                if "409" in str(e):
                    logger.info(f"Typedef déjà existant, on ignore: {entityDef['name']}")
                else:
                    raise

        for rel_def in typedefs_payload["relationshipDefs"]:
            try:
                atlas_post(ATLAS_TYPEDEF_URL, {"relationshipDefs": [rel_def]})
            except Exception as e:
                if "409" not in str(e):
                    raise

        # 4️⃣ Signature (sur df Parquet)
        signature = calculate_dataset_signature(df, original_name)
        persist_signature_to_db(db, dataset.id, signature)

        # 5️⃣ Parent intelligent
        parent_guid, parent_qn = find_smart_parent(df, original_name)

        # 6️⃣ Créer dataset Atlas
        dataset_guid, existed = create_dataset(
            hash_value,
            original_name,
            file_path,
            parent_qn,
            df,
            signature,
            owner_employee_id=dataset.owner_employee_id
        )


        dataset.atlas_guid = dataset_guid
        db.commit()

        # 7️⃣ Versioning
        if parent_guid and parent_guid != dataset_guid:
            link_versioning(parent_guid, dataset_guid)

        # 8️⃣ Colonnes → uniquement si dataset nouveau
        if not existed:
            col_guids = create_columns(df, dataset_guid, hash_value)
        else:
            col_guids = []

        message = "Ce dataset existe déjà dans Atlas." if existed else "Dataset ajouté à Atlas avec succès !"

        return {
            "message": message,
            "dataset_guid": dataset_guid,
            "parent_guid": parent_guid,
            "column_guids": col_guids,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Nettoyage TMP
        try:
            for f in os.listdir(TMP_DIR):
                full = os.path.join(TMP_DIR, f)
                if os.path.isfile(full):
                    os.remove(full)
        except:
            pass

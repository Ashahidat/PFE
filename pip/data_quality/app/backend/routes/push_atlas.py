from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
import logging
import os
import time

from config import spark
from db.connexion_db import get_db
from db.datasets import Dataset
from atlas.client import atlas_post, atlas_put, atlas_get, ATLAS_TYPEDEF_URL, ATLAS_SEARCH_URL
from atlas.typedefs import typedefs_payload
from atlas.datasets import create_dataset, link_versioning
from atlas.columns import create_columns
from atlas.signatures import find_smart_parent, calculate_dataset_signature, persist_signature_to_db
from atlas.processes import create_import_process
from atlas.versioning import find_latest_version
from jwt_dependencies import get_current_user

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

        file_path = dataset.file_path
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

        # Déployer classifications
        for class_def in typedefs_payload["classificationDefs"]:
            try:
                atlas_post(ATLAS_TYPEDEF_URL, {"classificationDefs": [class_def]})
                logger.info(f"✅ Classification créée: {class_def['name']}")
            except Exception as e:
                if "409" in str(e):
                    logger.info(f"Classification déjà existante: {class_def['name']}")
                else:
                    raise

        # 4️⃣ Calculer la signature du dataset
        signature = calculate_dataset_signature(df, original_name)
        persist_signature_to_db(db, dataset.id, signature)

        # 5️⃣ Parent intelligent pour versioning
        parent_guid = None
        parent_qn = None
        base_url = ATLAS_SEARCH_URL.split("/search")[0]  # -> http://localhost:21000/api/atlas/v2

        if dataset.atlas_guid:
            parent_guid = find_latest_version(dataset.atlas_guid)
            res = atlas_get(f"{base_url}/entity/guid/{parent_guid}")
            parent_qn = res.json()["entity"]["attributes"]["qualifiedName"]

        if not parent_guid:
            parent_guid, parent_qn = find_smart_parent(df, original_name)

        # 6️⃣ Créer le DataSet Atlas
        dataset_guid, dataset_existed = create_dataset(
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

        # 7️⃣ Créer Process seulement si version précédente
        process_guid = None
        if parent_guid and parent_guid != dataset_guid:
            process_guid = create_import_process(
                dataset_inputs=parent_guid,
                dataset_output_guid=dataset_guid,
                operation="TRANSFORMATION",
                description=f"Version dérivée de {parent_qn}"
            )
            link_versioning(parent_guid, dataset_guid)

        # 8️⃣ Colonnes → toujours créer/récupérer
        column_guids = create_columns(df, dataset_guid, hash_value)

        message = "Ce dataset existe déjà dans Atlas." if dataset_existed else "Dataset ajouté à Atlas avec succès !"

        return {
            "message": message,
            "dataset_guid": dataset_guid,
            "process_guid": process_guid,
            "parent_guid": parent_guid,
            "column_guids": column_guids,
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

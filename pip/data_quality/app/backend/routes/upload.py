import sys
from pathlib import Path

# Ajouter la racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import os
import uuid
import datetime
import hashlib

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from sqlalchemy.orm import Session

from settings.config_paths import TMP_DIR
from config import spark
from jwt_dependencies import get_current_user
from db.connexion_db import get_db
from db.datasets import Dataset
from db.projects import Project  
from core.permissions import can_upload_to_project
import logging 

logger = logging.getLogger("upload")
logger.setLevel(logging.DEBUG)

router = APIRouter()

# --- Cache simple pour les DataFrame Spark ---
spark_cache = {}  # clé = dataset_id, valeur = df Spark


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    project_id: str = Form(...),  
    description: str = Form(None),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    print(f"📄 Fichier reçu : {file.filename}")
    print(f"📁 Projet ID : {project_id}")
    print(f"📝 Description : {description}")
    print(f"👤 Utilisateur : {user['sub']} (role: {user['role']}, department: {user['department']})")

    # 1️⃣ Vérifier que le projet existe
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(
            status_code=404,
            detail="Projet introuvable"
        )

    # 2️⃣ 🔐 Vérifier les droits
    if not can_upload_to_project(user, project, db):
        logger.warning(
            f"⛔ Utilisateur {user['sub']} n'a pas le droit d'uploader dans le projet {project_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas les droits pour uploader dans ce projet"
        )

    logger.info(
        f"✅ Utilisateur {user['sub']} autorisé à uploader dans {project.name}"
    )

    # 3️⃣ Sauvegarde temporaire CSV
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    csv_path = TMP_DIR / f"{file.filename}_{timestamp}.csv"

    with open(csv_path, "wb") as f:
        f.write(await file.read())

    # 4️⃣ Calcul du hash SHA256
    h = hashlib.sha256()
    with open(csv_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    hash_value = h.hexdigest()

    # 5️⃣ Lecture CSV → Parquet via Spark
    df = spark.read.option("header", True).option("inferSchema", True).csv(str(csv_path))

    parquet_path = str(csv_path).replace(".csv", ".parquet")
    df.write.mode("overwrite").parquet(parquet_path)

    columns_list = df.columns
    del df

    # 6️⃣ Suppression CSV temporaire
    try:
        csv_path.unlink()  # équivalent à os.remove
        print(f"🗑️ CSV supprimé : {csv_path}")
    except Exception as e:
        print("Erreur suppression CSV :", e)

    # 7️⃣ Enregistrement PostgreSQL
    dataset_id = str(uuid.uuid4())

    db_dataset = Dataset(
        id=dataset_id,
        name=file.filename,
        file_path=parquet_path,
        hash=hash_value,
        columns_list=columns_list,
        owner_employee_id=user["sub"],
        atlas_guid=None,
        project_id=project_id,
        description=description
    )

    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)

    print("✅ Parquet créé et métadonnées enregistrées")

    return {
        "message": "Dataset chargé (converti en Parquet)",
        "columns": columns_list,
        "hash": hash_value,
        "dataset_id": dataset_id,
        "project_id": project_id,
        "description": description
    }


@router.get("/preview/{dataset_id}")
def preview(
    dataset_id: str,
    n: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable ou non autorisé")

    if dataset_id in spark_cache:
        df = spark_cache[dataset_id]
    else:
        df = spark.read.parquet(dataset.file_path)
        spark_cache[dataset_id] = df

    preview_data = df.limit(n).collect()
    preview_list = [row.asDict() for row in preview_data]

    return preview_list


@router.get("/get-columns/{dataset_id}")
def get_columns(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.owner_employee_id == user["sub"]
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable ou non autorisé")

    return {"columns": dataset.columns_list}
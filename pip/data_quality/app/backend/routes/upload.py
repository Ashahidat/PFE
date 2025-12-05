import os
import uuid
import datetime
import hashlib
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from config import spark
from jwt_dependencies import get_current_user
from db.crud_datasets import create_dataset
from db.connexion_db import get_db
from db.datasets import Dataset

# --- Dossier temporaire ---
TMP_DIR = "/home/ashahi/PFE/pip/data_quality/tmp"
os.makedirs(TMP_DIR, exist_ok=True)

router = APIRouter()
# --- Cache simple pour les DataFrame Spark ---
spark_cache = {}  # clé = dataset_id, valeur = df Spark

# ================= Upload CSV =================
@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    print(f"📄 Fichier reçu : {file.filename}")

    # 1️⃣ Sauvegarde temporaire avec horodatage pour éviter les collisions
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    tmp_file_path = os.path.join(TMP_DIR, f"{file.filename}_{timestamp}.csv")
    with open(tmp_file_path, "wb") as f:
        f.write(await file.read())

    # 2️⃣ Calcul du hash SHA256
    h = hashlib.sha256()
    with open(tmp_file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    hash_value = h.hexdigest()

    # 3️⃣ Lecture CSV via Spark pour obtenir les colonnes
    try:
        df = spark.read.option("header", True).option("inferSchema", True).csv(tmp_file_path)
        columns_list = df.columns
    finally:
        del df  # libération mémoire

    # 4️⃣ Stockage des métadonnées dans PostgreSQL
    dataset_id = str(uuid.uuid4())
    db_dataset = Dataset(
        id=dataset_id,
        name=file.filename,
        file_path=tmp_file_path,
        hash=hash_value,
        columns_list=columns_list
    )
    db.add(db_dataset)
    db.commit()
    db.refresh(db_dataset)

    print("✅ Fichier uploadé et métadonnées enregistrées en DB")
    return {
        "message": "Fichier chargé",
        "columns": columns_list,
        "hash": hash_value,
        "dataset_id": dataset_id
    }


# ================= Aperçu dataset =================
@router.get("/preview/{dataset_id}")
def preview(
    dataset_id: str,
    n: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    # Vérifier si le DataFrame est déjà en cache
    if dataset_id in spark_cache:
        df = spark_cache[dataset_id]
    else:
        df = spark.read.option("header", True).option("inferSchema", True).csv(dataset.file_path)
        spark_cache[dataset_id] = df  # mettre en cache pour les prochaines requêtes

    preview_data = df.limit(n).collect()  # récupérer n lignes
    preview_list = [row.asDict() for row in preview_data]  # transformer Row -> dict

    return preview_list

# ================= Obtenir les colonnes =================
@router.get("/get-columns/{dataset_id}")
def get_columns(
    dataset_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset introuvable")

    return {"columns": dataset.columns_list}

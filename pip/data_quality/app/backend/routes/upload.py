import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from config import spark
from session import session_data
import datetime
import hashlib

TMP_DIR = "/home/ashahi/PFE/pip/data_quality/tmp"
os.makedirs(TMP_DIR, exist_ok=True)

router = APIRouter()

# 📤 Upload CSV
@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    tmp_file_path = os.path.join(TMP_DIR, f"{file.filename}_{timestamp}.csv")

    with open(tmp_file_path, "wb") as f:
        f.write(await file.read())

    # Calcul du hash
    h = hashlib.sha256()
    with open(tmp_file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    hash_value = h.hexdigest()

    try:
        df = spark.read.option("header", True).option("inferSchema", True).csv(tmp_file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur lecture Spark: {str(e)}")

    # Stockage dans session
    session_data["df"] = df
    session_data["columns"] = df.columns
    session_data["file_path"] = tmp_file_path
    session_data["hash"] = hash_value
    session_data["original_name"] = file.filename  # <-- ajouté

    return {"message": "Fichier chargé", "columns": df.columns, "hash": hash_value, "original_name": file.filename}

# 👀 Aperçu du dataset
@router.get("/preview")
def preview(n: int = 100):
    df = session_data.get("df")
    if df is None:
        raise HTTPException(status_code=400, detail="Aucun fichier uploadé")
    return df.limit(n).toPandas().to_dict(orient="records")

# 📑 Obtenir les colonnes
@router.get("/get-columns")
async def get_columns():
    df = session_data.get("df")
    if df is None:
        raise HTTPException(status_code=400, detail="Aucun fichier uploadé")
    return {"columns": df.columns}

# 📑 Obtenir colonnes + types Spark
@router.get("/get-schema")
async def get_schema():
    df = session_data.get("df")
    if df is None:
        raise HTTPException(status_code=400, detail="Aucun fichier uploadé")
    return {"schema": [{"name": name, "type": dtype} for name, dtype in df.dtypes]}

import sys
from pathlib import Path

# Ajouter la racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import shutil
from fastapi import UploadFile

from settings.config_paths import TMP_DIR, RESULTS_DIR

def save_uploaded_file(uploaded_file: UploadFile) -> str:
    tmp_file_path = TMP_DIR / uploaded_file.filename

    with open(tmp_file_path, "wb") as f:
        shutil.copyfileobj(uploaded_file.file, f)

    return str(tmp_file_path)


def get_results_file(dag_run_id: str) -> str:
    """Retourne le chemin du fichier de résultats"""
    result_file = RESULTS_DIR / f"{dag_run_id}_validation.json"
    return str(result_file)


def cleanup_tmp_files():
    """Nettoie les fichiers temporaires"""
    for f in TMP_DIR.glob("*"):
        if f.is_file():
            f.unlink()
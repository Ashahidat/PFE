import os
import shutil
from fastapi import UploadFile

TMP_DIR = "/home/ashahi/PFE/pip/data_quality/tmp"
RESULTS_DIR = "/home/ashahi/PFE/pip/data_quality/results"

os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

def save_uploaded_file(uploaded_file: UploadFile) -> str:
    os.makedirs(TMP_DIR, exist_ok=True)
    tmp_file_path = os.path.join(TMP_DIR, uploaded_file.filename)

    with open(tmp_file_path, "wb") as f:
        # Copie directement le contenu binaire
        shutil.copyfileobj(uploaded_file.file, f)

    return tmp_file_path

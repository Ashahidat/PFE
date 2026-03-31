import os
import json
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from jwt_dependencies import get_current_user

import sys
from pathlib import Path

# Ajouter la racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from settings.config_paths import RESULTS_DIR
router = APIRouter()


@router.get("/results/{dag_run_id}")
def get_results(dag_run_id: str, user=Depends(get_current_user)):
    """
    Retourne les résultats standardisés pour un DAG run spécifique
    """
    result_file = os.path.join(RESULTS_DIR, f"{dag_run_id}_validation.json")
    if not os.path.exists(result_file):
        return JSONResponse(content=[], status_code=200)

    with open(result_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Tous les résultats sont maintenant dans data["checks"]
    return data.get("checks", [])
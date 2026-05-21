import os
import json
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from jwt_dependencies import get_current_user
from pathlib import Path

import sys

# Ajouter la racine au PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from settings.config_paths import RESULTS_DIR
router = APIRouter()


def _find_result_file(dag_run_id: str) -> Path | None:
    """
    Look for the current validation JSON first, then fall back to the archived copy.
    push-atlas moves processed JSON files to `results/archive/`, so the UI still needs
    to resolve those archived files when it polls the results page.
    """
    current_file = Path(RESULTS_DIR) / f"{dag_run_id}_validation.json"
    if current_file.exists():
        return current_file

    archive_dir = Path(RESULTS_DIR) / "archive"
    if not archive_dir.exists():
        return None

    matches = sorted(
        archive_dir.glob(f"*_{dag_run_id}_validation.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return matches[0] if matches else None


@router.get("/results/{dag_run_id}")
def get_results(dag_run_id: str, user=Depends(get_current_user)):
    """
    Retourne les résultats standardisés pour un DAG run spécifique
    """
    result_file = _find_result_file(dag_run_id)
    
    # Logs de debug
    print(f"🔍 Recherche du fichier: {result_file or os.path.join(RESULTS_DIR, f'{dag_run_id}_validation.json')}")
    print(f"📁 RESULTS_DIR = {RESULTS_DIR}")
    print(f"📁 Le dossier existe: {os.path.exists(RESULTS_DIR)}")
    
    if not result_file or not result_file.exists():
        print(f"❌ Fichier non trouvé: {result_file}")
        # Lister les fichiers présents
        if os.path.exists(RESULTS_DIR):
            print(f"📄 Fichiers présents: {os.listdir(RESULTS_DIR)}")
        return JSONResponse(content=[], status_code=200)

    with open(result_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"✅ Fichier trouvé! {len(data.get('checks', []))} checks")
    return data.get("checks", [])

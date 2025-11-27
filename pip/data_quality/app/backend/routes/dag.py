from fastapi import APIRouter, Request
from session import session_data
import sys
import os

# Ajouter le chemin correct vers le dossier utils
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '..'))
from utils.airflow_utils import trigger_dag, get_dag_status

router = APIRouter()

@router.post("/run-dag")
async def run_dag(rules: dict):
    file_path = session_data.get("file_path")
    if not file_path:
        return {"error": "Aucun fichier uploadé"}
    config = {"file_path": file_path, "rules": rules}
    dag_run_id, resp = trigger_dag(config)
    if dag_run_id:
        session_data["dag_run_id"] = dag_run_id
        return {"message": "DAG lancé", "dag_run_id": dag_run_id}
    return {"error": "Erreur lors du lancement du DAG"}

# CORRECTION : Utilisez api_route pour gérer GET et OPTIONS
@router.api_route("/dag-status", methods=["GET", "OPTIONS"])
async def dag_status(request: Request, dag_run_id: str):
    if request.method == "OPTIONS":
        # Réponse vide pour la requête préflight CORS
        return {}
    
    state = get_dag_status(dag_run_id)
    return {"state": state}

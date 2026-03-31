import urllib.parse
import requests
from requests.auth import HTTPBasicAuth
import os

# Variables d'environnement (avec valeurs par défaut)
AIRFLOW_API_BASE = os.environ.get("AIRFLOW_API_URL", "http://localhost:8080/api/v1")
AIRFLOW_USER = os.environ.get("AIRFLOW_USER", "admin")
AIRFLOW_PASSWORD = os.environ.get("AIRFLOW_PASSWORD", "admin")


def trigger_dag(dag_id: str, config: dict):
    """
    Déclenche un DAG Airflow
    Args:
        dag_id: ID du DAG à déclencher (ex: "modular_validation_dag" ou "data_quality_pipeline_v2")
        config: Configuration à passer au DAG
    """
    url = f"{AIRFLOW_API_BASE}/dags/{dag_id}/dagRuns"
    
    print(f"🔗 Tentative de connexion à Airflow: {url}")
    print(f"👤 Utilisateur: {AIRFLOW_USER}")
    print(f"📦 Config envoyée: {config}")
    
    response = requests.post(
        url,
        auth=HTTPBasicAuth(AIRFLOW_USER, AIRFLOW_PASSWORD),
        headers={"Content-Type": "application/json"},
        json={"conf": config},
        timeout=30
    )
    
    print(f"📡 Réponse HTTP: {response.status_code}")
    print(f"📄 Corps de la réponse: {response.text[:200]}...")
    
    if response.status_code == 200:
        dag_run_id = response.json().get("dag_run_id")
        print(f"✅ DAGRun créé avec ID: {dag_run_id}")
        return dag_run_id, None
    else:
        print(f"❌ Échec de l'appel Airflow: {response.status_code}")
        return None, response


def get_dag_status(dag_run_id: str):
    """Récupère le statut d'un DAG run"""
    url = f"{AIRFLOW_API_BASE}/dags/~/dagRuns/{urllib.parse.quote(dag_run_id)}"
    resp = requests.get(url, auth=HTTPBasicAuth(AIRFLOW_USER, AIRFLOW_PASSWORD))

    try:
        data = resp.json()
        print("Airflow DAG status response:", data)
    except Exception:
        print("Erreur Airflow:", resp.text)
        return None

    if resp.status_code == 200:
        return data.get("state")
    return None
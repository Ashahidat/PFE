import urllib.parse
import requests
from requests.auth import HTTPBasicAuth

AIRFLOW_API_BASE = "http://localhost:8080/api/v1"
DAG_ID = "modular_validation_dag"
AIRFLOW_URL = f"{AIRFLOW_API_BASE}/dags/{DAG_ID}/dagRuns"

AIRFLOW_USER = "admin"
AIRFLOW_PASSWORD = "admin"



def trigger_dag(config: dict):
    print(f"🔗 Tentative de connexion à Airflow: {AIRFLOW_URL}")
    print(f"👤 Utilisateur: {AIRFLOW_USER}")
    print(f"🔑 Mot de passe: {AIRFLOW_PASSWORD}")
    print(f"📦 Config envoyée: {config}")
    
    response = requests.post(
        AIRFLOW_URL,
        auth=HTTPBasicAuth(AIRFLOW_USER, AIRFLOW_PASSWORD),
        headers={"Content-Type": "application/json"},
        json={"conf": config},
        timeout=30  # Ajoutez un timeout
    )
    
    print(f"📡 Réponse HTTP: {response.status_code}")
    print(f"📄 Corps de la réponse: {response.text[:200]}...")  # Premier 200 caractères
    
    if response.status_code == 200:
        dag_run_id = response.json().get("dag_run_id")
        print(f"✅ DAGRun créé avec ID: {dag_run_id}")
        return dag_run_id, None
    else:
        print(f"❌ Échec de l'appel Airflow: {response.status_code}")
        return None, response



def get_dag_status(dag_run_id: str):
    # Encoder correctement l'ID pour éviter les espaces ou caractères spéciaux
    safe_id = urllib.parse.quote(dag_run_id, safe="")
    status_url = f"{AIRFLOW_URL}/{safe_id}"
    resp = requests.get(status_url, auth=HTTPBasicAuth(AIRFLOW_USER, AIRFLOW_PASSWORD))

    try:
        data = resp.json()
        print("Airflow DAG status response:", data)  # debug
    except Exception:
        print("Erreur Airflow:", resp.text)
        return None

    if resp.status_code == 200:
        return data.get("state")  # "success", "failed" ou "running"
    return None

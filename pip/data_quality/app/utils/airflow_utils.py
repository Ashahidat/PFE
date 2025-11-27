import urllib.parse
import requests
from requests.auth import HTTPBasicAuth

AIRFLOW_API_BASE = "http://localhost:8080/api/v1"
DAG_ID = "modular_validation_dag"
AIRFLOW_URL = f"{AIRFLOW_API_BASE}/dags/{DAG_ID}/dagRuns"

AIRFLOW_USER = "admin"
AIRFLOW_PASSWORD = "admin"


def trigger_dag(config: dict):
    response = requests.post(
        AIRFLOW_URL,
        auth=HTTPBasicAuth(AIRFLOW_USER, AIRFLOW_PASSWORD),
        headers={"Content-Type": "application/json"},
        json={"conf": config}
    )
    print("trigger_dag status:", response.status_code, response.text)  # <-- Ajoute ça

    if response.status_code == 200:
        dag_run_id = response.json().get("dag_run_id")
        print("DAGRun créé avec ID :", dag_run_id)  # <-- Ajoute ça
        return dag_run_id, None

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

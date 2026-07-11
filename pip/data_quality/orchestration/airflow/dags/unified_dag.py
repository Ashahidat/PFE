# airflow_dag_modular.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import os
import sys
import json
import importlib
from pyspark.sql import SparkSession
from datetime import datetime as dt
from pathlib import Path

# ============================================================================
# CONFIGURATION DU PYTHON PATH - VERSION RELATIVE
# ============================================================================
# Détection automatique de la racine du projet
# Ce fichier est dans orchestration/
# La racine est donc parent du dossier orchestration
PROJECT_ROOT = Path(__file__).resolve().parents[3]

paths_to_add = [
    str(PROJECT_ROOT),
    str(PROJECT_ROOT / "app/backend"),
    str(PROJECT_ROOT / "orchestration"),
    str(PROJECT_ROOT / "utils")
]

for path in paths_to_add:
    if path not in sys.path:
        sys.path.insert(0, path)


VALIDATOR_ALIASES = {
    "regex": "ge",
    "great_expectations": "ge",
    "ge": "ge",
    "duplicates": "duplicates",
    "deequ": "deequ",
    "ml_profile": "ml_profile",
}


def _resolve_validator_name(validation_type: str) -> str:
    return VALIDATOR_ALIASES.get(validation_type, validation_type)


def run_modular_validations(**kwargs):
    from settings.config_paths import RESULTS_DIR
    
    dag_run = kwargs.get("dag_run")
    conf = dag_run.conf or {}

    file_path = conf.get("file_path")
    rules = conf.get("rules", {})

    dag_run_uuid = conf.get("dag_run_uuid") or str(dag_run.run_id)
    dataset_version_id = conf.get("dataset_version_id")

    if not file_path or not rules:
        raise ValueError(f"Paramètres manquants : file_path={file_path}, rules={rules}")

    # INITIALISATION SPARK
    spark = SparkSession.builder \
        .master("local[*]") \
        .appName("ModularValidation") \
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.3-spark-3.3") \
        .getOrCreate()

    df = spark.read.parquet(file_path)
    results = {}

    # EXECUTION DYNAMIQUE DES VALIDATORS
    for validation_type, validation_rules in rules.items():
        try:
            resolved_validation_type = _resolve_validator_name(validation_type)
            module_name = f"validators.{resolved_validation_type}_validator"
            module = importlib.import_module(module_name)

            print(f"🚀 Exécution du validator '{validation_type}'")

            if hasattr(module, "run") and callable(module.run):
                try:
                    results[resolved_validation_type] = module.run(spark, df, validation_rules)
                except TypeError:
                    results[resolved_validation_type] = module.run(df, validation_rules)

            print(f"✅ Validator '{validation_type}' terminé")

        except ModuleNotFoundError:
            print(f"⚠️ Module '{module_name}' introuvable. Ignoré.")
        except Exception as e:
            print(f"❌ Erreur dans '{validation_type}': {e}")
            results[_resolve_validator_name(validation_type)] = {"error": str(e)}

    # STANDARDISATION DES RESULTATS
    standardized = {
        "dag_run_id": dag_run_uuid,
        "dataset_version_id": dataset_version_id,
        "execution_date": dt.utcnow().isoformat(),
        "checks": []
    }

    def map_status(statut):
        if not statut:
            return "inconnu"
        statut = statut.strip().lower()
        if statut in ["réussi", "pass"]:
            return "réussi"
        elif statut in ["échoué", "fail"]:
            return "échoué"
        elif statut in ["skipped"]:
            return "ignoré"
        else:
            return "inconnu"

    for validation_type, validation_output in results.items():
        if isinstance(validation_output, dict) and "error" in validation_output:
            continue

        if isinstance(validation_output, list):
            for r in validation_output:
                standardized["checks"].append({
                    "rule_type": r.get("type de test", validation_type.upper()),
                    "column_name": r.get("colonne testée"),
                    "status": map_status(r.get("statut")),
                    "error_count": r.get("nombre", 0),
                    "ratio": r.get("ratio", "0/0"),
                    "examples": r.get("exemples", [])
                })

        elif isinstance(validation_output, dict):
            for subkey, subtests in validation_output.items():
                if isinstance(subtests, list):
                    for r in subtests:
                        standardized["checks"].append({
                            "rule_type": r.get("type de test", validation_type.upper()),
                            "column_name": r.get("colonne testée"),
                            "status": map_status(r.get("statut")),
                            "error_count": r.get("nombre", 0),
                            "ratio": r.get("ratio", "0/0"),
                            "examples": r.get("exemples", [])
                        })

    # SAUVEGARDE JSON - Utilisation de RESULTS_DIR
    output_dir = RESULTS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{dag_run_uuid}_validation.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(standardized, f, ensure_ascii=False, indent=2)

    print(f"📄 Résultats standardisés sauvegardés dans : {output_path}")

    spark.stop()
    return standardized


# DEFINITION DU DAG
with DAG(
    dag_id="modular_validation_dag",
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["data_quality", "modular"]
) as dag:

    run_validations = PythonOperator(
        task_id="run_modular_validations",
        python_callable=run_modular_validations
    )

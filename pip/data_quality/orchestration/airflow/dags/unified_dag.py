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

# -----------------------------
# CONFIGURATION DU PYTHON PATH
# -----------------------------
PROJECT_ROOT = "/home/ashahi/PFE/pip/data_quality"
paths_to_add = [
    PROJECT_ROOT,
    os.path.join(PROJECT_ROOT, "app/backend"),
    os.path.join(PROJECT_ROOT, "orchestration"),
    os.path.join(PROJECT_ROOT, "utils")
]

for path in paths_to_add:
    if path not in sys.path:
        sys.path.insert(0, path)

# -----------------------------
# IMPORTS APRES AJOUT AU PATH
# -----------------------------
from utils.db_utils import save_results_to_postgres
from db.models.data_quality_results import DataQualityResult
from db.crud.data_quality_results import (
    create_result,
    get_results_by_dag_run,
    update_result_status,
)


def run_modular_validations(**kwargs):
    dag_run = kwargs.get("dag_run")
    conf = dag_run.conf or {}

    file_path = conf.get("file_path")
    rules = conf.get("rules", {})

    dag_run_uuid = conf.get("dag_run_uuid") or str(dag_run.run_id)
    dataset_version_id = conf.get("dataset_version_id")

    if not file_path or not rules:
        raise ValueError(f"Paramètres manquants : file_path={file_path}, rules={rules}")

    # -----------------------------
    # INITIALISATION SPARK
    # -----------------------------
    spark = SparkSession.builder \
        .master("local[*]") \
        .appName("ModularValidation") \
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.7-spark-3.3") \
        .getOrCreate()

    df = spark.read.parquet(file_path)

    results = {}

    # -----------------------------
    # EXECUTION DYNAMIQUE DES VALIDATORS
    # -----------------------------
    for validation_type, validation_rules in rules.items():
        try:
            module_name = f"validators.{validation_type}_validator"
            module = importlib.import_module(module_name)

            print(f"🚀 Exécution du validator '{validation_type}'")

            if hasattr(module, "run") and callable(module.run):
                try:
                    results[validation_type] = module.run(spark, df, validation_rules)
                except TypeError:
                    results[validation_type] = module.run(df, validation_rules)

            print(f"✅ Validator '{validation_type}' terminé")

        except ModuleNotFoundError:
            print(f"⚠️ Module '{module_name}' introuvable. Ignoré.")
        except Exception as e:
            print(f"❌ Erreur dans '{validation_type}': {e}")
            results[validation_type] = {"error": str(e)}

    # -----------------------------
    # STANDARDISATION DES RESULTATS
    # -----------------------------
    standardized = {
        "dag_run_id": dag_run_uuid,
        "dataset_version_id": dataset_version_id,
        "execution_date": dt.utcnow().isoformat(),
        "checks": []
    }

    def map_status(statut):
        if statut == "réussi":
            return "PASS"
        elif statut == "échoué":
            return "FAIL"
        elif statut == "skipped":
            return "SKIPPED"
        else:
            return "UNKNOWN"

    for validation_type, validation_output in results.items():

        # Ignorer erreurs globales
        if isinstance(validation_output, dict) and "error" in validation_output:
            continue

        # -----------------------------
        # CAS 1 : LISTE
        # -----------------------------
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

        # -----------------------------
        # CAS 2 : DICT IMBRIQUE (ex: regex)
        # -----------------------------
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

    # -----------------------------
    # SAUVEGARDE JSON
    # -----------------------------
    output_dir = "/home/ashahi/PFE/pip/data_quality/results"
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, f"{dag_run_uuid}_validation.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(standardized, f, ensure_ascii=False, indent=2)

    print(f"📄 Résultats standardisés sauvegardés dans : {output_path}")

    # -----------------------------
    # SAUVEGARDE POSTGRESQL
    # -----------------------------
    if dataset_version_id:
        try:
            valid_results = {
                k: v for k, v in results.items()
                if isinstance(v, (list, dict)) and "error" not in v
            }

            if valid_results:
                saved = save_results_to_postgres(
                    results=valid_results,
                    dag_run_uuid=dag_run_uuid,
                    dataset_version_id=dataset_version_id
                )
                print(f"✅ {len(saved)} résultats sauvegardés dans PostgreSQL")
            else:
                print("⚠️ Aucun résultat valide à sauvegarder")

        except Exception as e:
            print(f"❌ Erreur sauvegarde PostgreSQL: {e}")

    spark.stop()
    return standardized


# -----------------------------
# DEFINITION DU DAG
# -----------------------------
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

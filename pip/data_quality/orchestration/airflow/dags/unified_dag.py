# airflow_dag_modular.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import os
import sys
import json
import importlib
from pyspark.sql import SparkSession
import uuid

# -----------------------------
# CONFIGURATION DU PYTHON PATH
# -----------------------------
# Racine du projet Data Quality
PROJECT_ROOT = "/home/ashahi/PFE/pip/data_quality"

# Ajouter les dossiers principaux à sys.path
paths_to_add = [
    PROJECT_ROOT,                                   # /data_quality
    os.path.join(PROJECT_ROOT, "app/backend"),     # backend + db, models, crud
    os.path.join(PROJECT_ROOT, "orchestration"),   # orchestration DAGs
    os.path.join(PROJECT_ROOT, "utils")            # utils pour db_utils
]

for path in paths_to_add:
    if path not in sys.path:
        sys.path.insert(0, path)

# -----------------------------
# IMPORTS APRES AJOUT AU PATH
# -----------------------------
# db_utils doit exister dans /utils
from utils.db_utils import save_results_to_postgres  

# Modèles et CRUD SQLAlchemy
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
    
    # UUIDs obligatoires pour PostgreSQL
    dag_run_uuid = conf.get("dag_run_uuid")
    dataset_version_id = conf.get("dataset_version_id")
    
    if not dag_run_uuid:
        # Si non fourni, on peut le récupérer depuis Airflow
        dag_run_uuid = str(kwargs.get("dag_run").run_id)  # À adapter selon ta BDD
    
    if not dataset_version_id:
        raise ValueError("dataset_version_id est requis dans la configuration pour PostgreSQL")

    if not file_path or not rules:
        raise ValueError(f"Paramètres manquants : file_path={file_path}, rules={rules}")

    # Initialisation Spark
    spark = SparkSession.builder \
        .master("local[*]") \
        .appName("ModularValidation") \
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.7-spark-3.3") \
        .getOrCreate()

    # Lecture du fichier (sans cache inutile)
    df = spark.read.parquet(file_path)

    results = {}

    # Exécution dynamique des validateurs
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

    # Sauvegarde JSON
    output_dir = "/home/ashahi/PFE/pip/data_quality/results"
    os.makedirs(output_dir, exist_ok=True)
    dag_run_id = kwargs.get("run_id")
    output_path = os.path.join(output_dir, f"{dag_run_id}_validation.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"📄 Résultats sauvegardés dans : {output_path}")

    # 🔹 Sauvegarde PostgreSQL (seulement les résultats valides)
    try:
        # Filtrer les erreurs
        valid_results = {k: v for k, v in results.items() 
                        if isinstance(v, (list, dict)) and "error" not in v}
        
        if valid_results:
            saved = save_results_to_postgres(
                results=valid_results,
                dag_run_uuid=dag_run_uuid,
                dataset_version_id=dataset_version_id
            )
            print(f"✅ {len(saved)} résultats sauvegardés dans PostgreSQL")
        else:
            print("⚠️ Aucun résultat valide à sauvegarder dans PostgreSQL")
            
    except Exception as e:
        print(f"❌ Erreur sauvegarde PostgreSQL: {e}")
        # On continue, le fichier JSON est déjà sauvegardé

    spark.stop()
    return results


# Définition du DAG
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
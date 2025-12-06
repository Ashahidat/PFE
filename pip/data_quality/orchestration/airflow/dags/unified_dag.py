# airflow_dag_modular.py
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime
import os
import json
import sys
import importlib
from pyspark.sql import SparkSession


# Ajouter le chemin racine du projet pour trouver les validators
sys.path.append("/home/ashahi/PFE/pip/data_quality/orchestration")
sys.path.append("/home/ashahi/PFE/pip/data_quality")
from utils.db_utils import save_results_to_postgres
# from utils.atlas_entities import get_or_create_dataset, get_or_create_column


def run_modular_validations(**kwargs):
    dag_run = kwargs.get("dag_run")
    conf = dag_run.conf or {}

    file_path = conf.get("file_path")
    rules = conf.get("rules", {})

    if not file_path or not rules:
        raise ValueError(f"Paramètres manquants : file_path={file_path}, rules={rules}")

    # Initialisation Spark
    spark = SparkSession.builder \
        .master("local[*]") \
        .appName("ModularValidation") \
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.7-spark-3.3") \
        .getOrCreate()

    # # Lecture du fichier

    # Cache simple pour éviter de relire le même dataset
    spark_cache = {}  # clé = file_path, valeur = DataFrame

    if file_path in spark_cache:
        df = spark_cache[file_path]
    else:
        df = spark.read.parquet(file_path)
        spark_cache[file_path] = df

    # if file_path.endswith(".csv"):
    #     df = spark.read.option("header", "true").csv(file_path)
    # else:
    #     df = spark.read.json(file_path)

    results = {}

    # Exécution dynamique des validateurs
    for validation_type, validation_rules in rules.items():
        try:
            module_name = f"validators.{validation_type}_validator"
            module = importlib.import_module(module_name)
            print(f"🚀 Exécution du validator '{validation_type}'")

            # Certains modules ont besoin de spark, d'autres non
            if hasattr(module, "run") and callable(module.run):
                # Essayons de passer spark si nécessaire
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

    # Sauvegarde des résultats
    output_dir = "/home/ashahi/PFE/pip/data_quality/results"
    os.makedirs(output_dir, exist_ok=True)
    dag_run_id = kwargs.get("run_id")  # récupère le dag_run_id
    output_path = os.path.join(output_dir, f"{dag_run_id}_validation.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"📄 Résultats sauvegardés dans : {output_path}")


    # # 🔹 Sauvegarde Postgres
    # dag_run_id = kwargs.get("run_id")
    # # save_results_to_postgres(results, dag_run_id)


    spark.stop()
    return results

# Définition du DAG unifié modulaire
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

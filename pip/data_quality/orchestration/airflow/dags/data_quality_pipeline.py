"""
DAG Airflow modulaire pour la validation de qualité
Version avec tâches parallèles (sans expand)
"""

from airflow import DAG
from airflow.decorators import task
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json
import sys
from pathlib import Path

# Configuration des chemins
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "app/backend"))
sys.path.insert(0, str(PROJECT_ROOT / "validators"))
sys.path.insert(0, str(PROJECT_ROOT / "settings"))

try:
    from settings.config_paths import RESULTS_DIR
except ImportError:
    RESULTS_DIR = PROJECT_ROOT / "results"

from pyspark.sql import SparkSession


# ============================================================================
# TÂCHES
# ============================================================================

@task
def init_context(**context) -> Dict[str, Any]:
    """Initialise le contexte et charge les données"""
    dag_run = context.get("dag_run")
    conf = dag_run.conf or {}
    
    file_path = conf.get("file_path")
    rules = conf.get("rules", {})
    dag_run_uuid = conf.get("dag_run_uuid") or str(dag_run.run_id)
    dataset_version_id = conf.get("dataset_version_id")
    
    if not file_path:
        raise ValueError("file_path manquant")
    
    # Lire le fichier Parquet sans garder la session Spark
    spark = SparkSession.builder \
        .master("local[*]") \
        .appName(f"DQ_{dag_run_uuid[:8]}") \
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.7-spark-3.3") \
        .getOrCreate()
    
    df = spark.read.parquet(file_path)
    columns = df.columns
    total_rows = df.count()
    
    # Arrêter Spark immédiatement après avoir récupéré les infos
    spark.stop()
    
    # NE PAS retourner la session Spark !
    return {
        "file_path": file_path,
        "rules": rules,
        "dag_run_uuid": dag_run_uuid,
        "dataset_version_id": dataset_version_id,
        "columns": columns,
        "total_rows": total_rows
    }


@task
def validate_duplicates(init_data: Dict) -> List[Dict]:
    """Valide les doublons (sensibles + full row)"""
    from validators.duplicates_validator import run as run_duplicates
    from pyspark.sql import SparkSession
    
    # Créer une nouvelle session Spark pour cette tâche
    spark = SparkSession.builder \
        .master("local[*]") \
        .appName("ValidateDuplicates") \
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.7-spark-3.3") \
        .getOrCreate()
    
    file_path = init_data["file_path"]
    rules = init_data["rules"].get("duplicates", {})
    
    df = spark.read.parquet(file_path)
    results = run_duplicates(spark, df, rules)
    
    # Arrêter Spark
    spark.stop()
    
    return results


@task
def validate_regex(init_data: Dict) -> List[Dict]:
    """Valide les regex"""
    from validators.regex_validator import run as run_regex
    from pyspark.sql import SparkSession
    
    # Créer une nouvelle session Spark pour cette tâche
    spark = SparkSession.builder \
        .master("local[*]") \
        .appName("ValidateRegex") \
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.7-spark-3.3") \
        .getOrCreate()
    
    file_path = init_data["file_path"]
    rules = init_data["rules"].get("regex", {})
    
    df = spark.read.parquet(file_path)
    results = run_regex(df, rules)
    
    # Arrêter Spark
    spark.stop()
    
    return results.get("regex", [])


@task
def aggregate_results(
    init_data: Dict,
    duplicates_results: List[Dict],
    regex_results: List[Dict]
) -> Dict:
    """Agrège tous les résultats et sauvegarde"""
    from datetime import datetime as dt
    
    standardized = {
        "dag_run_id": init_data["dag_run_uuid"],
        "dataset_version_id": init_data["dataset_version_id"],
        "execution_date": dt.utcnow().isoformat(),
        "checks": []
    }
    
    standardized["checks"].extend(duplicates_results)
    standardized["checks"].extend(regex_results)
    
    output_path = RESULTS_DIR / f"{init_data['dag_run_uuid']}_validation.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(standardized, f, ensure_ascii=False, indent=2)
    
    print(f"📄 Résultats sauvegardés : {output_path}")
    print(f"📊 {len(standardized['checks'])} checks exécutés")
    
    return standardized


# ============================================================================
# DÉFINITION DU DAG
# ============================================================================

with DAG(
    dag_id="data_quality_pipeline_v2",
    start_date=datetime(2025, 1, 1),
    schedule_interval=None,
    catchup=False,
    tags=["data_quality", "modular"],
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
    }
) as dag:
    
    # 1. Initialisation
    init = init_context()
    
    # 2. Validation des doublons (1 tâche)
    duplicates = validate_duplicates(init)
    
    # 3. Validation des regex (1 tâche)
    regex = validate_regex(init)
    
    # 4. Agrégation
    final = aggregate_results(init, duplicates, regex)
    
    # Dépendances : duplicates et regex s'exécutent en parallèle
    init >> [duplicates, regex]
    duplicates >> final
    regex >> final
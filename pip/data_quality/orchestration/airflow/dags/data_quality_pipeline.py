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
import os
os.environ["SPARK_VERSION"] = "3.3"

# Configuration des chemins
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
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.3-spark-3.3") \
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
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.3-spark-3.3") \
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
    """Valide les contrôles Great Expectations (formats / contrats)."""
    from validators.ge_validator import run as run_ge
    from pyspark.sql import SparkSession
    
    # Créer une nouvelle session Spark pour cette tâche
    spark = SparkSession.builder \
        .master("local[*]") \
        .appName("ValidateGreatExpectations") \
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.3-spark-3.3") \
        .getOrCreate()
    
    file_path = init_data["file_path"]
    rules = init_data["rules"].get("ge") or init_data["rules"].get("regex", {})

    df = spark.read.parquet(file_path)
    results = run_ge(spark, df, rules)
    
    # Arrêter Spark
    spark.stop()
    
    return results.get("ge", [])


# Dans le DAG, AJOUTER cette tâche APRES validate_regex
@task
def validate_deequ(init_data: Dict) -> List[Dict]:
    """Valide les contraintes Deequ (complétude, min, max, valeurs autorisées)"""
    from validators.deequ_validator import run as run_deequ
    from pyspark.sql import SparkSession
    
    constraints = init_data["rules"].get("deequ", [])
    if not constraints:
        return []
    
    # Créer une nouvelle session Spark pour cette tâche
    spark = SparkSession.builder \
        .master("local[*]") \
        .appName("ValidateDeequ") \
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.3-spark-3.3") \
        .getOrCreate()
    
    file_path = init_data["file_path"]
    df = spark.read.parquet(file_path)
    results = run_deequ(spark, df, constraints)
    
    spark.stop()
    return results


@task
def validate_ml_profile(init_data: Dict) -> List[Dict]:
    """Valide le risque de profil colonne via le modèle ML champion."""
    from validators.ml_profile_validator import run as run_ml_profile
    from pyspark.sql import SparkSession

    spark = SparkSession.builder \
        .master("local[*]") \
        .appName("ValidateMLProfile") \
        .config("spark.jars.packages", "com.amazon.deequ:deequ:2.0.3-spark-3.3") \
        .getOrCreate()

    file_path = init_data["file_path"]
    df = spark.read.parquet(file_path)
    results = run_ml_profile(spark, df, init_data.get("rules", {}).get("ml_profile", {}))

    spark.stop()
    return results


# MODIFIER aggregate_results pour accepter deequ_results
@task
def aggregate_results(
    init_data: Dict,
    duplicates_results: List[Dict],
    ge_results: List[Dict],
    deequ_results: List[Dict],
    ml_profile_results: List[Dict]
) -> Dict:
    """Agrège tous les résultats et sauvegarde"""
    from datetime import datetime as dt
    
    standardized = {
        "dag_run_id": init_data["dag_run_uuid"],
        "dataset_version_id": init_data["dataset_version_id"],
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
        elif statut in ["ignoré", "skipped"]:
            return "ignoré"
        else:
            return "inconnu"
    
    # Standardiser les résultats des doublons
    for check in duplicates_results:
        standardized["checks"].append({
            "rule_type": check.get("type de test", "doublons"),
            "column_name": check.get("colonne testée"),
            "status": map_status(check.get("statut")),
            "error_count": check.get("nombre", 0),
            "ratio": check.get("ratio", "0/0"),
            "examples": check.get("exemples", [])
        })
    
    # Standardiser les résultats Great Expectations
    for check in ge_results:
        standardized["checks"].append({
            "rule_type": check.get("type de test", "ge"),
            "column_name": check.get("colonne testée"),
            "status": map_status(check.get("statut")),
            "error_count": check.get("nombre", 0),
            "ratio": check.get("ratio", "0/0"),
            "examples": check.get("exemples", [])
        })
    
    # NOUVEAU: Standardiser les résultats Deequ
    for check in deequ_results:
        standardized["checks"].append({
            "rule_type": check.get("type de test", "deequ"),
            "column_name": check.get("colonne testée"),
            "status": map_status(check.get("statut")),
            "error_count": check.get("nombre", 0),
            "ratio": check.get("ratio", "0/0"),
            "examples": check.get("exemples", [])
        })

    # Standardiser les résultats ML profile
    for check in ml_profile_results:
        standardized["checks"].append({
            "rule_type": check.get("type de test", "ml_profile"),
            "column_name": check.get("colonne testée"),
            "status": map_status(check.get("statut")),
            "error_count": check.get("nombre", 0),
            "ratio": check.get("ratio", "0/0"),
            "examples": check.get("exemples", [])
        })
    
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
    
    # 3. Validation Great Expectations (1 tâche)
    ge = validate_regex(init)
    
    # 4. Validation Deequ (1 tâche) - NOUVEAU
    deequ = validate_deequ(init)

    # 5. Validation ML profile
    ml_profile = validate_ml_profile(init)

    # 6. Agrégation
    final = aggregate_results(init, duplicates, ge, deequ, ml_profile)
    
    # Dépendances : duplicates, ge, deequ et ml_profile s'exécutent en parallèle
    init >> [duplicates, ge, deequ, ml_profile]  # ← Les tâches en parallèle
    duplicates >> final
    ge >> final
    deequ >> final
    ml_profile >> final

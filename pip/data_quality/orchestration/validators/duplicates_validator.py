# validators/duplicates_validator.py
from typing import Dict, Any, List
from pyspark.sql import DataFrame, SparkSession
import sys
import os

# chemin projet (ajuste si nécessaire)
sys.path.append("/home/ashahi/PFE/pip/data_quality")
os.environ["SPARK_VERSION"] = "3.3"
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyspark.sql.functions import col, count as _count


def get_detailed_duplicates_info(df: DataFrame, column_name: str, max_examples: int = 5) -> Dict[str, Any]:
    """
    Retourne:
      - nombre: nombre de VALEURS distinctes qui apparaissent plus d'une fois (ex: nombre de clés répétées)
      - total_non_null: nombre de lignes non nulles pour cette colonne (utile pour bâtir le ratio)
      - exemples: liste d'exemples (valeurs) répétées
    """
    total_non_null = df.filter(col(column_name).isNotNull()).count()
    if total_non_null == 0:
        return {"nombre": 0, "total_non_null": 0, "exemples": []}

    dup_values_df = (
        df.groupBy(column_name)
          .agg(_count("*").alias("occurrences"))
          .filter(col("occurrences") > 1)
          .orderBy(col("occurrences").desc())
          .cache()
    )

    total_repeated_values = dup_values_df.count()
    exemples = [str(row[column_name]) for row in dup_values_df.limit(max_examples).collect()]
    dup_values_df.unpersist()

    return {"nombre": total_repeated_values, "total_non_null": total_non_null, "exemples": exemples}


def detect_full_row_duplicates(df: DataFrame, max_examples: int = 5) -> Dict[str, Any]:
    total_rows = df.count()
    if total_rows == 0:
        return {
            "alerte": "Dataset vide, aucun doublon possible",
            "type de test": "doublons sur ligne entière",
            "statut": "réussi",
            "nombre": 0,
            "ratio": "0/0",
            "exemples": []
        }

    unique_rows_count = df.dropDuplicates().count()
    duplicate_rows_count = total_rows - unique_rows_count

    if duplicate_rows_count > 0:
        examples_raw = (
            df.groupBy(df.columns)
              .agg(_count("*").alias("occurrences"))
              .filter(col("occurrences") > 1)
              .orderBy(col("occurrences").desc())
              .limit(max_examples)
              .collect()
        )
        examples = [row.asDict() for row in examples_raw]
        statut = "échoué"
        message = "Des doublons sur lignes complètes ont été détectés"
    else:
        examples = []
        statut = "réussi"
        message = "Aucun doublon détecté sur lignes complètes"

    ratio_str = f"{duplicate_rows_count}/{total_rows}"

    return {
        "alerte": message,
        "type de test": "doublons sur ligne entière",
        "statut": statut,
        "nombre": duplicate_rows_count,
        "ratio": ratio_str,
        "exemples": examples
    }


def run(spark: SparkSession, df: DataFrame, rules: Any) -> List[Dict[str, Any]]:
    """
    Retourne une LISTE de dicts. Chaque dict porte :
      - type de test (ex: "doublons sensibles sur colonne: X" ou "doublons sur ligne entière")
      - statut: "réussi" / "échoué" / "skipped"
      - alerte, nombre, ratio, exemples...
    """

    # normaliser rules
    if isinstance(rules, list):
        rules = {"sensitive": rules, "full_row": False}
    elif not isinstance(rules, dict):
        raise ValueError(f"Le paramètre 'rules' doit être un dict ou une list, reçu {type(rules)}")

    validations: List[Dict[str, Any]] = []

    # Calculer total_rows une seule fois (coût : un count)
    total_rows = df.count()

    # 1) Doublons sensibles (par colonne demandée)
    sensitive_cols = rules.get("sensitive", [])
    if sensitive_cols:
        for col_name in sensitive_cols:
            # colonne absente => on marque skipped mais on garde un type explicite
            if col_name not in df.columns:
                validations.append({
                    "alerte": f"Colonne '{col_name}' introuvable dans le dataset",
                    "type de test": f"doublons sensibles sur colonne: {col_name}",
                    "statut": "skipped",
                    "colonne testée": col_name,
                    "nombre": 0,
                    "ratio": f"0/{total_rows}",
                    "exemples": []
                })
                continue

            detail = get_detailed_duplicates_info(df, col_name)
            nombre = detail["nombre"]
            # on préfère afficher ratio sur base du total de lignes (pour éviter 0/0),
            # si total_rows == 0 on retombe sur total_non_null
            denom = total_rows if total_rows > 0 else detail.get("total_non_null", 0)
            ratio = f"{nombre}/{denom}" if denom > 0 else "0/0"

            if nombre > 0:
                val = {
                    "alerte": "Des doublons ont été détectés sur cette colonne",
                    "type de test": f"doublons sensibles sur colonne: {col_name}",
                    "statut": "échoué",
                    "colonne testée": col_name,
                    "nombre": nombre,
                    "ratio": ratio,
                    "exemples": detail["exemples"]
                }
            else:
                val = {
                    "alerte": f"Aucun doublon détecté sur la colonne {col_name}",
                    "type de test": f"doublons sensibles sur colonne: {col_name}",
                    "statut": "réussi",
                    "colonne testée": col_name,
                    "nombre": 0,
                    "ratio": ratio,
                    "exemples": []
                }

            validations.append(val)

    # 2) Doublons sur ligne entière (full row) si demandé
    if rules.get("full_row", False):
        full_row_result = detect_full_row_duplicates(df)
        validations.append(full_row_result)

    # 3) Si aucune règle fournie, on renvoie une liste vide (le caller sait qu'aucun test n'a été exécuté)
    return validations

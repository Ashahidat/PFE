# validators/regex_validator.py
from typing import List, Dict
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, trim
from great_expectations.dataset import SparkDFDataset

DEFAULT_REGEX = {
    "email": r"^[\w\.-]+@[\w\.-]+\.\w+$",
    "phone": r"^\+?\d{8,15}$",
    "postal_code": r"^\d{5}$"
}

def run(df: DataFrame, user_selection: Dict[str, List[str]]) -> Dict[str, List[Dict]]:
    """
    Validateur de colonnes via regex (GE + Spark).
    user_selection: {"email_col": ["email"], "phone_col": ["phone"]}
    Retourne la liste des résultats + alertes formatées comme dans l'exemple 'duplicates'.
    """
    results = []
    max_examples = 5

    for col_name, rules in user_selection.items():
        if col_name not in df.columns:
            continue

        non_empty_df = df.withColumn(col_name, trim(col(col_name))) \
                         .filter(
                             (col(col_name).isNotNull()) &
                             (col(col_name) != "") &
                             (col(col_name) != "NULL")
                         )

        total_count = non_empty_df.count()

        if total_count == 0:
            for rule in rules:
                results.append({
                    "alerte": f"Aucune donnée à valider pour la colonne '{col_name}'",
                    "type de test": f"regex_{rule}",
                    "statut": "réussi",
                    "colonne testée": col_name,
                    "nombre": 0,
                    "ratio": "0/0",
                    "exemples": []
                })
            continue

        validator = SparkDFDataset(non_empty_df)

        for rule in rules:
            pattern = DEFAULT_REGEX.get(rule)
            if pattern is None:
                continue

            try:
                result = validator.expect_column_values_to_match_regex(
                    column=col_name,
                    regex=pattern,
                    meta={"rule": f"{col_name}_{rule}_check"}
                )

                unexpected_count = result.result.get("unexpected_count", 0)
                examples = result.result.get("partial_unexpected_list", [])[:max_examples]
                statut = "réussi" if result.success else "échoué"

                if not result.success:
                    entry = {
                        "alerte": "Des valeurs non conformes ont été détectées sur la colonne",
                        "type de test": f"regex_{rule}",
                        "statut": "échoué",
                        "colonne testée": col_name,
                        "nombre": unexpected_count,
                        "ratio": f"{unexpected_count}/{total_count}",
                        "exemples": examples
                    }
                else:
                    entry = {
                        "type de test": f"regex_{rule}",
                        "statut": "réussi",
                        "colonne testée": col_name,
                        "nombre": unexpected_count,
                        "ratio": f"{unexpected_count}/{total_count}",
                        # "exemples": examples
                    }

                results.append(entry)



            except Exception as e:
                results.append({
                    "alerte": f"Échec technique de la validation de la colonne '{col_name}'",
                    "type de test": f"regex_{rule}",
                    "statut": "échoué",
                    "colonne testée": col_name,
                    "nombre": total_count,
                    "ratio": f"{total_count}/{total_count}",
                    "exemples": ["Validation failed"],
                    "error": str(e)
                })

    return {"regex": results}

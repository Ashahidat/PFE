# validators/ge_validator.py
from typing import Any, Dict, List

from pyspark.sql import DataFrame, SparkSession

from validators.regex_validator import run as run_regex


def _rewrite_rule_type(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith("regex_"):
        return "ge_" + value[len("regex_"):]
    if value == "regex":
        return "ge"
    return value


def run(spark: SparkSession, df: DataFrame, user_selection: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Bloc Great Expectations.

    On conserve l'implémentation actuelle basée sur des validations de format,
    mais on l'expose sous un nom métier explicite pour éviter la confusion avec
    les autres couches.
    """

    result = run_regex(df, user_selection)
    ge_results = []

    for item in result.get("regex", []):
        transformed = dict(item)
        transformed["type de test"] = _rewrite_rule_type(transformed.get("type de test"))
        ge_results.append(transformed)

    return {"ge": ge_results}

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd
from pyspark.sql import DataFrame, SparkSession

from settings.config_paths import BASE_DIR, ML_MODELS_DIR

_ID_NAME_RE = re.compile(r"(^|[^a-z0-9])(id|uuid|guid|key)([^a-z0-9]|$)")
_TIMESTAMP_NAME_RE = re.compile(r"(^|[^a-z0-9])(date|datetime|timestamp|time|created_at|updated_at)([^a-z0-9]|$)")
_TARGET_NAME_RE = re.compile(r"(^|[^a-z0-9])(target|label|class|churn|status|outcome)([^a-z0-9]|$)")


def _candidate_registry_paths() -> list[Path]:
    return [
        ML_MODELS_DIR / "model_registry.json",
        BASE_DIR / "notebooks" / "artifacts" / "ml_models" / "model_registry.json",
    ]


def _load_registry() -> dict | None:
    for path in _candidate_registry_paths():
        if path.exists():
            import json

            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    return None


def _normalized_name(column_name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", column_name.strip().lower())


def _spark_detect_protected_columns(df: DataFrame) -> dict[str, str]:
    from pyspark.sql import functions as F
    from pyspark.sql.types import DateType, TimestampType

    total_rows = df.count()
    protected_columns: dict[str, str] = {}

    for field in df.schema.fields:
        column_name = field.name
        normalized_name = _normalized_name(column_name)
        reasons: list[str] = []

        non_null_count = df.filter(F.col(column_name).isNotNull()).count()
        distinct_non_null = df.select(F.countDistinct(F.col(column_name)).alias("distinct")).first()["distinct"] or 0

        if non_null_count == 0:
            reasons.append("all_null")
        elif distinct_non_null <= 1:
            reasons.append("constant")

        if isinstance(field.dataType, (DateType, TimestampType)) or _TIMESTAMP_NAME_RE.search(normalized_name):
            reasons.append("timestamp_like")

        if _TARGET_NAME_RE.search(normalized_name):
            reasons.append("target_like")

        if _ID_NAME_RE.search(normalized_name):
            reasons.append("identifier_like")
        elif non_null_count >= 10 and distinct_non_null > 0:
            uniqueness_ratio = distinct_non_null / max(non_null_count, 1)
            if uniqueness_ratio >= 0.98 and (
                normalized_name.endswith("_id")
                or normalized_name.endswith("id")
                or normalized_name.endswith("_key")
                or normalized_name.endswith("key")
            ):
                reasons.append("high_cardinality_identifier")

        if reasons:
            protected_columns[column_name] = ", ".join(dict.fromkeys(reasons))

    if total_rows == 0:
        return {field.name: "all_null" for field in df.schema.fields}

    return protected_columns


def _spark_column_entropy(df: DataFrame, column_name: str) -> float:
    from pyspark.sql import functions as F

    rows = df.groupBy(F.col(column_name)).count().collect()
    if len(rows) <= 1:
        return 0.0

    total = sum(row["count"] for row in rows) or 1
    entropy_value = 0.0
    for row in rows:
        p = row["count"] / total
        if p > 0:
            entropy_value -= p * float(np.log(p))
    return float(entropy_value)


def _spark_profile_column(df: DataFrame, column_name: str, dataset_name: str) -> dict[str, Any]:
    from pyspark.sql import functions as F
    from pyspark.sql.types import NumericType

    field = next(field for field in df.schema.fields if field.name == column_name)
    total_rows = df.count()
    normalized_name = _normalized_name(column_name)
    missing_count = df.filter(F.col(column_name).isNull()).count()
    non_null_count = total_rows - missing_count
    distinct_non_null = df.select(F.countDistinct(F.col(column_name)).alias("distinct")).first()["distinct"] or 0
    cardinality = distinct_non_null + (1 if missing_count > 0 else 0)

    base = {
        "missing_rate": missing_count / max(total_rows, 1),
        "cardinality": int(cardinality),
        "cardinality_ratio": cardinality / max(total_rows, 1),
        "non_null_cardinality_ratio": distinct_non_null / max(non_null_count, 1),
        "duplication_rate": 1 - (distinct_non_null / max(non_null_count, 1)),
        "dataset_name": dataset_name,
        "column_name": column_name,
    }

    if isinstance(field.dataType, NumericType):
        series_df = df.select(F.col(column_name).cast("double").alias("value")).where(F.col("value").isNotNull())
        aggregate = series_df.agg(
            F.mean("value").alias("mean"),
            F.stddev_samp("value").alias("std"),
            F.min("value").alias("min"),
            F.max("value").alias("max"),
            F.skewness("value").alias("skewness"),
            F.kurtosis("value").alias("kurtosis"),
        ).first().asDict()

        quantiles = series_df.approxQuantile("value", [0.25, 0.5, 0.75], 0.01) if non_null_count else [np.nan, np.nan, np.nan]
        q1, median, q3 = (float(quantiles[0]) if len(quantiles) > 0 and quantiles[0] is not None else np.nan,
                          float(quantiles[1]) if len(quantiles) > 1 and quantiles[1] is not None else np.nan,
                          float(quantiles[2]) if len(quantiles) > 2 and quantiles[2] is not None else np.nan)
        iqr = q3 - q1 if pd.notna(q1) and pd.notna(q3) else np.nan

        if pd.notna(median) and non_null_count:
            mad_df = series_df.select(F.abs(F.col("value") - F.lit(median)).alias("abs_dev")).where(F.col("abs_dev").isNotNull())
            mad_quantiles = mad_df.approxQuantile("abs_dev", [0.5], 0.01)
            mad = float(mad_quantiles[0]) if mad_quantiles else np.nan
        else:
            mad = np.nan

        if pd.notna(q1) and pd.notna(q3) and iqr > 0:
            outlier_share = (
                series_df.select(
                    F.mean(
                        F.when((F.col("value") < q1 - 1.5 * iqr) | (F.col("value") > q3 + 1.5 * iqr), 1).otherwise(0)
                    ).alias("outlier_share")
                ).first()["outlier_share"]
            )
            outlier_share = float(outlier_share) if outlier_share is not None else 0.0
        else:
            outlier_share = 0.0

        zero_rate = series_df.select(F.mean(F.when(F.col("value") == 0, 1).otherwise(0)).alias("rate")).first()["rate"]
        negative_rate = series_df.select(F.mean(F.when(F.col("value") < 0, 1).otherwise(0)).alias("rate")).first()["rate"]
        positive_rate = series_df.select(F.mean(F.when(F.col("value") > 0, 1).otherwise(0)).alias("rate")).first()["rate"]

        features = {
            **base,
            "mean": float(aggregate.get("mean")) if aggregate.get("mean") is not None else np.nan,
            "std": float(aggregate.get("std")) if aggregate.get("std") is not None else np.nan,
            "min": float(aggregate.get("min")) if aggregate.get("min") is not None else np.nan,
            "max": float(aggregate.get("max")) if aggregate.get("max") is not None else np.nan,
            "iqr": float(iqr) if pd.notna(iqr) else np.nan,
            "skewness": float(aggregate.get("skewness")) if aggregate.get("skewness") is not None else np.nan,
            "kurtosis": float(aggregate.get("kurtosis")) if aggregate.get("kurtosis") is not None else np.nan,
            "median": float(median) if pd.notna(median) else np.nan,
            "mad": float(mad) if pd.notna(mad) else np.nan,
            "zero_rate": float(zero_rate) if zero_rate is not None else np.nan,
            "negative_rate": float(negative_rate) if negative_rate is not None else np.nan,
            "positive_rate": float(positive_rate) if positive_rate is not None else np.nan,
            "outlier_share": float(outlier_share),
            "is_numeric": 1,
            "avg_string_length": np.nan,
            "std_string_length": np.nan,
            "top_value_share": np.nan,
            "second_value_share": np.nan,
            "digit_ratio": np.nan,
            "alpha_ratio": np.nan,
        }
    else:
        series_df = df.select(F.col(column_name).cast("string").alias("value")).where(F.col("value").isNotNull())
        length_df = series_df.select(F.length(F.col("value")).alias("length"))
        aggregate = length_df.agg(
            F.mean("length").alias("avg_string_length"),
            F.stddev_samp("length").alias("std_string_length"),
        ).first().asDict() if non_null_count else {"avg_string_length": np.nan, "std_string_length": np.nan}
        top_rows = series_df.groupBy("value").count().orderBy(F.desc("count")).limit(2).collect()
        top_share = top_rows[0]["count"] / max(non_null_count, 1) if len(top_rows) > 0 else 0.0
        second_share = top_rows[1]["count"] / max(non_null_count, 1) if len(top_rows) > 1 else 0.0
        digit_ratio = series_df.select(F.mean(F.when(F.col("value").rlike(r"\d"), 1).otherwise(0)).alias("rate")).first()["rate"]
        alpha_ratio = series_df.select(
            F.mean(F.when(F.col("value").rlike(r"[A-Za-zÀ-ÿ]"), 1).otherwise(0)).alias("rate")
        ).first()["rate"]

        features = {
            **base,
            "mean": np.nan,
            "std": np.nan,
            "min": np.nan,
            "max": np.nan,
            "iqr": np.nan,
            "skewness": np.nan,
            "kurtosis": np.nan,
            "median": np.nan,
            "mad": np.nan,
            "zero_rate": np.nan,
            "negative_rate": np.nan,
            "positive_rate": np.nan,
            "outlier_share": np.nan,
            "is_numeric": 0,
            "avg_string_length": float(aggregate.get("avg_string_length")) if aggregate.get("avg_string_length") is not None else np.nan,
            "std_string_length": float(aggregate.get("std_string_length")) if aggregate.get("std_string_length") is not None else np.nan,
            "top_value_share": float(top_share),
            "second_value_share": float(second_share),
            "digit_ratio": float(digit_ratio) if digit_ratio is not None else np.nan,
            "alpha_ratio": float(alpha_ratio) if alpha_ratio is not None else np.nan,
        }

    features["entropy"] = _spark_column_entropy(df, column_name)
    return features


def _spark_profile_dataset(df: DataFrame, dataset_name: str, protected_columns: dict[str, str]) -> pd.DataFrame:
    rows = []
    for field in df.schema.fields:
        if field.name in protected_columns:
            continue
        rows.append(_spark_profile_column(df, field.name, dataset_name))
    return pd.DataFrame(rows)


def _threshold_from_detector(detector, scores: np.ndarray) -> float:
    if getattr(detector, "threshold", None) is not None:
        return float(detector.threshold)
    if len(scores) == 0:
        return 0.0
    return float(np.percentile(scores, 90))


def _resolve_model_entry(registry: dict) -> dict | None:
    model_entry = registry.get("model")
    if isinstance(model_entry, dict) and model_entry.get("artifact_path"):
        return model_entry

    if isinstance(registry.get("artifact_path"), str):
        return {
            "artifact_path": registry["artifact_path"],
            "model_name": registry.get("model_name", "unknown"),
            "feature_cols": registry.get("feature_cols"),
            "protected_columns": registry.get("protected_columns", []),
            "scope": registry.get("scope", "legacy"),
        }

    benchmark = registry.get("benchmark")
    if isinstance(benchmark, dict):
        candidates = benchmark.get("by_model")
        if isinstance(candidates, list) and candidates:
            def _benchmark_score(entry: dict) -> tuple[float, float, float]:
                f1 = entry.get("f1_mean", 0.0) or 0.0
                precision = entry.get("precision_mean", 0.0) or 0.0
                recall = entry.get("recall_mean", 0.0) or 0.0
                return float(f1), float(precision), float(recall)

            best = max(candidates, key=_benchmark_score)
            if isinstance(best, dict) and best.get("artifact_path"):
                return best
    return None


def _build_profile_explanations(detector, row: pd.Series, score: float) -> list[str]:
    if hasattr(detector, "explain_profile_row"):
        try:
            return list(detector.explain_profile_row(row, score))
        except Exception:
            pass

    def as_float(key: str) -> float:
        value = row.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float("nan")

    reasons: list[str] = []
    missing_rate = as_float("missing_rate")
    cardinality_ratio = as_float("cardinality_ratio")
    non_null_cardinality_ratio = as_float("non_null_cardinality_ratio")
    top_value_share = as_float("top_value_share")
    is_numeric = int(row.get("is_numeric", 0) or 0) == 1

    if np.isfinite(missing_rate) and missing_rate >= 0.25:
        reasons.append("beaucoup de valeurs manquantes")
    if np.isfinite(non_null_cardinality_ratio) and non_null_cardinality_ratio >= 0.95:
        if np.isfinite(top_value_share) and top_value_share <= 0.2:
            reasons.append("forte unicité, ressemble à un identifiant")
        else:
            reasons.append("quasi toutes les valeurs sont distinctes")
    elif np.isfinite(cardinality_ratio) and cardinality_ratio <= 0.05:
        reasons.append("faible diversité, proche d'une colonne constante")
    outlier_share = as_float("outlier_share")
    if is_numeric and np.isfinite(outlier_share) and outlier_share >= 0.2:
        reasons.append("présence d'outliers marqués")
    if not reasons:
        reasons.append("profil globalement cohérent")
    return reasons


def run(spark: SparkSession, df: DataFrame, rules: Any = None) -> List[Dict[str, Any]]:
    """
    ML column-risk validator.

    It profiles each column, loads the single global detector when available,
    and returns one standardized check per profiled column.
    """
    registry = _load_registry()
    if not registry:
        return [
            {
                "type de test": "ml_profile",
                "statut": "ignoré",
                "colonne testée": "N/A",
                "nombre": 0,
                "ratio": "0/0",
                "exemples": ["Aucun registre de modèles ML trouvé"],
            }
        ]

    if not df.columns:
        return [
            {
                "type de test": "ml_profile",
                "statut": "ignoré",
                "colonne testée": "N/A",
                "nombre": 0,
                "ratio": "0/0",
                "exemples": ["Dataset vide"],
            }
        ]

    entry = _resolve_model_entry(registry)
    if not entry:
        return [
            {
                "type de test": "ml_profile",
                "statut": "ignoré",
                "colonne testée": "N/A",
                "nombre": 0,
                "ratio": "0/0",
                "exemples": ["Aucun modèle ML global trouvé dans le registre"],
            }
        ]

    artifact_path = Path(entry["artifact_path"])
    if not artifact_path.exists():
        return [
            {
                "type de test": "ml_profile",
                "statut": "échoué",
                "colonne testée": "N/A",
                "nombre": 0,
                "ratio": "0/0",
                "exemples": [f"Artefact introuvable: {artifact_path}"],
            }
        ]

    detector = joblib.load(artifact_path)

    auto_protected = _spark_detect_protected_columns(df)
    registry_protected = {
        column_name: "registry_protected"
        for column_name in entry.get("protected_columns", [])
        if column_name in df.columns
    }
    protected_columns = {**auto_protected, **registry_protected}
    profile_df = _spark_profile_dataset(df, entry.get("scope", "global_profile"), protected_columns)

    if profile_df.empty:
        return [
            {
                "type de test": "ml_profile",
                "statut": "ignoré",
                "colonne testée": "N/A",
                "nombre": 0,
                "ratio": "0/0",
                "exemples": [
                    "Toutes les colonnes restantes ont été exclues avant le profiling Spark",
                    *[f"{col} -> {reason}" for col, reason in list(protected_columns.items())[:5]],
                ],
            }
        ]

    predictions = detector.predict(profile_df)
    scores = detector.anomaly_scores(profile_df)
    threshold = _threshold_from_detector(detector, scores)

    results: list[dict[str, Any]] = []
    cols = profile_df["column_name"].tolist()

    for idx, column_name in enumerate(cols):
        pred = int(predictions[idx])
        score = float(scores[idx]) if len(scores) > idx else 0.0
        status = "échoué" if pred == -1 else "réussi"
        message = "Profil atypique détecté" if pred == -1 else "Profil cohérent"
        reasons = _build_profile_explanations(detector, profile_df.iloc[idx], score)
        examples = [
            f"model={entry.get('model_name', 'unknown')}",
            f"score={score:.4f}",
            f"threshold={threshold:.4f}",
            *[f"raison={reason}" for reason in reasons],
        ]
        if column_name in protected_columns:
            examples.append(f"excluded={protected_columns[column_name]}")
        results.append(
            {
                "alerte": message if pred == -1 else None,
                "type de test": "ml_profile",
                "statut": status,
                "colonne testée": column_name,
                "nombre": 1 if pred == -1 else 0,
                "ratio": f"{1 if pred == -1 else 0}/1",
                "exemples": examples,
            }
        )

    return results

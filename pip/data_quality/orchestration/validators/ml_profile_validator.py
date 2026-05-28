from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd
from pyspark.sql import DataFrame, SparkSession

from settings.config_paths import BASE_DIR, ML_MODELS_DIR

from ml_model_factory import (
    build_profile_frame,
    drop_protected_columns,
    infer_family,
)


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


def _normalize_family_name(family: str) -> str:
    family_aliases = {
        "mixed": "mixed_structured",
        "mixed_structured": "mixed_structured",
        "categorical": "categorical_text",
        "categorical_text": "categorical_text",
        "numeric": "numeric",
    }
    return family_aliases.get(family, family)


def _pick_family_entry(registry: dict, family: str) -> dict | None:
    normalized_family = _normalize_family_name(family)

    for entry in registry.get("families", []):
        if entry.get("family") == normalized_family:
            return entry
    return None


def _infer_dataset_name(registry: dict | None, family: str) -> str:
    if not registry:
        return family
    entry = _pick_family_entry(registry, family)
    if entry:
        return entry.get("dataset_name") or family
    return family


def _to_pandas_profile(df: DataFrame, max_rows: int = 50000) -> pd.DataFrame:
    limited_df = df.limit(max_rows)
    return limited_df.toPandas()


def _threshold_from_detector(detector, scores: np.ndarray) -> float:
    if getattr(detector, "threshold", None) is not None:
        return float(detector.threshold)
    if len(scores) == 0:
        return 0.0
    return float(np.percentile(scores, 90))


def run(spark: SparkSession, df: DataFrame, rules: Any = None) -> List[Dict[str, Any]]:
    """
    ML column-risk validator.

    It profiles each column, routes the dataset to the best champion model by family,
    then returns one standardized check per profiled column.
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

    pdf = _to_pandas_profile(df)
    if pdf.empty:
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

    family = infer_family(pdf)
    entry = _pick_family_entry(registry, family)
    if not entry:
        return [
            {
                "type de test": f"ml_profile_{family}",
                "statut": "ignoré",
                "colonne testée": "N/A",
                "nombre": 0,
                "ratio": "0/0",
                "exemples": [f"Aucun modèle trouvé pour la famille '{family}'"],
            }
        ]

    artifact_path = Path(entry["artifact_path"])
    if not artifact_path.exists():
        return [
            {
                "type de test": f"ml_profile_{family}",
                "statut": "échoué",
                "colonne testée": "N/A",
                "nombre": 0,
                "ratio": "0/0",
                "exemples": [f"Artefact introuvable: {artifact_path}"],
            }
        ]

    detector = joblib.load(artifact_path)

    dataset_name = _infer_dataset_name(registry, family)
    profile_df = build_profile_frame(pdf, dataset_name)
    predictions = detector.predict(profile_df)
    scores = detector.anomaly_scores(profile_df)
    threshold = _threshold_from_detector(detector, scores)

    results: list[dict[str, Any]] = []
    cols = profile_df["column_name"].tolist()

    for idx, column_name in enumerate(cols):
        pred = int(predictions[idx])
        score = float(scores[idx]) if len(scores) > idx else 0.0
        status = "échoué" if pred == -1 else "réussi"
        message = "Signal ML de risque élevé" if pred == -1 else "Profil cohérent avec le modèle ML"
        examples = [
            f"family={family}",
            f"model={entry.get('model_name', 'unknown')}",
            f"score={score:.4f}",
            f"threshold={threshold:.4f}",
        ]
        results.append(
            {
                "alerte": message if pred == -1 else None,
                "type de test": f"ml_profile_{family}",
                "statut": status,
                "colonne testée": column_name,
                "nombre": 1 if pred == -1 else 0,
                "ratio": f"{1 if pred == -1 else 0}/1",
                "exemples": examples,
            }
        )

    return results

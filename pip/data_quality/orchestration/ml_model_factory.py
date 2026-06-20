from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.covariance import EllipticEnvelope
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from ml_profile_eval_utils import inject_anomalies, profile_dataset


FEATURE_COLS = [
    "missing_rate",
    "cardinality",
    "cardinality_ratio",
    "non_null_cardinality_ratio",
    "duplication_rate",
    "mean",
    "std",
    "min",
    "max",
    "iqr",
    "skewness",
    "kurtosis",
    "median",
    "mad",
    "zero_rate",
    "negative_rate",
    "positive_rate",
    "outlier_share",
    "is_numeric",
    "avg_string_length",
    "std_string_length",
    "top_value_share",
    "second_value_share",
    "digit_ratio",
    "alpha_ratio",
    "entropy",
]

_ID_NAME_RE = re.compile(r"(^|[^a-z0-9])(id|uuid|guid|key)([^a-z0-9]|$)")
_TIMESTAMP_NAME_RE = re.compile(r"(^|[^a-z0-9])(date|datetime|timestamp|time|created_at|updated_at)([^a-z0-9]|$)")
_TARGET_NAME_RE = re.compile(r"(^|[^a-z0-9])(target|label|class|churn|status|outcome)([^a-z0-9]|$)")


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    path: Path
    family: str
    anomaly_rate: float
    protected_columns: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class ColumnAnomalyDetector:
    family: str
    model_name: str
    feature_cols: list[str]
    imputer: SimpleImputer
    scaler: StandardScaler
    estimator: object
    contamination: float
    threshold: float | None = None
    metadata: dict | None = None

    def _prepare_features(self, profile_df: pd.DataFrame) -> np.ndarray:
        x = profile_df[self.feature_cols].copy()
        x_imputed = self.imputer.transform(x)
        return self.scaler.transform(x_imputed)

    def anomaly_scores(self, profile_df: pd.DataFrame) -> np.ndarray:
        x = self._prepare_features(profile_df)

        if self.model_name == "kmeans":
            centers = self.estimator.cluster_centers_
            distances = np.min(np.linalg.norm(x[:, None] - centers[None, :], axis=2), axis=1)
            return distances

        if hasattr(self.estimator, "decision_function"):
            scores = self.estimator.decision_function(x)
            return -np.asarray(scores)

        if hasattr(self.estimator, "score_samples"):
            scores = self.estimator.score_samples(x)
            return -np.asarray(scores)

        preds = self.estimator.predict(x)
        return np.where(preds == -1, 1.0, 0.0)

    def predict(self, profile_df: pd.DataFrame) -> np.ndarray:
        x = self._prepare_features(profile_df)
        scores = self.anomaly_scores(profile_df)

        if self.threshold is not None:
            return np.where(scores > self.threshold, -1, 1)

        if hasattr(self.estimator, "predict"):
            return np.asarray(self.estimator.predict(x))

        threshold = float(np.percentile(scores, 90))
        return np.where(scores > threshold, -1, 1)

    def to_payload(self) -> dict:
        return {
            "family": self.family,
            "model_name": self.model_name,
            "feature_cols": self.feature_cols,
            "contamination": self.contamination,
            "threshold": self.threshold,
            "metadata": self.metadata or {},
        }


def load_dataset(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def drop_protected_columns(df: pd.DataFrame, protected_columns: Iterable[str]) -> pd.DataFrame:
    protected = [col for col in protected_columns if col in df.columns]
    if not protected:
        return df.copy()
    return df.drop(columns=protected)


def detect_protected_columns(df: pd.DataFrame) -> dict[str, str]:
    """
    Heuristically identify columns that should be excluded before ML profiling.

    We keep the rules conservative so we only remove columns that are very likely
    to act as identifiers, timestamps, targets, or constant placeholders.
    """
    protected: dict[str, str] = {}

    for col in df.columns:
        series = df[col]
        normalized_name = re.sub(r"[^a-z0-9]+", "_", str(col).strip().lower())
        reasons: list[str] = []

        if series.isna().all():
            reasons.append("all_null")
        elif series.nunique(dropna=False) <= 1:
            reasons.append("constant")

        if pd.api.types.is_datetime64_any_dtype(series) or _TIMESTAMP_NAME_RE.search(normalized_name):
            reasons.append("timestamp_like")

        if _TARGET_NAME_RE.search(normalized_name):
            reasons.append("target_like")

        if _ID_NAME_RE.search(normalized_name):
            reasons.append("identifier_like")
        else:
            non_null = series.dropna()
            if len(non_null) >= 10:
                uniqueness_ratio = non_null.nunique(dropna=True) / max(len(non_null), 1)
                if uniqueness_ratio >= 0.98 and (
                    normalized_name.endswith("_id")
                    or normalized_name.endswith("id")
                    or normalized_name.endswith("_key")
                    or normalized_name.endswith("key")
                ):
                    reasons.append("high_cardinality_identifier")

        if reasons:
            protected[col] = ", ".join(dict.fromkeys(reasons))

    return protected


def infer_family(df: pd.DataFrame) -> str:
    if df.empty or not len(df.columns):
        return "mixed_structured"

    numeric_count = sum(pd.api.types.is_numeric_dtype(df[c]) for c in df.columns)
    datetime_count = sum(pd.api.types.is_datetime64_any_dtype(df[c]) for c in df.columns)
    object_count = len(df.columns) - numeric_count - datetime_count
    total = max(len(df.columns), 1)

    numeric_ratio = numeric_count / total
    datetime_ratio = datetime_count / total
    text_ratio = object_count / total

    if numeric_ratio >= 0.8 and datetime_ratio <= 0.1:
        return "numeric"
    if text_ratio >= 0.6 and numeric_ratio <= 0.4 and datetime_ratio <= 0.2:
        return "categorical_text"
    return "mixed"


def build_profile_frame(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    return profile_dataset(df, dataset_name)


def build_feature_matrix(profile_df: pd.DataFrame, feature_cols: list[str] | None = None):
    if feature_cols is None:
        feature_cols = [
            col
            for col in FEATURE_COLS
            if col in profile_df.columns and pd.api.types.is_numeric_dtype(profile_df[col])
        ]

    x = profile_df[feature_cols].copy()
    for col in feature_cols:
        if x[col].isna().all():
            x[col] = 0.0

    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    x_imputed = imputer.fit_transform(x)
    x_scaled = scaler.fit_transform(x_imputed)
    return x_scaled, imputer, scaler, feature_cols


def _model_scores(estimator: object, model_name: str, X: np.ndarray) -> np.ndarray:
    if model_name == "kmeans":
        centers = estimator.cluster_centers_
        return np.min(np.linalg.norm(X[:, None] - centers[None, :], axis=2), axis=1)

    if hasattr(estimator, "decision_function"):
        return -np.asarray(estimator.decision_function(X))

    if hasattr(estimator, "score_samples"):
        return -np.asarray(estimator.score_samples(X))

    preds = estimator.predict(X)
    return np.where(preds == -1, 1.0, 0.0)


def _dynamic_threshold(scores: np.ndarray, contamination: float) -> float:
    finite_scores = np.asarray(scores, dtype=float)
    finite_scores = finite_scores[np.isfinite(finite_scores)]
    if len(finite_scores) == 0:
        return 0.0
    if len(finite_scores) == 1:
        return float(finite_scores[0])

    contamination = float(np.clip(contamination, 0.01, 0.49))
    percentile_threshold = float(np.percentile(finite_scores, (1.0 - contamination) * 100.0))
    q1, q3 = np.percentile(finite_scores, [25.0, 75.0])
    iqr = float(q3 - q1)
    robust_threshold = float(q3 + 1.5 * iqr) if iqr > 0 else percentile_threshold
    return max(percentile_threshold, robust_threshold)


def _fit_candidate(X: np.ndarray, model_name: str, contamination: float, seed: int = 42):
    n_samples = len(X)
    if model_name == "isolation_forest":
        model = IsolationForest(
            contamination=contamination,
            random_state=seed,
            n_estimators=300,
        )
        model.fit(X)
        scores = _model_scores(model, model_name, X)
        return model, _dynamic_threshold(scores, contamination)

    if model_name == "local_outlier_factor":
        n_neighbors = min(20, max(2, n_samples - 1))
        model = LocalOutlierFactor(
            contamination=contamination,
            novelty=True,
            n_neighbors=n_neighbors,
        )
        model.fit(X)
        scores = _model_scores(model, model_name, X)
        return model, _dynamic_threshold(scores, contamination)

    if model_name == "one_class_svm":
        model = OneClassSVM(nu=max(0.01, min(0.25, contamination)), gamma="scale")
        model.fit(X)
        scores = _model_scores(model, model_name, X)
        return model, _dynamic_threshold(scores, contamination)

    if model_name == "elliptic_envelope":
        support_fraction = min(0.95, max(0.5, 1.0 - contamination))
        model = EllipticEnvelope(
            contamination=contamination,
            support_fraction=support_fraction,
            random_state=seed,
        )
        model.fit(X)
        scores = _model_scores(model, model_name, X)
        return model, _dynamic_threshold(scores, contamination)

    if model_name == "kmeans":
        if n_samples < 2:
            n_clusters = 1
        else:
            n_clusters = min(max(2, int(np.sqrt(n_samples))), n_samples)
        model = KMeans(n_clusters=n_clusters, random_state=seed, n_init=10)
        model.fit(X)
        distances = _model_scores(model, model_name, X)
        threshold = _dynamic_threshold(distances, contamination)
        return model, threshold

    raise ValueError(f"Unsupported model: {model_name}")


def evaluate_predictions(ground_truth: dict[str, bool], predictions, cols: list[str], model_name: str) -> dict:
    from sklearn.metrics import f1_score, precision_score, recall_score

    y_true = np.array([1 if ground_truth[col] else 0 for col in cols])
    y_pred = np.array([1 if p == -1 else 0 for p in predictions])
    return {
        "model": model_name,
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "detected_anomalies": int(y_pred.sum()),
        "true_anomalies": int(y_true.sum()),
    }


def train_detector(
    profile_df: pd.DataFrame,
    family: str,
    model_name: str,
    contamination: float,
    seed: int = 42,
) -> ColumnAnomalyDetector:
    X, imputer, scaler, feature_cols = build_feature_matrix(profile_df)
    estimator, threshold = _fit_candidate(X, model_name, contamination, seed=seed)
    return ColumnAnomalyDetector(
        family=family,
        model_name=model_name,
        feature_cols=feature_cols,
        imputer=imputer,
        scaler=scaler,
        estimator=estimator,
        contamination=contamination,
        threshold=threshold,
        metadata={"trained_at": datetime.now(timezone.utc).isoformat()},
    )


def benchmark_spec(
    spec: DatasetSpec,
    candidate_models: list[str],
    seeds: Iterable[int] = range(8),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = load_dataset(spec.path)
    df = drop_protected_columns(df, spec.protected_columns)

    clean_profile = build_profile_frame(df, spec.name)
    clean_result_rows: list[dict] = []
    detail_rows: list[dict] = []
    benchmark_rows: list[dict] = []

    for seed in seeds:
        corrupted_df, anomaly_mask, anomaly_details = inject_anomalies(
            df,
            anomaly_rate=spec.anomaly_rate,
            seed=seed,
            family=spec.family,
        )
        profile_df = build_profile_frame(corrupted_df, f"{spec.name}_seed_{seed}")
        X, imputer, scaler, feature_cols = build_feature_matrix(profile_df)
        column_names = profile_df["column_name"].tolist()

        benchmark_rows.append(
            {
                "dataset_name": spec.name,
                "family": spec.family,
                "seed": seed,
                "anomaly_rate": spec.anomaly_rate,
                "n_columns": len(df.columns),
                "n_target_columns": int(sum(anomaly_mask.values())),
                "feature_count": len(feature_cols),
            }
        )

        for model_name in candidate_models:
            estimator, threshold = _fit_candidate(X, model_name, contamination=spec.anomaly_rate, seed=seed)
            detector = ColumnAnomalyDetector(
                family=spec.family,
                model_name=model_name,
                feature_cols=feature_cols,
                imputer=imputer,
                scaler=scaler,
                estimator=estimator,
                contamination=spec.anomaly_rate,
                threshold=threshold,
            )
            predictions = detector.predict(profile_df)
            metrics = evaluate_predictions(anomaly_mask, predictions, column_names, model_name)
            metrics.update(
                {
                    "dataset_name": spec.name,
                    "family": spec.family,
                    "seed": seed,
                    "anomaly_rate": spec.anomaly_rate,
                    "feature_count": len(feature_cols),
                    "n_columns": len(column_names),
                    "n_target_columns": int(sum(anomaly_mask.values())),
                }
            )
            detail_rows.append(metrics)

        clean_result_rows.append(
            {
                "dataset_name": spec.name,
                "family": spec.family,
                "columns_profiled": len(clean_profile),
            }
        )

    detail = pd.DataFrame(detail_rows)
    summary = (
        detail.groupby(["family", "model"], as_index=False)
        .agg(
            precision_mean=("precision", "mean"),
            precision_std=("precision", "std"),
            recall_mean=("recall", "mean"),
            recall_std=("recall", "std"),
            f1_mean=("f1", "mean"),
            f1_std=("f1", "std"),
            detected_mean=("detected_anomalies", "mean"),
            true_anomalies_mean=("true_anomalies", "mean"),
        )
        .sort_values(["family", "f1_mean", "precision_mean", "recall_mean"], ascending=[True, False, False, False])
        .reset_index(drop=True)
    )

    benchmark = pd.DataFrame(benchmark_rows)
    clean = pd.DataFrame(clean_result_rows)
    return summary, detail, benchmark


def select_family_champions(summary: pd.DataFrame) -> pd.DataFrame:
    return (
        summary.sort_values(
            ["family", "f1_mean", "f1_std", "precision_mean"],
            ascending=[True, False, True, False],
        )
        .groupby("family", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )


def save_detector(detector: ColumnAnomalyDetector, output_dir: Path, dataset_name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{dataset_name}_{detector.model_name}_detector.joblib"
    joblib.dump(detector, path)
    return path


def save_registry(registry: dict, output_dir: Path, filename: str = "model_registry.json") -> Path:
    import json

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    with path.open("w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    return path

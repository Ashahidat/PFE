from __future__ import annotations

import math
import random
import warnings
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import entropy
from sklearn.cluster import DBSCAN, KMeans
from sklearn.covariance import EllipticEnvelope
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.neighbors import LocalOutlierFactor, NearestNeighbors
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM


def _safe_entropy(series: pd.Series) -> float:
    counts = series.value_counts(normalize=True, dropna=False)
    if len(counts) <= 1:
        return 0.0
    return float(entropy(counts))


def _string_stats(series: pd.Series) -> dict:
    as_str = series.astype("string")
    lengths = as_str.str.len().fillna(0)
    top_freq = as_str.value_counts(dropna=False, normalize=True).iloc[0] if len(as_str) else 0.0
    second_freq = as_str.value_counts(dropna=False, normalize=True).iloc[1] if len(as_str.value_counts(dropna=False, normalize=True)) > 1 else 0.0
    return {
        "avg_string_length": float(lengths.mean()) if len(lengths) else np.nan,
        "std_string_length": float(lengths.std()) if len(lengths) > 1 else np.nan,
        "top_value_share": float(top_freq),
        "second_value_share": float(second_freq),
        "digit_ratio": float(as_str.str.contains(r"\d", regex=True, na=False).mean()) if len(as_str) else 0.0,
        "alpha_ratio": float(as_str.str.contains(r"[A-Za-zÀ-ÿ]", regex=True, na=False).mean()) if len(as_str) else 0.0,
    }


def profile_column(series: pd.Series) -> dict:
    n = len(series)
    n_missing = int(series.isna().sum())
    non_null = series.dropna()
    cardinality = int(series.nunique(dropna=False))
    non_null_cardinality = int(series.nunique(dropna=True))
    denom = max(n, 1)
    non_null_denom = max(n - n_missing, 1)

    features = {
        "missing_rate": n_missing / denom,
        "cardinality": cardinality,
        "cardinality_ratio": cardinality / denom,
        "non_null_cardinality_ratio": non_null_cardinality / max(non_null_denom, 1),
        "duplication_rate": 1 - (non_null_cardinality / non_null_denom),
    }

    if pd.api.types.is_numeric_dtype(series):
        if len(non_null) > 0:
            q1 = float(non_null.quantile(0.25))
            q3 = float(non_null.quantile(0.75))
            median = float(non_null.median())
            mad = float(np.median(np.abs(non_null - median)))
            iqr = q3 - q1
            outlier_share = float(((non_null < (q1 - 1.5 * iqr)) | (non_null > (q3 + 1.5 * iqr))).mean()) if iqr > 0 else 0.0
            features.update({
                "mean": float(non_null.mean()),
                "std": float(non_null.std()) if len(non_null) > 1 else 0.0,
                "min": float(non_null.min()),
                "max": float(non_null.max()),
                "iqr": float(iqr),
                "skewness": float(non_null.skew()) if len(non_null) > 1 else 0.0,
                "kurtosis": float(non_null.kurtosis()) if len(non_null) > 3 else 0.0,
                "median": median,
                "mad": mad,
                "zero_rate": float((non_null == 0).mean()),
                "negative_rate": float((non_null < 0).mean()),
                "positive_rate": float((non_null > 0).mean()),
                "outlier_share": outlier_share,
                "is_numeric": 1,
                "avg_string_length": np.nan,
                "std_string_length": np.nan,
                "top_value_share": np.nan,
                "second_value_share": np.nan,
                "digit_ratio": np.nan,
                "alpha_ratio": np.nan,
            })
        else:
            features.update({
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
                "is_numeric": 1,
                "avg_string_length": np.nan,
                "std_string_length": np.nan,
                "top_value_share": np.nan,
                "second_value_share": np.nan,
                "digit_ratio": np.nan,
                "alpha_ratio": np.nan,
            })
    else:
        string_stats = _string_stats(non_null)
        features.update({
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
            **string_stats,
        })

    features["entropy"] = _safe_entropy(series)
    return features


def profile_dataset(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        row = profile_column(df[col])
        row["column_name"] = col
        row["dataset_name"] = dataset_name
        rows.append(row)
    return pd.DataFrame(rows)


def inject_anomalies(
    df: pd.DataFrame,
    anomaly_rate: float = 0.2,
    seed: int = 42,
) -> tuple[pd.DataFrame, dict[str, bool], pd.DataFrame]:
    rng = np.random.default_rng(seed)
    df_corrupted = df.copy()
    anomaly_mask: dict[str, bool] = {}
    anomaly_records: list[dict[str, object]] = []

    numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    categorical_cols = [col for col in df.columns if col not in numeric_cols]
    cols = list(df.columns)

    n_anomalies = max(1, int(round(len(cols) * anomaly_rate)))
    target_cols = list(rng.choice(cols, size=min(n_anomalies, len(cols)), replace=False))

    for col in cols:
        anomaly_mask[col] = col in target_cols

    for col in target_cols:
        is_numeric = col in numeric_cols
        if is_numeric:
            anomaly_type = rng.choice(
                ["missing", "duplicate", "outlier", "drift", "noise", "constant"],
                p=[0.16, 0.18, 0.26, 0.2, 0.12, 0.08],
            )
        else:
            anomaly_type = rng.choice(
                ["missing", "duplicate", "rare_category", "shuffle", "corrupt_text"],
                p=[0.2, 0.25, 0.2, 0.2, 0.15],
            )

        severity = float(rng.uniform(0.15, 0.6))
        n_rows = len(df_corrupted)
        affected = max(1, int(round(n_rows * severity * 0.15)))
        idx = rng.choice(n_rows, size=min(affected, n_rows), replace=False)

        if anomaly_type == "missing":
            df_corrupted.loc[df_corrupted.index[idx], col] = np.nan
        elif anomaly_type == "duplicate":
            mode = df_corrupted[col].mode(dropna=True)
            if len(mode) > 0:
                df_corrupted.loc[df_corrupted.index[idx], col] = mode.iloc[0]
        elif anomaly_type == "outlier" and is_numeric:
            col_std = float(df_corrupted[col].std(ddof=0) or 1.0)
            col_mean = float(df_corrupted[col].mean())
            scale = rng.uniform(8.0, 16.0)
            direction = rng.choice([-1.0, 1.0])
            df_corrupted.loc[df_corrupted.index[idx], col] = col_mean + direction * scale * col_std
        elif anomaly_type == "drift" and is_numeric:
            factor = rng.uniform(1.8, 8.0)
            offset = rng.uniform(50.0, 500.0)
            df_corrupted[col] = df_corrupted[col] * factor + offset
        elif anomaly_type == "noise" and is_numeric:
            noise = rng.normal(0, float(df_corrupted[col].std(ddof=0) or 1.0) * rng.uniform(2.0, 5.0), size=n_rows)
            df_corrupted[col] = df_corrupted[col] + noise
        elif anomaly_type == "constant" and is_numeric:
            replacement = float(df_corrupted[col].median()) if pd.notna(df_corrupted[col].median()) else 0.0
            df_corrupted.loc[df_corrupted.index[idx], col] = replacement
        elif anomaly_type == "rare_category" and not is_numeric:
            df_corrupted.loc[df_corrupted.index[idx], col] = f"__rare__{col}"
        elif anomaly_type == "shuffle" and not is_numeric:
            shuffled = df_corrupted[col].sample(frac=1.0, random_state=seed).to_numpy()
            df_corrupted[col] = shuffled
        elif anomaly_type == "corrupt_text" and not is_numeric:
            df_corrupted.loc[df_corrupted.index[idx], col] = df_corrupted.loc[df_corrupted.index[idx], col].astype(str) + "_corrupt"
        else:
            df_corrupted.loc[df_corrupted.index[idx], col] = np.nan

        anomaly_records.append(
            {
                "column": col,
                "type": anomaly_type,
                "is_numeric": is_numeric,
                "severity": severity,
                "rows_affected": len(idx),
            }
        )

    anomaly_details = pd.DataFrame(anomaly_records)
    return df_corrupted, anomaly_mask, anomaly_details


def prepare_features(profile_df: pd.DataFrame, feature_cols: Iterable[str] | None = None):
    if feature_cols is None:
        feature_cols = [
            col
            for col in profile_df.columns
            if col not in {"column_name", "dataset_name"}
            and pd.api.types.is_numeric_dtype(profile_df[col])
        ]

    feature_cols = list(feature_cols)
    x = profile_df[feature_cols].copy()
    for col in feature_cols:
        if x[col].isna().all():
            x[col] = 0.0

    imputer = SimpleImputer(strategy="median")
    scaler = StandardScaler()
    x_imputed = imputer.fit_transform(x)
    x_scaled = scaler.fit_transform(x_imputed)
    return x_scaled, imputer, scaler, feature_cols


def _run_isolation_forest(X, contamination: float):
    model = IsolationForest(contamination=contamination, random_state=42, n_estimators=300)
    labels = model.fit_predict(X)
    scores = -model.decision_function(X)
    return model, labels, scores


def _run_kmeans(X, contamination: float):
    n_samples = len(X)
    n_clusters = max(2, min(int(math.sqrt(max(n_samples, 2))), n_samples))
    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=20)
    labels_fit = model.fit_predict(X)
    distances = np.min(np.linalg.norm(X[:, None] - model.cluster_centers_[None, :], axis=2), axis=1)
    threshold = np.percentile(distances, (1 - contamination) * 100)
    labels = np.where(distances > threshold, -1, 1)
    return model, labels, distances


def _run_dbscan(X, contamination: float):
    n_neighbors = min(4, max(2, len(X) - 1))
    if len(X) <= 2:
        model = DBSCAN(eps=0.5, min_samples=2)
    else:
        nn = NearestNeighbors(n_neighbors=n_neighbors)
        nn.fit(X)
        kth_dist = nn.kneighbors(X)[0][:, -1]
        eps = float(np.clip(np.quantile(kth_dist, 0.85), 0.35, 2.5))
        min_samples = max(2, min(4, len(X) // 2))
        model = DBSCAN(eps=eps, min_samples=min_samples)
    labels_fit = model.fit_predict(X)
    scores = np.where(labels_fit == -1, 1.0, 0.0)
    labels = np.where(labels_fit == -1, -1, 1)
    return model, labels, scores


def _run_lof(X, contamination: float):
    n_neighbors = max(2, min(10, len(X) - 1))
    model = LocalOutlierFactor(n_neighbors=n_neighbors, contamination=contamination)
    labels = model.fit_predict(X)
    scores = -model.negative_outlier_factor_
    return model, labels, scores


def _run_one_class_svm(X, contamination: float):
    model = OneClassSVM(nu=contamination, kernel="rbf", gamma="scale")
    labels = model.fit_predict(X)
    scores = -model.decision_function(X)
    return model, labels, scores


def _run_elliptic_envelope(X, contamination: float):
    support_fraction = min(0.95, max(0.5, 1 - contamination))
    model = EllipticEnvelope(contamination=contamination, support_fraction=support_fraction, random_state=42)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        labels = model.fit_predict(X)
        scores = -model.decision_function(X)
    return model, labels, scores


def run_model_suite(X, contamination: float = 0.2):
    return OrderedDict(
        [
            ("IsolationForest", _run_isolation_forest(X, contamination)),
            ("LocalOutlierFactor", _run_lof(X, contamination)),
            ("KMeans", _run_kmeans(X, contamination)),
            ("DBSCAN", _run_dbscan(X, contamination)),
            ("OneClassSVM", _run_one_class_svm(X, contamination)),
            ("EllipticEnvelope", _run_elliptic_envelope(X, contamination)),
        ]
    )


def evaluate_predictions(ground_truth: dict[str, bool], predictions, cols: list[str], model_name: str) -> dict:
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


def benchmark_dataset(
    df: pd.DataFrame,
    dataset_name: str,
    *,
    anomaly_rate: float = 0.2,
    contamination: float = 0.2,
    seeds: Iterable[int] = range(5),
):
    run_rows: list[dict[str, object]] = []
    per_seed_profiles: list[pd.DataFrame] = []

    for seed in seeds:
        corrupted_df, anomaly_mask, anomaly_details = inject_anomalies(df, anomaly_rate=anomaly_rate, seed=seed)
        profile_df = profile_dataset(corrupted_df, f"{dataset_name}_seed_{seed}")
        X, imputer, scaler, feature_cols = prepare_features(profile_df)
        model_suite = run_model_suite(X, contamination=contamination)
        column_names = profile_df["column_name"].tolist()

        per_seed_profiles.append(
            pd.DataFrame(
                {
                    "dataset_name": dataset_name,
                    "seed": seed,
                    "anomaly_rate": anomaly_rate,
                    "n_columns": len(df.columns),
                    "n_target_columns": int(sum(anomaly_mask.values())),
                },
                index=[0],
            )
        )

        for model_name, (_, labels, scores) in model_suite.items():
            metrics = evaluate_predictions(anomaly_mask, labels, column_names, model_name)
            metrics.update(
                {
                    "dataset_name": dataset_name,
                    "seed": seed,
                    "anomaly_rate": anomaly_rate,
                    "feature_count": len(feature_cols),
                    "n_columns": len(column_names),
                    "n_target_columns": int(sum(anomaly_mask.values())),
                }
            )
            run_rows.append(metrics)

    detail = pd.DataFrame(run_rows)
    summary = (
        detail.groupby("model", as_index=False)
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
        .sort_values(["f1_mean", "precision_mean", "recall_mean"], ascending=False)
        .reset_index(drop=True)
    )

    return summary, detail


def build_f1_plot(summary: pd.DataFrame, title: str):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 4))
    ordered = summary.sort_values("f1_mean", ascending=False)
    ax.bar(ordered["model"], ordered["f1_mean"], yerr=ordered["f1_std"].fillna(0.0), color="#4c78a8")
    ax.set_ylim(0, 1)
    ax.set_ylabel("F1 mean")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    return fig, ax

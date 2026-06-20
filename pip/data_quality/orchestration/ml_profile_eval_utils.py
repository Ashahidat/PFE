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


def _infer_family_from_frame(df: pd.DataFrame) -> str:
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
    return "mixed_structured"


def _select_target_columns(
    cols: list[str],
    numeric_cols: list[str],
    categorical_cols: list[str],
    *,
    family: str,
    n_anomalies: int,
    rng: np.random.Generator,
) -> list[str]:
    if n_anomalies <= 0:
        return []

    if family == "numeric":
        pool = numeric_cols or cols
        return list(rng.choice(pool, size=min(n_anomalies, len(pool)), replace=False))

    if family == "categorical_text":
        pool = categorical_cols or cols
        return list(rng.choice(pool, size=min(n_anomalies, len(pool)), replace=False))

    targets: list[str] = []
    if numeric_cols:
        numeric_share = max(1, int(round(n_anomalies * 0.4)))
        numeric_share = min(numeric_share, len(numeric_cols), n_anomalies)
        targets.extend(rng.choice(numeric_cols, size=numeric_share, replace=False).tolist())
    if categorical_cols and len(targets) < n_anomalies:
        remaining = n_anomalies - len(targets)
        categorical_share = min(remaining, len(categorical_cols))
        targets.extend(rng.choice(categorical_cols, size=categorical_share, replace=False).tolist())

    if len(targets) < n_anomalies:
        fallback_pool = [col for col in cols if col not in targets]
        if fallback_pool:
            remaining = min(n_anomalies - len(targets), len(fallback_pool))
            targets.extend(rng.choice(fallback_pool, size=remaining, replace=False).tolist())
    return targets


def _mutate_numeric_column(df_corrupted: pd.DataFrame, col: str, idx: np.ndarray, rng: np.random.Generator) -> dict[str, object]:
    series = pd.to_numeric(df_corrupted[col], errors="coerce").astype(float)
    df_corrupted[col] = series
    anomaly_type = rng.choice(
        ["missing", "duplicate", "outlier", "drift", "noise", "constant", "scale_shift", "sign_flip"],
        p=[0.14, 0.16, 0.18, 0.16, 0.12, 0.10, 0.12, 0.02],
    )

    if anomaly_type == "missing":
        df_corrupted.loc[df_corrupted.index[idx], col] = np.nan
    elif anomaly_type == "duplicate":
        mode = series.mode(dropna=True)
        if len(mode) > 0:
            df_corrupted.loc[df_corrupted.index[idx], col] = float(mode.iloc[0])
    elif anomaly_type == "outlier":
        col_std = float(series.std(ddof=0) or 1.0)
        col_mean = float(series.mean())
        scale = rng.uniform(6.0, 12.0)
        direction = rng.choice([-1.0, 1.0])
        df_corrupted.loc[df_corrupted.index[idx], col] = col_mean + direction * scale * col_std
    elif anomaly_type == "drift":
        factor = rng.uniform(1.2, 3.5)
        offset = rng.uniform(-0.5, 0.5) * float(series.std(ddof=0) or 1.0)
        df_corrupted[col] = series * factor + offset
    elif anomaly_type == "noise":
        sigma = float(series.std(ddof=0) or 1.0) * rng.uniform(0.8, 2.5)
        noise = rng.normal(0, sigma, size=len(series))
        df_corrupted[col] = series + noise
    elif anomaly_type == "constant":
        replacement = float(series.median()) if pd.notna(series.median()) else 0.0
        df_corrupted.loc[df_corrupted.index[idx], col] = replacement
    elif anomaly_type == "scale_shift":
        factor = rng.uniform(0.4, 2.2)
        offset = rng.uniform(-2.0, 2.0) * float(series.std(ddof=0) or 1.0)
        df_corrupted[col] = series * factor + offset
    elif anomaly_type == "sign_flip":
        df_corrupted.loc[df_corrupted.index[idx], col] = -series.iloc[idx].to_numpy()

    return {
        "type": anomaly_type,
        "is_numeric": True,
    }


def _mutate_categorical_column(df_corrupted: pd.DataFrame, col: str, idx: np.ndarray, rng: np.random.Generator) -> dict[str, object]:
    series = df_corrupted[col].astype("string")
    anomaly_type = rng.choice(
        ["missing", "duplicate", "rare_category", "shuffle", "corrupt_text", "case_shift", "whitespace", "merge_categories"],
        p=[0.14, 0.16, 0.18, 0.12, 0.12, 0.10, 0.08, 0.10],
    )

    if anomaly_type == "missing":
        df_corrupted.loc[df_corrupted.index[idx], col] = pd.NA
    elif anomaly_type == "duplicate":
        mode = series.mode(dropna=True)
        if len(mode) > 0:
            df_corrupted.loc[df_corrupted.index[idx], col] = mode.iloc[0]
    elif anomaly_type == "rare_category":
        df_corrupted.loc[df_corrupted.index[idx], col] = f"__rare__{col}"
    elif anomaly_type == "shuffle":
        shuffled = series.sample(frac=1.0, random_state=int(rng.integers(0, 1_000_000))).to_numpy()
        df_corrupted[col] = shuffled
    elif anomaly_type == "corrupt_text":
        corrupted = series.iloc[idx].fillna("").astype(str) + "_corrupt"
        df_corrupted.loc[df_corrupted.index[idx], col] = corrupted.to_numpy()
    elif anomaly_type == "case_shift":
        values = series.iloc[idx].fillna("").astype(str)
        transformed = []
        for value in values:
            mode = rng.choice(["lower", "upper", "title"])
            transformed.append(getattr(value, mode)())
        df_corrupted.loc[df_corrupted.index[idx], col] = transformed
    elif anomaly_type == "whitespace":
        values = series.iloc[idx].fillna("").astype(str)
        df_corrupted.loc[df_corrupted.index[idx], col] = ["  " + value.strip() + "  " for value in values]
    elif anomaly_type == "merge_categories":
        mode = series.mode(dropna=True)
        if len(mode) > 0:
            replacement = mode.iloc[0]
        else:
            replacement = "__merged__"
        df_corrupted.loc[df_corrupted.index[idx], col] = replacement

    return {
        "type": anomaly_type,
        "is_numeric": False,
    }


def _apply_mixed_relationship_breaks(
    df_corrupted: pd.DataFrame,
    numeric_targets: list[str],
    categorical_targets: list[str],
    rng: np.random.Generator,
) -> list[dict[str, object]]:
    """
    Add a small amount of cross-field corruption for mixed datasets.

    The goal is to break row-level consistency between numeric and categorical
    columns without relying on synthetic labels that are too obvious.
    """
    anomaly_records: list[dict[str, object]] = []
    if not numeric_targets or not categorical_targets or len(df_corrupted) < 3:
        return anomaly_records

    n_pairs = min(len(numeric_targets), len(categorical_targets), max(1, round(len(df_corrupted.columns) * 0.15)))
    paired_numeric = numeric_targets[:n_pairs]
    paired_categorical = categorical_targets[:n_pairs]

    for num_col, cat_col in zip(paired_numeric, paired_categorical):
        row_count = len(df_corrupted)
        affected = max(2, int(round(row_count * rng.uniform(0.08, 0.22))))
        affected = min(affected, row_count)
        idx = rng.choice(row_count, size=min(affected, row_count), replace=False)

        num_values = pd.to_numeric(df_corrupted[num_col], errors="coerce").astype(float)
        cat_values = df_corrupted[cat_col].astype("string")
        donor_rows = rng.choice(row_count, size=len(idx), replace=False)

        # Keep the corruption plausible by moving values between unrelated rows,
        # then apply a small drift on top of the swap.
        swapped_num = num_values.iloc[donor_rows].to_numpy()
        df_corrupted.loc[df_corrupted.index[idx], num_col] = swapped_num

        drift_scale = rng.uniform(0.7, 1.5)
        drift_shift = rng.uniform(-0.35, 0.35) * float(num_values.std(ddof=0) or 1.0)
        df_corrupted.loc[df_corrupted.index[idx], num_col] = pd.to_numeric(
            df_corrupted.loc[df_corrupted.index[idx], num_col], errors="coerce"
        ).astype(float) * drift_scale + drift_shift

        # Local record corruption: a handful of rows become incomplete, which is
        # common in real mixed schemas where a single record is partially broken.
        missing_count = max(1, len(idx) // 4)
        missing_idx = idx[:missing_count]
        if len(missing_idx) > 0:
            df_corrupted.loc[df_corrupted.index[missing_idx], num_col] = np.nan

        swapped_cat = cat_values.iloc[donor_rows].fillna("").astype(str).to_numpy()
        alias_style = rng.choice(["case", "space", "suffix", "rare"], p=[0.35, 0.25, 0.25, 0.15])
        if alias_style == "case":
            mutated_cat = [value.upper() if i % 2 == 0 else value.lower() for i, value in enumerate(swapped_cat)]
        elif alias_style == "space":
            mutated_cat = [f" {value.strip()} " for value in swapped_cat]
        elif alias_style == "suffix":
            mutated_cat = [f"{value}_mix" for value in swapped_cat]
        else:
            mode = cat_values.mode(dropna=True)
            rare_value = mode.iloc[0] if len(mode) > 0 else f"__mixed__{cat_col}"
            mutated_cat = [rare_value for _ in range(len(swapped_cat))]
        df_corrupted.loc[df_corrupted.index[idx], cat_col] = mutated_cat

        anomaly_records.extend(
            [
                {
                    "column": num_col,
                    "paired_column": cat_col,
                    "type": "mixed_relationship_break",
                    "is_numeric": True,
                    "severity": float(rng.uniform(0.2, 0.45)),
                    "rows_affected": len(idx),
                },
                {
                    "column": cat_col,
                    "paired_column": num_col,
                    "type": "mixed_relationship_break",
                    "is_numeric": False,
                    "severity": float(rng.uniform(0.2, 0.45)),
                    "rows_affected": len(idx),
                },
            ]
        )

    return anomaly_records


def inject_anomalies(
    df: pd.DataFrame,
    anomaly_rate: float = 0.2,
    seed: int = 42,
    family: str | None = None,
) -> tuple[pd.DataFrame, dict[str, bool], pd.DataFrame]:
    rng = np.random.default_rng(seed)
    df_corrupted = df.copy()
    anomaly_mask: dict[str, bool] = {}
    anomaly_records: list[dict[str, object]] = []

    numeric_cols = [col for col in df.columns if pd.api.types.is_numeric_dtype(df[col])]
    categorical_cols = [col for col in df.columns if col not in numeric_cols]
    cols = list(df.columns)
    family = family or _infer_family_from_frame(df)

    n_anomalies = max(1, int(round(len(cols) * anomaly_rate)))
    target_cols = _select_target_columns(
        cols,
        numeric_cols,
        categorical_cols,
        family=family,
        n_anomalies=min(n_anomalies, len(cols)),
        rng=rng,
    )

    for col in cols:
        anomaly_mask[col] = col in target_cols

    for col in target_cols:
        is_numeric = col in numeric_cols
        if is_numeric:
            # Cast once so injected float anomalies do not trigger dtype warnings on int columns.
            df_corrupted[col] = pd.to_numeric(df_corrupted[col], errors="coerce").astype(float)

        severity = float(rng.uniform(0.15, 0.6))
        n_rows = len(df_corrupted)
        if family == "mixed_structured":
            severity = float(rng.uniform(0.12, 0.5))
        affected = max(1, int(round(n_rows * severity * 0.12)))
        idx = rng.choice(n_rows, size=min(affected, n_rows), replace=False)

        if is_numeric:
            mutation = _mutate_numeric_column(df_corrupted, col, idx, rng)
        else:
            mutation = _mutate_categorical_column(df_corrupted, col, idx, rng)

        anomaly_records.append(
            {
                "column": col,
                "type": mutation["type"],
                "is_numeric": mutation["is_numeric"],
                "severity": severity,
                "rows_affected": len(idx),
            }
        )

    if family == "mixed_structured":
        target_numeric_cols = [col for col in target_cols if col in numeric_cols]
        target_categorical_cols = [col for col in target_cols if col in categorical_cols]
        anomaly_records.extend(
            _apply_mixed_relationship_breaks(df_corrupted, target_numeric_cols, target_categorical_cols, rng)
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

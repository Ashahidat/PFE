from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
try:
    from pyspark.sql import SparkSession
except Exception:  # pragma: no cover - Spark is optional in constrained envs
    SparkSession = None


ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_QUALITY_DIR = ROOT_DIR / "pip" / "data_quality"
ORCHESTRATION_DIR = DATA_QUALITY_DIR / "orchestration"

for path in (str(DATA_QUALITY_DIR), str(ORCHESTRATION_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from settings.config_paths import ML_MODELS_DIR
from ml_model_factory import (
    ColumnAnomalyDetector,
    DatasetSpec,
    build_profile_frame,
    _fit_candidate,
    save_detector,
    save_registry,
    select_global_champion,
    train_detector,
)
from ml_profile_eval_utils import (
    evaluate_predictions,
    inject_anomalies,
    profile_dataset,
    prepare_features,
)


ADULT_COLUMNS = [
    "age",
    "workclass",
    "fnlwgt",
    "education",
    "education_num",
    "marital_status",
    "occupation",
    "relationship",
    "race",
    "sex",
    "capital_gain",
    "capital_loss",
    "hours_per_week",
    "native_country",
    "income",
]

MUSHROOM_COLUMNS = [
    "class",
    "cap_shape",
    "cap_surface",
    "cap_color",
    "bruises",
    "odor",
    "gill_attachment",
    "gill_spacing",
    "gill_size",
    "gill_color",
    "stalk_shape",
    "stalk_root",
    "stalk_surface_above_ring",
    "stalk_surface_below_ring",
    "stalk_color_above_ring",
    "stalk_color_below_ring",
    "veil_type",
    "veil_color",
    "ring_number",
    "ring_type",
    "spore_print_color",
    "population",
    "habitat",
]


DEFAULT_DATASET_SPECS = [
    DatasetSpec(
        name="creditcard",
        path=ROOT_DIR / "data" / "creditcard.csv",
        anomaly_rate=0.18,
        protected_columns=("Class",),
        tags=("benchmark", "numeric"),
    ),
    DatasetSpec(
        name="adult",
        path=ROOT_DIR / "data" / "datasets_benchmark2_off" / "adult.data",
        anomaly_rate=0.22,
        protected_columns=("income",),
        tags=("benchmark", "hybrid"),
    ),
    DatasetSpec(
        name="mushroom",
        path=ROOT_DIR / "data" / "datasets_benchmark2_off" / "agaricus-lepiota.data",
        anomaly_rate=0.18,
        protected_columns=("class",),
        tags=("benchmark", "textual"),
    ),
]

DEFAULT_CANDIDATE_MODELS = [
    "isolation_forest",
    "local_outlier_factor",
    "one_class_svm",
]


def _spark_session(app_name: str = "ml_profile_training") -> Optional["SparkSession"]:
    if SparkSession is None:
        return None

    def _build_session() -> "SparkSession":
        return (
            SparkSession.builder.master("local[*]")
            .appName(app_name)
            .config("spark.driver.host", "127.0.0.1")
            .config("spark.driver.bindAddress", "127.0.0.1")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.ui.enabled", "false")
            .getOrCreate()
        )

    try:
        return _build_session()
    except Exception:
        return None


def _load_clean_dataset_as_pandas(
    spark: Optional["SparkSession"],
    spec: DatasetSpec,
    *,
    max_rows: int,
) -> pd.DataFrame:
    """
    Load the dataset through Spark and only materialize a bounded sample to pandas.

    This keeps the Spark path for large CSVs while preventing an accidental
    driver-side blowup when the raw dataset is very wide or very large.
    """
    name = spec.path.name.lower()

    if name == "adult.test":
        df = pd.read_csv(
            spec.path,
            header=None,
            names=ADULT_COLUMNS,
            skiprows=1,
            skipinitialspace=True,
            na_values="?",
            engine="python",
        )
        df["income"] = df["income"].astype(str).str.replace(".", "", regex=False)
    elif name == "adult.data":
        adult_test_path = spec.path.with_name("adult.test")
        adult_train = pd.read_csv(
            spec.path,
            header=None,
            names=ADULT_COLUMNS,
            skipinitialspace=True,
            na_values="?",
            engine="python",
        )
        adult_test = pd.read_csv(
            adult_test_path,
            header=None,
            names=ADULT_COLUMNS,
            skiprows=1,
            skipinitialspace=True,
            na_values="?",
            engine="python",
        )
        adult_test["income"] = adult_test["income"].astype(str).str.replace(".", "", regex=False)
        df = pd.concat([adult_train, adult_test], ignore_index=True)
    elif name == "agaricus-lepiota.data":
        df = pd.read_csv(
            spec.path,
            header=None,
            names=MUSHROOM_COLUMNS,
            na_values="?",
            engine="python",
        )
    else:
        if spark is None:
            df = pd.read_csv(spec.path)
            if spec.protected_columns:
                df = df.drop(columns=[col for col in spec.protected_columns if col in df.columns])
            return df.head(max_rows).copy()

        spark_df = (
            spark.read.option("header", True)
            .option("inferSchema", True)
            .csv(str(spec.path))
        )
        if spec.protected_columns:
            spark_df = spark_df.drop(*[col for col in spec.protected_columns if col in spark_df.columns])
        return spark_df.limit(max_rows).toPandas()

    if spec.protected_columns:
        df = df.drop(columns=[col for col in spec.protected_columns if col in df.columns])
    return df.head(max_rows).copy()


def _benchmark_dataset(
    df: pd.DataFrame,
    dataset_name: str,
    *,
    candidate_models: list[str],
    anomaly_rate: float,
    contamination: float,
    seeds: range,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    detail_rows: list[dict[str, object]] = []
    benchmark_rows: list[dict[str, object]] = []

    for seed in seeds:
        corrupted_df, anomaly_mask, _ = inject_anomalies(df, anomaly_rate=anomaly_rate, seed=seed)
        profile_df = profile_dataset(corrupted_df, f"{dataset_name}_seed_{seed}")
        X, imputer, scaler, feature_cols = prepare_features(profile_df)
        column_names = profile_df["column_name"].tolist()

        benchmark_rows.append(
            {
                "dataset_name": dataset_name,
                "seed": seed,
                "anomaly_rate": anomaly_rate,
                "n_columns": len(df.columns),
                "n_target_columns": int(sum(anomaly_mask.values())),
                "feature_count": len(feature_cols),
            }
        )

        for model_name in candidate_models:
            estimator, threshold = _fit_candidate(X, model_name, contamination=contamination, seed=seed)
            detector = ColumnAnomalyDetector(
                model_name=model_name,
                feature_cols=feature_cols,
                imputer=imputer,
                scaler=scaler,
                estimator=estimator,
                contamination=contamination,
                threshold=threshold,
            )
            labels = detector.predict(profile_df)
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
            detail_rows.append(metrics)

    detail = pd.DataFrame(detail_rows)
    summary = (
        detail.groupby(["model"], as_index=False)
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
        .sort_values(["f1_mean", "precision_mean", "recall_mean"], ascending=[False, False, False])
        .reset_index(drop=True)
    )

    benchmark = pd.DataFrame(benchmark_rows)
    return summary, detail, benchmark


def train_and_export(
    dataset_specs: list[DatasetSpec] | None = None,
    candidate_models: list[str] | None = None,
    *,
    output_dir: Path = ML_MODELS_DIR,
    seeds: range = range(8),
    max_training_rows: int = 50_000,
) -> dict[str, object]:
    dataset_specs = dataset_specs or DEFAULT_DATASET_SPECS
    candidate_models = candidate_models or DEFAULT_CANDIDATE_MODELS
    output_dir.mkdir(parents=True, exist_ok=True)

    spark = _spark_session()
    all_details: list[pd.DataFrame] = []
    all_benchmarks: list[pd.DataFrame] = []
    pooled_profiles: list[pd.DataFrame] = []

    try:
        for spec in dataset_specs:
            clean_df = _load_clean_dataset_as_pandas(spark, spec, max_rows=max_training_rows)
            pooled_profiles.append(build_profile_frame(clean_df, spec.name))

            _summary, detail, benchmark = _benchmark_dataset(
                clean_df,
                spec.name,
                candidate_models=candidate_models,
                anomaly_rate=spec.anomaly_rate,
                contamination=spec.anomaly_rate,
                seeds=seeds,
            )
            all_details.append(detail)
            all_benchmarks.append(benchmark)
    finally:
        if spark is not None:
            spark.stop()

    overall_detail = pd.concat(all_details, ignore_index=True)
    overall_benchmark = pd.concat(all_benchmarks, ignore_index=True)
    model_summary = (
        overall_detail.groupby(["model"], as_index=False)
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
        .sort_values(["f1_mean", "precision_mean", "recall_mean"], ascending=[False, False, False])
        .reset_index(drop=True)
    )

    global_summary = select_global_champion(overall_detail).to_frame().T
    champion_model = str(global_summary.iloc[0]["model"])
    pooled_profile_df = pd.concat(pooled_profiles, ignore_index=True)
    contamination = float(np.median([spec.anomaly_rate for spec in dataset_specs])) if dataset_specs else 0.1
    detector = train_detector(
        pooled_profile_df,
        model_name=champion_model,
        contamination=contamination,
    )
    artifact_path = save_detector(detector, output_dir, dataset_name="global_column_risk")

    registry: dict[str, object] = {
        "version": 2,
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "model": {
            "scope": "global",
            "model_name": detector.model_name,
            "artifact_path": str(artifact_path),
            "feature_cols": detector.feature_cols,
            "contamination": detector.contamination,
            "threshold": detector.threshold,
            "trained_on_datasets": [spec.name for spec in dataset_specs],
            "protected_columns": sorted({col for spec in dataset_specs for col in spec.protected_columns}),
            "tags": sorted({tag for spec in dataset_specs for tag in spec.tags}),
            "metrics": global_summary.iloc[0].to_dict(),
        },
        "benchmark": {
            "by_model": model_summary.to_dict(orient="records"),
            "datasets": [spec.name for spec in dataset_specs],
            "detail_rows": int(len(overall_detail)),
        },
    }

    summary_path = output_dir / "model_summary.csv"
    detail_path = output_dir / "model_detail.csv"
    benchmark_path = output_dir / "model_benchmark.csv"
    benchmark_summary_path = output_dir / "benchmark_summary.md"
    registry_path = save_registry(registry, output_dir)

    global_summary.to_csv(summary_path, index=False)
    overall_detail.to_csv(detail_path, index=False)
    overall_benchmark.to_csv(benchmark_path, index=False)
    model_summary_path = output_dir / "model_summary_by_model.csv"
    model_summary.to_csv(model_summary_path, index=False)

    top_rows = model_summary.head(5).to_dict(orient="records")
    benchmark_lines = [
        "# ML Benchmark Summary",
        "",
        f"- Champion: `{champion_model}`",
        f"- Datasets: {', '.join(spec.name for spec in dataset_specs)}",
        f"- Tested models: {', '.join(candidate_models)}",
        "",
        "## Top models",
        "",
        "| model | f1_mean | precision_mean | recall_mean |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in top_rows:
        benchmark_lines.append(
            f"| {row['model']} | {float(row['f1_mean']):.3f} | {float(row['precision_mean']):.3f} | {float(row['recall_mean']):.3f} |"
        )
    benchmark_summary_path.write_text("\n".join(benchmark_lines) + "\n", encoding="utf-8")

    return {
        "registry_path": str(registry_path),
        "summary_path": str(summary_path),
        "model_summary_path": str(model_summary_path),
        "benchmark_summary_path": str(benchmark_summary_path),
        "detail_path": str(detail_path),
        "benchmark_path": str(benchmark_path),
        "artifact_paths": {"global": str(artifact_path)},
        "champions": global_summary,
        "overall_summary": global_summary,
        "overall_detail": overall_detail,
        "overall_benchmark": overall_benchmark,
    }


def main() -> None:
    result = train_and_export()
    print(f"Registry saved to: {result['registry_path']}")
    print(f"Summary saved to: {result['summary_path']}")
    print(f"Detail saved to: {result['detail_path']}")
    print(f"Benchmark saved to: {result['benchmark_path']}")
    print(result["artifact_paths"])


if __name__ == "__main__":
    main()

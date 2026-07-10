from __future__ import annotations

import types
import sys
from pathlib import Path
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA_QUALITY_DIR = ROOT / "pip" / "data_quality"
ORCHESTRATION_DIR = DATA_QUALITY_DIR / "orchestration"
VALIDATORS_DIR = ORCHESTRATION_DIR / "validators"

for path in (str(DATA_QUALITY_DIR), str(ORCHESTRATION_DIR), str(VALIDATORS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _install_import_stubs() -> None:
    if "joblib" not in sys.modules:
        sys.modules["joblib"] = types.ModuleType("joblib")
    if "numpy" not in sys.modules:
        sys.modules["numpy"] = types.ModuleType("numpy")
    if "pandas" not in sys.modules:
        sys.modules["pandas"] = types.ModuleType("pandas")

    if "pyspark" not in sys.modules:
        pyspark_module = types.ModuleType("pyspark")
        pyspark_sql_module = types.ModuleType("pyspark.sql")
        pyspark_sql_module.DataFrame = object
        pyspark_sql_module.SparkSession = object
        pyspark_module.sql = pyspark_sql_module
        sys.modules["pyspark"] = pyspark_module
        sys.modules["pyspark.sql"] = pyspark_sql_module

    if "settings" not in sys.modules:
        settings_module = types.ModuleType("settings")
        config_paths_module = types.ModuleType("settings.config_paths")
        config_paths_module.BASE_DIR = DATA_QUALITY_DIR
        config_paths_module.ML_MODELS_DIR = DATA_QUALITY_DIR / "notebooks" / "artifacts" / "ml_models"
        settings_module.config_paths = config_paths_module
        sys.modules["settings"] = settings_module
        sys.modules["settings.config_paths"] = config_paths_module

    if "ml_model_factory" not in sys.modules:
        factory_module = types.ModuleType("ml_model_factory")
        factory_module.build_profile_frame = lambda *args, **kwargs: None
        factory_module.detect_protected_columns = lambda *args, **kwargs: {}
        factory_module.drop_protected_columns = lambda *args, **kwargs: None
        sys.modules["ml_model_factory"] = factory_module


_install_import_stubs()

from validators.ml_profile_validator import _build_profile_explanations, _resolve_model_entry


class ResolveModelEntryTest(unittest.TestCase):
    def test_prefers_global_model_entry(self) -> None:
        registry = {
            "model": {
                "artifact_path": "/tmp/global.joblib",
                "model_name": "isolation_forest",
                "protected_columns": ["id"],
            }
        }

        entry = _resolve_model_entry(registry)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["artifact_path"], "/tmp/global.joblib")

    def test_falls_back_to_best_benchmark_model(self) -> None:
        registry = {
            "benchmark": {
                "by_model": [
                    {
                        "model": "local_outlier_factor",
                        "artifact_path": "/tmp/lof.joblib",
                        "f1_mean": 0.61,
                        "precision_mean": 0.55,
                        "recall_mean": 0.66,
                    },
                    {
                        "model": "isolation_forest",
                        "artifact_path": "/tmp/if.joblib",
                        "f1_mean": 0.74,
                        "precision_mean": 0.7,
                        "recall_mean": 0.69,
                    },
                ]
            }
        }

        entry = _resolve_model_entry(registry)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["artifact_path"], "/tmp/if.joblib")


class ExplanationTest(unittest.TestCase):
    def test_builds_human_explanations_from_profile_row(self) -> None:
        class Detector:
            threshold = 1.0

            def explain_profile_row(self, row, score):
                return ["forte unicité", "score au-dessus du seuil"]

        row = pd.Series(
            {
                "missing_rate": 0.02,
                "cardinality_ratio": 0.98,
                "non_null_cardinality_ratio": 0.99,
                "top_value_share": 0.05,
                "is_numeric": 1,
            }
        )

        reasons = _build_profile_explanations(Detector(), row, 1.4)
        self.assertIn("forte unicité", reasons)


if __name__ == "__main__":
    unittest.main()

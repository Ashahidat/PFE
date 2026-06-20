from __future__ import annotations

import types
import sys
from pathlib import Path
import unittest


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
        factory_module.infer_family = lambda *args, **kwargs: "mixed"
        sys.modules["ml_model_factory"] = factory_module


_install_import_stubs()

from ml_profile_validator import _normalize_family_name, _pick_family_entry


class PickFamilyEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = {
            "families": [
                {
                    "family": "mixed_structured",
                    "dataset_name": "loan_approval",
                    "artifact_path": "/tmp/mixed.joblib",
                },
                {
                    "family": "categorical_text",
                    "dataset_name": "telco_churn",
                    "artifact_path": "/tmp/categorical.joblib",
                },
                {
                    "family": "numeric",
                    "dataset_name": "numeric_sample",
                    "artifact_path": "/tmp/numeric.joblib",
                },
            ]
        }

    def test_normalizes_mixed_family(self) -> None:
        self.assertEqual(_normalize_family_name("mixed"), "mixed_structured")
        entry = _pick_family_entry(self.registry, "mixed")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["family"], "mixed_structured")
        self.assertEqual(entry["dataset_name"], "loan_approval")

    def test_normalizes_categorical_family(self) -> None:
        self.assertEqual(_normalize_family_name("categorical"), "categorical_text")
        entry = _pick_family_entry(self.registry, "categorical")
        self.assertIsNotNone(entry)
        self.assertEqual(entry["family"], "categorical_text")
        self.assertEqual(entry["dataset_name"], "telco_churn")

    def test_unknown_family_returns_none(self) -> None:
        self.assertIsNone(_pick_family_entry(self.registry, "unknown"))


if __name__ == "__main__":
    unittest.main()

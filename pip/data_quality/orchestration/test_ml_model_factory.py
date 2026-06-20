from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
DATA_QUALITY_DIR = ROOT / "pip" / "data_quality"
ORCHESTRATION_DIR = DATA_QUALITY_DIR / "orchestration"

for path in (str(DATA_QUALITY_DIR), str(ORCHESTRATION_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from ml_model_factory import detect_protected_columns, drop_protected_columns, infer_family, _fit_candidate


class DetectProtectedColumnsTest(unittest.TestCase):
    def test_flags_identifiers_targets_timestamps_and_constants(self) -> None:
        df = pd.DataFrame(
            {
                "customer_id": [1, 2, 3, 4],
                "created_at": pd.to_datetime(
                    ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
                ),
                "Churn": ["yes", "no", "no", "yes"],
                "constant_flag": ["same", "same", "same", "same"],
                "feature": [10, 20, 30, 40],
            }
        )

        protected = detect_protected_columns(df)

        self.assertIn("customer_id", protected)
        self.assertIn("created_at", protected)
        self.assertIn("Churn", protected)
        self.assertIn("constant_flag", protected)
        self.assertNotIn("feature", protected)

    def test_drop_protected_columns_keeps_remaining_data(self) -> None:
        df = pd.DataFrame({"keep": [1, 2], "drop_me": [3, 4]})
        cleaned = drop_protected_columns(df, ["drop_me"])

        self.assertListEqual(list(cleaned.columns), ["keep"])


class InferFamilyTest(unittest.TestCase):
    def test_infers_numeric_family_for_numeric_heavy_schema(self) -> None:
        df = pd.DataFrame(
            {
                "a": [1, 2, 3],
                "b": [4.0, 5.5, 6.2],
                "c": [7, 8, 9],
                "d": [10, 11, 12],
                "label": ["x", "y", "z"],
            }
        )

        self.assertEqual(infer_family(df), "numeric")

    def test_infers_categorical_text_family_for_text_heavy_schema(self) -> None:
        df = pd.DataFrame(
            {
                "name": ["alice", "bob", "carol"],
                "city": ["paris", "lyon", "nice"],
                "segment": ["a", "b", "a"],
                "score": [1, 2, 3],
            }
        )

        self.assertEqual(infer_family(df), "categorical_text")


class DynamicThresholdTest(unittest.TestCase):
    def test_threshold_changes_with_dataset_scale(self) -> None:
        x_small = np.array([[0.0], [0.1], [0.2], [0.3], [0.4]])
        x_large = np.array([[0.0], [5.0], [10.0], [15.0], [20.0]])

        _, threshold_small = _fit_candidate(x_small, "kmeans", contamination=0.2, seed=42)
        _, threshold_large = _fit_candidate(x_large, "kmeans", contamination=0.2, seed=42)

        self.assertIsNotNone(threshold_small)
        self.assertIsNotNone(threshold_large)
        self.assertNotEqual(threshold_small, threshold_large)


if __name__ == "__main__":
    unittest.main()

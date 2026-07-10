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

from ml_model_factory import detect_protected_columns, drop_protected_columns, _fit_candidate, select_global_champion


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


class DynamicThresholdTest(unittest.TestCase):
    def test_threshold_changes_with_contamination(self) -> None:
        x = np.array([[0.0], [0.1], [0.2], [0.3], [1.8], [2.0], [2.2], [2.4]])

        _, threshold_small = _fit_candidate(x, "isolation_forest", contamination=0.1, seed=42)
        _, threshold_large = _fit_candidate(x, "isolation_forest", contamination=0.3, seed=42)

        self.assertIsNotNone(threshold_small)
        self.assertIsNotNone(threshold_large)
        self.assertNotEqual(threshold_small, threshold_large)


class GlobalChampionTest(unittest.TestCase):
    def test_selects_best_model_from_detail_table(self) -> None:
        detail = pd.DataFrame(
            [
                {"model": "lof", "precision": 0.55, "recall": 0.66, "f1": 0.60, "detected_anomalies": 3, "true_anomalies": 4},
                {"model": "if", "precision": 0.70, "recall": 0.69, "f1": 0.74, "detected_anomalies": 4, "true_anomalies": 4},
            ]
        )

        champion = select_global_champion(detail)

        self.assertEqual(champion["model"], "if")
        self.assertAlmostEqual(float(champion["f1_mean"]), 0.74, places=2)


if __name__ == "__main__":
    unittest.main()

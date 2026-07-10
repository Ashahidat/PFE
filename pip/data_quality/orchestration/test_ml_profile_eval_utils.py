from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
DATA_QUALITY_DIR = ROOT / "pip" / "data_quality"
ORCHESTRATION_DIR = DATA_QUALITY_DIR / "orchestration"

for path in (str(DATA_QUALITY_DIR), str(ORCHESTRATION_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from ml_profile_eval_utils import inject_anomalies, run_model_suite


class InjectAnomaliesCrossFieldTest(unittest.TestCase):
    def test_injects_cross_field_corruptions(self) -> None:
        df = pd.DataFrame(
            {
                "age": [21, 22, 23, 24, 25, 26, 27, 28],
                "income": [2000, 2100, 2200, 2300, 2400, 2500, 2600, 2700],
                "hours_per_week": [35, 36, 37, 38, 39, 40, 41, 42],
                "workclass": ["private", "public", "private", "self", "private", "public", "self", "private"],
                "education": ["hs", "ba", "hs", "ma", "ba", "hs", "ma", "ba"],
                "city": ["paris", "lyon", "nice", "paris", "lyon", "nice", "paris", "lyon"],
            }
        )

        corrupted_df, anomaly_mask, anomaly_details = inject_anomalies(
            df,
            anomaly_rate=0.6,
            seed=7,
        )

        self.assertFalse(corrupted_df.equals(df))
        self.assertIn("cross_field_break", set(anomaly_details["type"]))

        numeric_targets = anomaly_details.loc[anomaly_details["is_numeric"], "column"].unique().tolist()
        categorical_targets = anomaly_details.loc[~anomaly_details["is_numeric"], "column"].unique().tolist()

        self.assertTrue(numeric_targets)
        self.assertTrue(categorical_targets)
        self.assertTrue(any(not corrupted_df[col].equals(df[col]) for col in numeric_targets))
        self.assertTrue(any(not corrupted_df[col].equals(df[col]) for col in categorical_targets))
        self.assertGreater(sum(anomaly_mask.values()), 0)

    def test_model_suite_contains_three_models(self) -> None:
        X = pd.DataFrame(
            {
                "missing_rate": [0.0, 0.1, 0.2, 0.3],
                "cardinality": [1, 2, 3, 4],
                "entropy": [0.2, 0.3, 0.4, 0.5],
            }
        ).to_numpy()

        suite = run_model_suite(X, contamination=0.2)

        self.assertListEqual(
            list(suite.keys()),
            ["IsolationForest", "LocalOutlierFactor", "OneClassSVM"],
        )


if __name__ == "__main__":
    unittest.main()

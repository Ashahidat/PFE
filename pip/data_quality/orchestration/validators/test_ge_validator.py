from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DATA_QUALITY_DIR = ROOT / "pip" / "data_quality"
ORCHESTRATION_DIR = DATA_QUALITY_DIR / "orchestration"
VALIDATORS_DIR = ORCHESTRATION_DIR / "validators"

for path in (str(DATA_QUALITY_DIR), str(ORCHESTRATION_DIR), str(VALIDATORS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _install_import_stubs() -> None:
    if "pyspark" not in sys.modules:
        pyspark_module = types.ModuleType("pyspark")
        pyspark_sql_module = types.ModuleType("pyspark.sql")
        pyspark_sql_module.DataFrame = object
        pyspark_sql_module.SparkSession = object
        pyspark_module.sql = pyspark_sql_module
        sys.modules["pyspark"] = pyspark_module
        sys.modules["pyspark.sql"] = pyspark_sql_module

    if "validators.regex_validator" not in sys.modules:
        regex_module = types.ModuleType("validators.regex_validator")
        regex_module.run = lambda df, user_selection: {
            "regex": [
                {
                    "type de test": "regex_email",
                    "statut": "réussi",
                    "colonne testée": "email",
                    "nombre": 0,
                    "ratio": "0/10",
                    "exemples": [],
                }
            ]
        }
        sys.modules["validators.regex_validator"] = regex_module


_install_import_stubs()

from ge_validator import run


class FakeDataFrame:
    pass


class FakeSparkSession:
    pass


class GeValidatorTest(unittest.TestCase):
    def test_rewrites_regex_labels_to_ge(self) -> None:
        result = run(FakeSparkSession(), FakeDataFrame(), {"email": ["email"]})
        self.assertIn("ge", result)
        self.assertEqual(result["ge"][0]["type de test"], "ge_email")


if __name__ == "__main__":
    unittest.main()

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

        functions_module = types.ModuleType("pyspark.sql.functions")
        functions_module.col = lambda name: ("col", name)
        functions_module.lit = lambda value: ("lit", value)
        functions_module.trim = lambda value: ("trim", value)
        functions_module.length = lambda value: ("length", value)

        pyspark_sql_module.functions = functions_module
        pyspark_module.sql = pyspark_sql_module
        sys.modules["pyspark"] = pyspark_module
        sys.modules["pyspark.sql"] = pyspark_sql_module
        sys.modules["pyspark.sql.functions"] = functions_module

    if "pydeequ" not in sys.modules:
        pydeequ_module = types.ModuleType("pydeequ")
        checks_module = types.ModuleType("pydeequ.checks")
        verification_module = types.ModuleType("pydeequ.verification")

        class FakeCheck:
          calls: list[tuple[str, str]] = []

          def __init__(self, spark, level, name):
              self.spark = spark
              self.level = level
              self.name = name

          def hasCompleteness(self, column, predicate):
              self.calls.append(("hasCompleteness", column))
              return self

          def hasMin(self, column, predicate):
              self.calls.append(("hasMin", column))
              return self

          def hasMax(self, column, predicate):
              self.calls.append(("hasMax", column))
              return self

          def isContainedIn(self, column, values):
              self.calls.append(("isContainedIn", column))
              return self

          def isNonNegative(self, column):
              self.calls.append(("isNonNegative", column))
              return self

          def isPositive(self, column):
              self.calls.append(("isPositive", column))
              return self

          def hasMinLength(self, column, predicate):
              self.calls.append(("hasMinLength", column))
              return self

          def hasMaxLength(self, column, predicate):
              self.calls.append(("hasMaxLength", column))
              return self

        class FakeVerificationSuite:
            def __init__(self, spark):
                self.spark = spark

            def onData(self, df):
                self.df = df
                return self

            def addCheck(self, check):
                self.check = check
                return self

            def run(self):
                return types.SimpleNamespace(status="Success", checkResults={})

        checks_module.Check = FakeCheck
        checks_module.CheckLevel = types.SimpleNamespace(Error="Error")
        verification_module.VerificationSuite = FakeVerificationSuite
        verification_module.VerificationResult = object

        pydeequ_module.checks = checks_module
        pydeequ_module.verification = verification_module
        sys.modules["pydeequ"] = pydeequ_module
        sys.modules["pydeequ.checks"] = checks_module
        sys.modules["pydeequ.verification"] = verification_module


_install_import_stubs()

from deequ_validator import run
from pydeequ.checks import Check


class FakeDataFrame:
    def __init__(self, columns, total_rows=10):
        self.columns = columns
        self._total_rows = total_rows

    def count(self):
        return self._total_rows

    def filter(self, *_args, **_kwargs):
        return self

    def select(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def collect(self):
        return []


class FakeSparkSession:
    pass


class DeequValidatorTest(unittest.TestCase):
    def setUp(self) -> None:
        Check.calls = []

    def test_supports_complementary_constraint_types(self) -> None:
        df = FakeDataFrame(["amount", "label"])

        results = run(
            FakeSparkSession(),
            df,
            [
                {"type": "non_negative", "column": "amount"},
                {"type": "positive", "column": "amount"},
                {"type": "min_length", "column": "label", "threshold": 3},
                {"type": "max_length", "column": "label", "threshold": 12},
            ],
        )

        self.assertEqual([r["statut"] for r in results], ["réussi", "réussi", "réussi", "réussi"])
        self.assertIn(("isNonNegative", "amount"), Check.calls)
        self.assertIn(("isPositive", "amount"), Check.calls)
        self.assertIn(("hasMinLength", "label"), Check.calls)
        self.assertIn(("hasMaxLength", "label"), Check.calls)

    def test_skips_unknown_constraint_type(self) -> None:
        df = FakeDataFrame(["amount"])

        results = run(
            FakeSparkSession(),
            df,
            [{"type": "not_supported", "column": "amount"}],
        )

        self.assertEqual(results[0]["statut"], "ignoré")
        self.assertIn("non supporté", results[0]["exemples"][0])


if __name__ == "__main__":
    unittest.main()

import atexit
import os
import threading

os.environ["SPARK_VERSION"] = "3.3"

from pyspark.sql import SparkSession
import pydeequ

_spark_lock = threading.Lock()
_spark_session = None


def _build_spark():
    return (
        SparkSession.builder.appName("DataQualityApp")
        .config("spark.jars.packages", pydeequ.deequ_maven_coord)
        .config("spark.jars.excludes", pydeequ.f2j_maven_coord)
        .getOrCreate()
    )


def get_spark():
    global _spark_session
    with _spark_lock:
        if _spark_session is not None:
            try:
                jsc = _spark_session.sparkContext._jsc
                if jsc is not None:
                    _ = jsc.sc()
                    return _spark_session
            except Exception:
                try:
                    _spark_session.stop()
                except Exception:
                    pass
                _spark_session = None

        _spark_session = _build_spark()
        return _spark_session


class _SparkProxy:
    def __getattr__(self, item):
        return getattr(get_spark(), item)


spark = _SparkProxy()


def stop_spark():
    global _spark_session
    with _spark_lock:
        if _spark_session is not None:
            try:
                _spark_session.stop()
            except Exception:
                pass
            _spark_session = None


atexit.register(stop_spark)


# Dossiers
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_REACT_DIR = os.path.join(BASE_DIR, "..", "frontend-react")
REACT_DIST_DIR = os.path.join(FRONTEND_REACT_DIR, "dist")

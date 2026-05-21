import os
import signal
os.environ["SPARK_VERSION"] = "3.3"
from pyspark.sql import SparkSession
import atexit
import pydeequ


# Spark
spark = SparkSession.builder \
    .appName("DataQualityApp") \
    .config("spark.jars.packages", pydeequ.deequ_maven_coord) \
    .config("spark.jars.excludes", pydeequ.f2j_maven_coord) \
    .getOrCreate()

# Fermeture propre
def stop_spark():
    try:
        spark.stop()
    except:
        pass

atexit.register(stop_spark)


# Dossiers
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_REACT_DIR = os.path.join(BASE_DIR, "..", "frontend-react")
REACT_DIST_DIR = os.path.join(FRONTEND_REACT_DIR, "dist")

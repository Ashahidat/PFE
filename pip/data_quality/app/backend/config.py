import os
from pyspark.sql import SparkSession

# Spark
spark = SparkSession.builder.appName("DataQualityApp").getOrCreate()

# Dossiers
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

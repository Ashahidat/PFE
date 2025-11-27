from pyspark.sql import SparkSession
from atlasclient.client import Atlas

def connect_atlas():
    return Atlas("http://localhost:21000", username="admin", password="admin")

def register_dataset_with_columns(csv_path: str, dataset_name: str):
    spark = SparkSession.builder.getOrCreate()
    df = spark.read.option("header", True).csv(csv_path)

    client = connect_atlas()

    # Créer le dataset
    dataset_entity = {
        "typeName": "DataSet",
        "attributes": {
            "name": dataset_name,
            "qualifiedName": f"{dataset_name}@pfe",
            "description": f"Dataset Spark chargé depuis {csv_path}"
        }
    }

    resp = client.entity.create(data=dataset_entity)
    dataset_guid = resp['guid']

    # Créer les colonnes
    for field in df.schema.fields:
        column_entity = {
            "typeName": "spark_column",
            "attributes": {
                "name": field.name,
                "qualifiedName": f"{dataset_name}.{field.name}@pfe",
                "type": str(field.dataType),
                "dataset": {"guid": dataset_guid, "typeName": "DataSet"}
            }
        }
        client.entity.create(data=column_entity)

    return dataset_guid, [field.name for field in df.schema.fields]

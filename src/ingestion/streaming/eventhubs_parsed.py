# Databricks notebook source
import dlt
from pyspark.sql.functions import from_json, col, struct
from pyspark.sql.types import MapType, StringType

# COMMAND ----------

# Azure Event Hubs exposes a Kafka-compatible endpoint (port 9093).
# Requires an Event Hubs namespace on the Standard tier or above.
# The connection string is read from a Databricks secret scope - never hardcode it.
EH_NAMESPACE = "<eventhubs-namespace>"
EH_NAME = "<telematics-event-hub-name>"
SECRET_SCOPE = "<secret-scope>"
SECRET_KEY = "<eventhubs-connection-string-key>"

eventhubs_config = {
    "kafka.bootstrap.servers": f"{EH_NAMESPACE}.servicebus.windows.net:9093",
    "subscribe": EH_NAME,
    "kafka.security.protocol": "SASL_SSL",
    "kafka.sasl.mechanism": "PLAIN",
    "kafka.sasl.jaas.config": (
        "kafkashaded.org.apache.kafka.common.security.plain.PlainLoginModule required "
        'username="$ConnectionString" '
        f'password="{dbutils.secrets.get(SECRET_SCOPE, SECRET_KEY)}";'
    ),
    "startingOffsets": "earliest"
}

# COMMAND ----------

payload_schema = MapType(StringType(), StringType())

# COMMAND ----------

@dlt.table(
    name="telematics",
    comment="Parsed Event Hubs data as map with metadata struct",
    table_properties={"quality": "bronze"}
)
def bronze_table():
    raw_stream = (
        spark.readStream
        .format("kafka")
        .options(**eventhubs_config)
        .load()
    )

    parsed_stream = raw_stream.selectExpr(
        "CAST(value AS STRING) AS raw_json",
        "CAST(key AS STRING) AS partitionKey",
        "topic",
        "partition",
        "offset",
        "timestamp"
    ).withColumn(
        "decoded_data",
        from_json(col("raw_json"), payload_schema)
    ).withColumn(
        "stream_metadata",
        struct(
            col("partitionKey"),
            col("topic"),
            col("partition"),
            col("offset"),
            col("timestamp")
        )
    )

    return parsed_stream.select(
            col("decoded_data.chassis_no"),
            col("decoded_data.latitude"),
            col("decoded_data.longitude"),
            col("decoded_data.event_timestamp"),
            col("decoded_data.speed"),
            col("stream_metadata")
        )

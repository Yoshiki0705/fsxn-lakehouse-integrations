# Databricks notebook source
# Manufacturing Data Platform PoC — Kafka → Delta Lake Streaming Pipeline
#
# Architecture Reference: DES-010, ADR-001, ADR-010
# This notebook implements Structured Streaming from MSK to Unity Catalog Delta tables.
#
# Prerequisites:
#   - Unity Catalog catalog/schema created (run 01_setup_catalog.sql first)
#   - MSK cluster deployed and accessible from Databricks VPC
#   - Cluster configured with Unity Catalog access mode
#
# Configuration: Set widgets or use environment variables

# COMMAND ----------

# MAGIC %md
# MAGIC # Manufacturing Streaming Pipeline
# MAGIC Reads from Kafka topics and writes to Unity Catalog governed Delta tables.
# MAGIC - **Exactly-once semantics** via Delta Lake transaction log
# MAGIC - **Schema evolution** via mergeSchema
# MAGIC - **Deduplication** via foreachBatch + MERGE (quality events) or dropDuplicates (sensor data)

# COMMAND ----------

# Configuration — update these for your environment
KAFKA_BOOTSTRAP_SERVERS = spark.conf.get(
    "spark.manufacturing.kafka.bootstrap",
    "PLACEHOLDER:9098"  # Replace with actual MSK bootstrap servers
)
CHECKPOINT_BASE = spark.conf.get(
    "spark.manufacturing.checkpoint.base",
    "s3://manufacturing-poc-checkpoints-ACCOUNTID/"  # Replace with actual bucket
)
TARGET_CATALOG = "manufacturing_poc"
TARGET_SCHEMA_ALPHA = "factory_alpha"
TARGET_SCHEMA_BETA = "factory_beta"

# COMMAND ----------

from pyspark.sql.functions import (
    col,
    current_timestamp,
    from_json,
    get_json_object,
    to_timestamp,
    expr,
)
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType,
    LongType,
    BooleanType,
    TimestampType,
)
from delta.tables import DeltaTable

# COMMAND ----------

# MAGIC %md
# MAGIC ## Schema Definitions

# COMMAND ----------

sensor_schema = StructType([
    StructField("event_id", StringType(), False),
    StructField("timestamp", LongType(), False),
    StructField("factory_id", StringType(), False),
    StructField("device_id", StringType(), False),
    StructField("line_id", StringType(), False),
    StructField("event_type", StringType(), False),
    StructField("sensor_type", StringType(), True),
    StructField("value", DoubleType(), True),
    StructField("unit", StringType(), True),
    StructField("payload_reference", StringType(), True),
    StructField("content_type", StringType(), True),
    StructField("payload_size_bytes", LongType(), True),
    StructField("checksum_sha256", StringType(), True),
    StructField("equipment_state", StringType(), True),
    StructField("measurement_value", DoubleType(), True),
    StructField("pass_fail", BooleanType(), True),
])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Kafka Source Configuration

# COMMAND ----------

def create_kafka_stream(topic: str):
    """Create a Kafka readStream for the given topic with MSK IAM auth."""
    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", topic)
        .option("kafka.security.protocol", "SASL_SSL")
        .option("kafka.sasl.mechanism", "AWS_MSK_IAM")
        .option(
            "kafka.sasl.jaas.config",
            "software.amazon.msk.auth.iam.IAMLoginModule required;"
        )
        .option(
            "kafka.sasl.client.callback.handler.class",
            "software.amazon.msk.auth.iam.IAMClientCallbackHandler"
        )
        .option("startingOffsets", "latest")
        .option("maxOffsetsPerTrigger", "100000")
        .load()
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Stream 1: Sensor Data (High Volume — dropDuplicates approach)

# COMMAND ----------

def start_sensor_stream():
    """Sensor data stream: Kafka → Delta with watermark-based dedup."""
    
    raw_stream = create_kafka_stream("factory.sensor-data")
    
    parsed = (
        raw_stream
        .select(
            from_json(col("value").cast("string"), sensor_schema).alias("data"),
            col("topic"),
            col("partition").alias("kafka_partition"),
            col("offset").alias("kafka_offset"),
        )
        .select("data.*", "topic", "kafka_partition", "kafka_offset")
        .withColumn(
            "event_timestamp",
            to_timestamp(col("timestamp") / 1000)  # millis to timestamp
        )
        .withColumn("ingestion_timestamp", current_timestamp())
        .withColumn("kafka_topic", col("topic"))
        # Dedup within watermark window (ADR-010)
        .withWatermark("event_timestamp", "1 hour")
        .dropDuplicatesWithinWatermark(["event_id"])
    )
    
    # Route by factory_id to appropriate schema
    # For PoC simplicity, write all to factory_alpha
    sensor_output = parsed.select(
        "event_id",
        "event_timestamp",
        "factory_id",
        "device_id",
        "line_id",
        "sensor_type",
        "value",
        "unit",
        "ingestion_timestamp",
        "kafka_topic",
        "kafka_partition",
        "kafka_offset",
    )
    
    query = (
        sensor_output.writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"{CHECKPOINT_BASE}sensor-data/")
        .option("mergeSchema", "true")
        .trigger(processingTime="10 seconds")
        .toTable(f"{TARGET_CATALOG}.{TARGET_SCHEMA_ALPHA}.sensor_readings")
    )
    
    return query

# COMMAND ----------

# MAGIC %md
# MAGIC ## Stream 2: Quality Events (Critical — foreachBatch + MERGE for exact dedup)

# COMMAND ----------

def upsert_quality_events(batch_df, batch_id):
    """Idempotent upsert for quality events — guarantees no duplicates (ADR-010)."""
    if batch_df.isEmpty():
        return
    
    # Deduplicate within micro-batch
    deduped = batch_df.dropDuplicates(["event_id"])
    
    target_table = f"{TARGET_CATALOG}.{TARGET_SCHEMA_ALPHA}.quality_events"
    
    # Check if target table exists and has data
    try:
        delta_table = DeltaTable.forName(spark, target_table)
        (
            delta_table.alias("target")
            .merge(
                deduped.alias("source"),
                "target.event_id = source.event_id"
            )
            .whenNotMatchedInsertAll()
            .execute()
        )
    except Exception:
        # Table may be empty on first run — just insert
        deduped.write.format("delta").mode("append").saveAsTable(target_table)


def start_quality_stream():
    """Quality events stream: Kafka → Delta with exact dedup via MERGE."""
    
    raw_stream = create_kafka_stream("factory.quality-events")
    
    parsed = (
        raw_stream
        .select(
            from_json(col("value").cast("string"), sensor_schema).alias("data"),
        )
        .select("data.*")
        .withColumn(
            "event_timestamp",
            to_timestamp(col("timestamp") / 1000)
        )
        .withColumn("ingestion_timestamp", current_timestamp())
        .select(
            "event_id",
            "event_timestamp",
            "factory_id",
            "device_id",
            "line_id",
            "event_type",
            "measurement_value",
            "pass_fail",
            col("payload_reference").alias("payload_uri"),
            "content_type",
            col("payload_size_bytes"),
            col("checksum_sha256").alias("payload_checksum"),
            "ingestion_timestamp",
        )
    )
    
    query = (
        parsed.writeStream
        .foreachBatch(upsert_quality_events)
        .option("checkpointLocation", f"{CHECKPOINT_BASE}quality-events/")
        .trigger(processingTime="30 seconds")
        .start()
    )
    
    return query

# COMMAND ----------

# MAGIC %md
# MAGIC ## Start All Streams

# COMMAND ----------

# Start sensor data stream
sensor_query = start_sensor_stream()
print(f"Sensor stream started: {sensor_query.name}")

# Start quality events stream
quality_query = start_quality_stream()
print(f"Quality stream started: {quality_query.name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Monitor Streams

# COMMAND ----------

# Display active streams
for stream in spark.streams.active:
    print(f"Stream: {stream.name}, Status: {stream.status}")

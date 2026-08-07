# Databricks notebook source
# Manufacturing Data Platform PoC — Training Features Import (Path B)
#
# Integration Path B: ClickHouse → Parquet Export → ONTAP S3 → DataSync → S3 → UC
# Source: factory_v3.training_features_export (ClickHouse)
# Target: manufacturing_poc.silver.training_features
#
# This notebook implements the scheduled import of pre-computed features
# from ClickHouse into Databricks Unity Catalog for ML training.
#
# Execution Options:
#   1. Databricks Workflow (scheduled, recommended)
#   2. Manual run for ad-hoc imports
#
# Prerequisites:
#   - DataSync task configured (ONTAP S3 → S3 bucket)
#   - S3 bucket: s3://manufacturing-poc-features-ACCOUNTID/
#   - IAM role with S3 read access attached to cluster
#   - UC catalog manufacturing_poc.silver exists

# COMMAND ----------

# MAGIC %md
# MAGIC # Training Features Import Pipeline
# MAGIC
# MAGIC ## Data Flow
# MAGIC ```
# MAGIC ClickHouse (training_features_export)
# MAGIC   → Scheduled Query (Parquet export to ONTAP S3)
# MAGIC   → AWS DataSync (ONTAP S3 → S3 bucket)
# MAGIC   → This notebook (S3 → Delta Lake via Auto Loader)
# MAGIC   → manufacturing_poc.silver.training_features
# MAGIC ```

# COMMAND ----------

from pyspark.sql.functions import (
    current_timestamp,
    input_file_name,
    expr,
)
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    DoubleType,
    LongType,
    IntegerType,
    TimestampType,
)

# COMMAND ----------

# Configuration
FEATURES_S3_PATH = spark.conf.get(
    "spark.manufacturing.features.s3_path",
    "s3://manufacturing-poc-features-ACCOUNTID/training_features/"
)
CHECKPOINT_PATH = spark.conf.get(
    "spark.manufacturing.features.checkpoint",
    "s3://manufacturing-poc-checkpoints-ACCOUNTID/training-features-import/"
)
TARGET_TABLE = "manufacturing_poc.silver.training_features"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Schema Definition (matches ClickHouse training_features_export)

# COMMAND ----------

features_schema = StructType([
    StructField("export_id", StringType(), False),
    StructField("site_id", StringType(), False),
    StructField("equipment_id", StringType(), False),
    StructField("sensor_id", StringType(), False),
    StructField("feature_window_start", TimestampType(), False),
    StructField("feature_window_end", TimestampType(), False),
    StructField("avg_value", DoubleType(), True),
    StructField("min_value", DoubleType(), True),
    StructField("max_value", DoubleType(), True),
    StructField("stddev_value", DoubleType(), True),
    StructField("count_readings", LongType(), True),
    StructField("p50_value", DoubleType(), True),
    StructField("p95_value", DoubleType(), True),
    StructField("p99_value", DoubleType(), True),
    StructField("quality_label", StringType(), True),
    StructField("defect_type", StringType(), True),
    # Human ground-truth labels (feedback loop, Edge round 2)
    StructField("human_label", StringType(), True),
    StructField("label_confidence", DoubleType(), True),
    StructField("labeled_by", StringType(), True),
    StructField("labeled_at", TimestampType(), True),
    StructField("export_timestamp", TimestampType(), True),
    StructField("feature_version", StringType(), True),
    StructField("window_duration_seconds", IntegerType(), True),
])

# COMMAND ----------

# MAGIC %md
# MAGIC ## Option 1: Auto Loader (Streaming — Recommended for production)

# COMMAND ----------

def run_streaming_import():
    """
    Auto Loader based import — processes new Parquet files as they arrive.
    Runs continuously or can be triggered on schedule.
    """
    return (
        spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "parquet")
        .option("cloudFiles.schemaLocation", f"{CHECKPOINT_PATH}schema/")
        .option("cloudFiles.inferColumnTypes", "true")
        .option("cloudFiles.schemaEvolutionMode", "addNewColumns")
        .schema(features_schema)
        .load(FEATURES_S3_PATH)
        .withColumn("_imported_at", current_timestamp())
        .withColumn("_source_file", input_file_name())
        .writeStream
        .format("delta")
        .outputMode("append")
        .option("checkpointLocation", f"{CHECKPOINT_PATH}checkpoint/")
        .option("mergeSchema", "true")
        .trigger(availableNow=True)  # Process all available files then stop
        .toTable(TARGET_TABLE)
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## Option 2: Batch Import (for ad-hoc or backfill)

# COMMAND ----------

def run_batch_import(date_filter: str | None = None):
    """
    Batch import — reads all Parquet files (or filtered by date partition).
    Use for initial load or backfill scenarios.

    Args:
        date_filter: Optional date string (YYYY-MM-DD) to filter by export date
    """
    df = (
        spark.read
        .format("parquet")
        .schema(features_schema)
        .load(FEATURES_S3_PATH)
        .withColumn("_imported_at", current_timestamp())
        .withColumn("_source_file", input_file_name())
    )

    if date_filter:
        df = df.filter(expr(f"date(export_timestamp) = '{date_filter}'"))

    # Deduplicate by export_id (idempotent writes)
    df_deduped = df.dropDuplicates(["export_id"])

    # MERGE for idempotent upsert
    from delta.tables import DeltaTable

    if DeltaTable.isDeltaTable(spark, TARGET_TABLE):
        target = DeltaTable.forName(spark, TARGET_TABLE)
        (
            target.alias("t")
            .merge(df_deduped.alias("s"), "t.export_id = s.export_id")
            .whenNotMatchedInsertAll()
            .execute()
        )
    else:
        df_deduped.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)

    return df_deduped.count()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Execute Import

# COMMAND ----------

# Default: Use Auto Loader (streaming with availableNow=True)
# This processes all new files since last checkpoint, then stops.
query = run_streaming_import()
query.awaitTermination()

print(f"Import complete. Target: {TARGET_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validation Queries

# COMMAND ----------

# Record count and latest import
display(spark.sql(f"""
    SELECT
        count(*) AS total_records,
        count(DISTINCT export_id) AS unique_exports,
        min(feature_window_start) AS earliest_window,
        max(feature_window_end) AS latest_window,
        max(_imported_at) AS last_import_time
    FROM {TARGET_TABLE}
"""))

# COMMAND ----------

# Distribution by site and quality label
display(spark.sql(f"""
    SELECT
        site_id,
        quality_label,
        count(*) AS count,
        avg(avg_value) AS mean_avg_value,
        avg(stddev_value) AS mean_stddev
    FROM {TARGET_TABLE}
    GROUP BY site_id, quality_label
    ORDER BY site_id, quality_label
"""))

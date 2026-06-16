# Databricks notebook source
# Manufacturing Data Platform PoC — Gold Training Dataset Generation
#
# Builds manufacturing_poc.gold.training_dataset by joining sensor features
# with human ground-truth labels from the feedback loop.
#
# Reference: Edge databricks-integration.md section 5.1
# Sync Date: 2026-06-16
#
# Label priority (Edge round 2 design):
#   1. human_label  (feedback_events — operator ground truth) — HIGHEST
#   2. quality_label (AI classification from quality_events)  — fallback
#   3. 'unknown'                                               — no label
#
# Prerequisites:
#   - manufacturing_poc.silver.training_features populated (Path B import)
#   - manufacturing_poc.bronze.feedback_events populated (DLT route)
#   - manufacturing_poc.gold.training_dataset created (03_unity_catalog_v2.sql)

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.window import Window

# COMMAND ----------

CATALOG = "manufacturing_poc"
TARGET_TABLE = f"{CATALOG}.gold.training_dataset"

# Train/validation/test split ratios
SPLIT_RATIOS = {"train": 0.7, "validation": 0.15, "test": 0.15}
SPLIT_SEED = 42

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Load Silver features and feedback labels

# COMMAND ----------

features = spark.table(f"{CATALOG}.silver.training_features")
feedback = spark.table(f"{CATALOG}.bronze.feedback_events")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Resolve human labels per (site, equipment, window)
# MAGIC
# MAGIC A feedback event corrects a specific target event. We attach the most
# MAGIC recent human label that falls within each feature window, keyed by
# MAGIC site + equipment. ReplacingMergeTree on the ClickHouse side already
# MAGIC dedups by target_event_id; here we keep the latest label per window.

# COMMAND ----------

# Keep the most recent feedback per (site_id, equipment_id, labeled_at)
feedback_latest = (
    feedback
    .filter(F.col("human_label").isNotNull())
    .withColumn(
        "_rank",
        F.row_number().over(
            Window.partitionBy("site_id", "equipment_id", F.col("target_event_id"))
            .orderBy(F.col("labeled_at").desc())
        ),
    )
    .filter(F.col("_rank") == 1)
    .select(
        "site_id",
        "equipment_id",
        F.col("event_timestamp").alias("feedback_timestamp"),
        "human_label",
        F.col("defect_type").alias("feedback_defect_type"),
        "label_confidence",
        "labeled_by",
        "labeled_at",
        "is_synthetic",
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Join features with human labels (window containment)

# COMMAND ----------

joined = (
    features.alias("f")
    .join(
        feedback_latest.alias("fb"),
        on=[
            F.col("f.site_id") == F.col("fb.site_id"),
            F.col("f.equipment_id") == F.col("fb.equipment_id"),
            F.col("fb.feedback_timestamp") >= F.col("f.feature_window_start"),
            F.col("fb.feedback_timestamp") <= F.col("f.feature_window_end"),
        ],
        how="left",
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Resolve final label (human > AI > unknown)

# COMMAND ----------

labeled = (
    joined
    .withColumn(
        "label",
        F.coalesce(
            F.col("fb.human_label"),       # 1. human ground truth
            F.col("f.quality_label"),       # 2. AI classification
            F.lit("unknown"),               # 3. no label
        ),
    )
    .withColumn(
        "label_source",
        F.when(F.col("fb.human_label").isNotNull(), F.lit("human"))
        .when(F.col("f.quality_label").isNotNull(), F.lit("ai"))
        .otherwise(F.lit("none")),
    )
    .withColumn(
        "defect_type",
        F.coalesce(F.col("fb.feedback_defect_type"), F.col("f.defect_type")),
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Assign deterministic train/validation/test split

# COMMAND ----------

# Deterministic split via hash of sample_id for reproducibility
final_df = (
    labeled
    # Exclude unlabeled rows from the training dataset
    .filter(F.col("label") != "unknown")
    .withColumn(
        "sample_id",
        F.sha2(
            F.concat_ws(
                "-",
                F.col("f.site_id"),
                F.col("f.equipment_id"),
                F.col("f.feature_window_start").cast("string"),
            ),
            256,
        ),
    )
    .withColumn("_split_bucket", F.abs(F.hash(F.col("sample_id"))) % 100)
    .withColumn(
        "split",
        F.when(F.col("_split_bucket") < 70, F.lit("train"))
        .when(F.col("_split_bucket") < 85, F.lit("validation"))
        .otherwise(F.lit("test")),
    )
    .select(
        "sample_id",
        F.col("f.site_id").alias("site_id"),
        F.col("f.equipment_id").alias("equipment_id"),
        F.col("f.feature_window_start").alias("feature_window_start"),
        F.col("f.feature_window_end").alias("feature_window_end"),
        F.col("f.avg_value").alias("avg_value"),
        F.col("f.min_value").alias("min_value"),
        F.col("f.max_value").alias("max_value"),
        F.col("f.stddev_value").alias("stddev_value"),
        F.col("f.count_readings").alias("count_readings"),
        F.col("f.p50_value").alias("p50_value"),
        F.col("f.p95_value").alias("p95_value"),
        F.col("f.p99_value").alias("p99_value"),
        F.lit(None).cast("string").alias("image_path"),
        F.lit(None).cast("array<double>").alias("image_embedding"),
        "label",
        "defect_type",
        F.lit("1.0.0").alias("dataset_version"),
        "split",
        F.current_timestamp().alias("_created_at"),
    )
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Idempotent write (MERGE by sample_id)

# COMMAND ----------

from delta.tables import DeltaTable

deduped = final_df.dropDuplicates(["sample_id"])

if DeltaTable.isDeltaTable(spark, TARGET_TABLE):
    target = DeltaTable.forName(spark, TARGET_TABLE)
    (
        target.alias("t")
        .merge(deduped.alias("s"), "t.sample_id = s.sample_id")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
else:
    deduped.write.format("delta").mode("overwrite").saveAsTable(TARGET_TABLE)

print(f"Gold training dataset written: {TARGET_TABLE}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validation

# COMMAND ----------

display(spark.sql(f"""
    SELECT
        split,
        label,
        count(*) AS samples
    FROM {TARGET_TABLE}
    GROUP BY split, label
    ORDER BY split, label
"""))

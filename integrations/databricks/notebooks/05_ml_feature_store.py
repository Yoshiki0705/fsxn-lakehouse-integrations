# Databricks notebook source
# MAGIC %md
# MAGIC # 05 - ML Feature Store on FSxN
# MAGIC
# MAGIC Use FSx for NetApp ONTAP as the storage layer for Databricks Feature Store.
# MAGIC ONTAP FlexClone enables instant feature set snapshots for model reproducibility.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

S3_ACCESS_POINT_ALIAS = "<your-s3ap-alias>"
CATALOG = "fsxn_lakehouse"
FEATURE_SCHEMA = "features"

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG fsxn_lakehouse;
# MAGIC CREATE SCHEMA IF NOT EXISTS features COMMENT 'ML Feature Store tables on FSxN';
# MAGIC USE SCHEMA features;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Feature Tables

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import *
from datetime import datetime, timedelta
import random
import numpy as np

# Generate customer features
def generate_customer_features(n=10000):
    data = []
    for i in range(n):
        data.append((
            f"CUST-{i:04d}",
            random.randint(1, 100),           # total_orders
            round(random.uniform(50, 5000), 2),  # total_spend
            round(random.uniform(20, 200), 2),   # avg_order_value
            random.randint(1, 365),              # days_since_last_order
            round(random.uniform(0, 1), 4),      # churn_probability
            random.choice(["high", "medium", "low"]),  # segment
            datetime.now() - timedelta(hours=random.randint(0, 24))  # feature_timestamp
        ))
    schema = StructType([
        StructField("customer_id", StringType()),
        StructField("total_orders", IntegerType()),
        StructField("total_spend", DoubleType()),
        StructField("avg_order_value", DoubleType()),
        StructField("days_since_last_order", IntegerType()),
        StructField("churn_probability", DoubleType()),
        StructField("segment", StringType()),
        StructField("feature_timestamp", TimestampType()),
    ])
    return spark.createDataFrame(data, schema)

customer_features_df = generate_customer_features()

# COMMAND ----------

# Write feature table as Delta on FSxN
feature_path = f"s3://{S3_ACCESS_POINT_ALIAS}/gold/features/customer_features/"

customer_features_df.write \
    .format("delta") \
    .mode("overwrite") \
    .option("overwriteSchema", "true") \
    .save(feature_path)

# Register as Unity Catalog table
spark.sql(f"""
CREATE TABLE IF NOT EXISTS fsxn_lakehouse.features.customer_features
USING DELTA
LOCATION '{feature_path}'
COMMENT 'Customer ML features on FSxN'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'purpose' = 'ml_feature_store',
    'refresh_frequency' = 'daily'
)
""")

print(f"✅ Feature table created: {feature_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Feature Lookup for Model Training

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Feature lookup query for model training
# MAGIC SELECT
# MAGIC   cf.customer_id,
# MAGIC   cf.total_orders,
# MAGIC   cf.total_spend,
# MAGIC   cf.avg_order_value,
# MAGIC   cf.days_since_last_order,
# MAGIC   cf.churn_probability,
# MAGIC   cf.segment
# MAGIC FROM fsxn_lakehouse.features.customer_features cf
# MAGIC WHERE cf.feature_timestamp >= current_timestamp() - INTERVAL 24 HOURS;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Feature Versioning with ONTAP Snapshots
# MAGIC
# MAGIC **Workflow for ML Reproducibility:**
# MAGIC
# MAGIC 1. Train model with current features
# MAGIC 2. ONTAP creates scheduled Snapshot of feature volume
# MAGIC 3. When retraining, FlexClone from specific Snapshot
# MAGIC 4. Point training job to cloned feature set
# MAGIC 5. Guaranteed identical features for reproducibility
# MAGIC
# MAGIC ```
# MAGIC Feature Volume (FSxN)
# MAGIC ├── Snapshot: features_2024_Q1 ──→ FlexClone → Model v1 training
# MAGIC ├── Snapshot: features_2024_Q2 ──→ FlexClone → Model v2 training
# MAGIC └── Current (live features)    ──→ Model v3 training (in progress)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Point-in-Time Feature Retrieval

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Enable Change Data Feed for point-in-time correctness
# MAGIC ALTER TABLE fsxn_lakehouse.features.customer_features
# MAGIC SET TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true');

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Read changes since last model training
# MAGIC SELECT *
# MAGIC FROM table_changes('fsxn_lakehouse.features.customer_features', 1)
# MAGIC WHERE _change_type IN ('insert', 'update_postimage');

# COMMAND ----------

# MAGIC %md
# MAGIC ## ONTAP Value for Feature Store
# MAGIC
# MAGIC | Feature | ML Benefit |
# MAGIC |---------|-----------|
# MAGIC | FlexClone | Instant feature set snapshot for training (zero-copy) |
# MAGIC | Snapshot | Versioned feature sets for model reproducibility |
# MAGIC | Deduplication | Feature tables with overlapping columns save space |
# MAGIC | Tiering | Old feature versions auto-tier (keep for audit) |
# MAGIC | SnapMirror | DR for critical feature pipelines |

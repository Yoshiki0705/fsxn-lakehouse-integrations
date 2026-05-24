# Experimental validation notebook
# This notebook documents observed behavior for FSx for ONTAP S3 Access Point access from Databricks.
# It is not a production reference architecture.
# Do not use Instance Profile + boto3 as a Unity Catalog governance replacement.

# Databricks notebook source
# MAGIC %md
# MAGIC # 03 - Delta Lake Tables on FSxN
# MAGIC
# MAGIC Create and manage Delta Lake tables with FSx for NetApp ONTAP as the storage layer.
# MAGIC Demonstrates ACID transactions, time travel, and ONTAP Snapshot integration.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

S3_ACCESS_POINT_ALIAS = "<your-s3ap-alias>"
CATALOG = "fsxn_lakehouse"

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG fsxn_lakehouse;
# MAGIC USE SCHEMA silver;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Delta Table on FSxN (Silver Layer)

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import *
from datetime import datetime, timedelta
import random

# Generate sample data
def generate_orders(n=10000):
    data = []
    for i in range(n):
        data.append((
            f"ORD-{i:08d}",
            f"CUST-{random.randint(1, 1000):04d}",
            random.choice(["electronics", "clothing", "food", "books", "sports"]),
            round(random.uniform(10.0, 500.0), 2),
            random.randint(1, 10),
            random.choice(["pending", "shipped", "delivered", "cancelled"]),
            datetime(2024, 1, 1) + timedelta(days=random.randint(0, 365))
        ))
    schema = StructType([
        StructField("order_id", StringType()),
        StructField("customer_id", StringType()),
        StructField("category", StringType()),
        StructField("amount", DoubleType()),
        StructField("quantity", IntegerType()),
        StructField("status", StringType()),
        StructField("order_date", TimestampType()),
    ])
    return spark.createDataFrame(data, schema)

orders_df = generate_orders(50000)
orders_df.display()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Write Delta Table to FSxN

# COMMAND ----------

# Write as Delta table on FSxN
delta_path = f"s3://{S3_ACCESS_POINT_ALIAS}/silver/orders_delta/"

orders_df.write \
    .format("delta") \
    .mode("overwrite") \
    .partitionBy("category") \
    .save(delta_path)

print(f"✅ Delta table written to: {delta_path}")

# COMMAND ----------

# Register as Unity Catalog table
spark.sql(f"""
CREATE TABLE IF NOT EXISTS fsxn_lakehouse.silver.orders
USING DELTA
LOCATION '{delta_path}'
COMMENT 'Orders Delta table on FSx for NetApp ONTAP'
""")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Verify Delta table
# MAGIC DESCRIBE HISTORY fsxn_lakehouse.silver.orders;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Delta Lake Operations on FSxN

# COMMAND ----------

# MAGIC %md
# MAGIC ### UPDATE - Modify existing records

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Update order statuses
# MAGIC UPDATE fsxn_lakehouse.silver.orders
# MAGIC SET status = 'delivered'
# MAGIC WHERE status = 'shipped' AND order_date < '2024-06-01';

# COMMAND ----------

# MAGIC %md
# MAGIC ### MERGE (Upsert) - CDC pattern

# COMMAND ----------

# Simulate incoming CDC data
cdc_data = generate_orders(1000)
cdc_df = cdc_data.withColumn("updated_at", F.current_timestamp())
cdc_df.createOrReplaceTempView("cdc_updates")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- MERGE (upsert) pattern
# MAGIC MERGE INTO fsxn_lakehouse.silver.orders AS target
# MAGIC USING cdc_updates AS source
# MAGIC ON target.order_id = source.order_id
# MAGIC WHEN MATCHED THEN
# MAGIC   UPDATE SET
# MAGIC     target.status = source.status,
# MAGIC     target.amount = source.amount
# MAGIC WHEN NOT MATCHED THEN
# MAGIC   INSERT (order_id, customer_id, category, amount, quantity, status, order_date)
# MAGIC   VALUES (source.order_id, source.customer_id, source.category, source.amount,
# MAGIC           source.quantity, source.status, source.order_date);

# COMMAND ----------

# MAGIC %md
# MAGIC ## Delta Time Travel on FSxN

# COMMAND ----------

# MAGIC %sql
# MAGIC -- View table history
# MAGIC DESCRIBE HISTORY fsxn_lakehouse.silver.orders;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Query previous version (time travel)
# MAGIC SELECT COUNT(*), status
# MAGIC FROM fsxn_lakehouse.silver.orders VERSION AS OF 0
# MAGIC GROUP BY status;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Compare current vs previous version
# MAGIC SELECT 'current' as version, COUNT(*) as total_rows FROM fsxn_lakehouse.silver.orders
# MAGIC UNION ALL
# MAGIC SELECT 'version_0' as version, COUNT(*) as total_rows FROM fsxn_lakehouse.silver.orders VERSION AS OF 0;

# COMMAND ----------

# MAGIC %md
# MAGIC ## ONTAP Snapshot + Delta Time Travel
# MAGIC
# MAGIC **Complementary Recovery Strategy:**
# MAGIC - Delta Time Travel: Row-level recovery within retention period
# MAGIC - ONTAP Snapshot: Volume-level instant recovery (entire table state)
# MAGIC
# MAGIC ```
# MAGIC Timeline:
# MAGIC ─────────────────────────────────────────────────────
# MAGIC  ONTAP Snap 1    Delta v0   v1   v2    ONTAP Snap 2
# MAGIC  (full volume)   (rows)  (rows) (rows) (full volume)
# MAGIC ─────────────────────────────────────────────────────
# MAGIC ```
# MAGIC
# MAGIC To restore from ONTAP Snapshot:
# MAGIC 1. Create FlexClone from snapshot
# MAGIC 2. Mount clone as new volume
# MAGIC 3. Point new External Location to clone
# MAGIC 4. Query historical data without affecting production

# COMMAND ----------

# MAGIC %md
# MAGIC ## OPTIMIZE and VACUUM on FSxN

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Optimize (compact small files) - benefits from ONTAP deduplication
# MAGIC OPTIMIZE fsxn_lakehouse.silver.orders;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Z-ORDER for query optimization
# MAGIC OPTIMIZE fsxn_lakehouse.silver.orders
# MAGIC ZORDER BY (customer_id, order_date);

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Vacuum old files (ONTAP dedup handles storage efficiency)
# MAGIC -- Note: Keep longer retention if using ONTAP Snapshots for recovery
# MAGIC VACUUM fsxn_lakehouse.silver.orders RETAIN 168 HOURS;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Storage Efficiency Check
# MAGIC
# MAGIC ONTAP deduplication is especially effective for Delta tables because:
# MAGIC - Multiple versions share common data blocks
# MAGIC - Parquet column chunks have high dedup ratio
# MAGIC - OPTIMIZE creates new files with overlapping content

# COMMAND ----------

# Check Delta table file statistics
from delta.tables import DeltaTable

dt = DeltaTable.forPath(spark, delta_path)
detail = dt.detail().collect()[0]

print(f"Table: fsxn_lakehouse.silver.orders")
print(f"  Files: {detail['numFiles']}")
print(f"  Size: {detail['sizeInBytes'] / 1024 / 1024:.1f} MB")
print(f"  Partitions: {detail['numPartitions'] if 'numPartitions' in detail.asDict() else 'N/A'}")
print(f"  Format: {detail['format']}")
print(f"\n💡 ONTAP deduplication typically reduces Delta storage by 30-60%")
print(f"   due to shared data blocks across versions.")

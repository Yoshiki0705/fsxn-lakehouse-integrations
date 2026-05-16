# Databricks notebook source
# MAGIC %md
# MAGIC # 04 - Apache Iceberg Tables on FSxN
# MAGIC
# MAGIC Create and manage Iceberg tables on FSx for NetApp ONTAP.
# MAGIC Iceberg provides vendor-neutral ACID tables accessible from multiple engines.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

S3_ACCESS_POINT_ALIAS = "<your-s3ap-alias>"
CATALOG = "fsxn_lakehouse"

# COMMAND ----------

# MAGIC %sql
# MAGIC USE CATALOG fsxn_lakehouse;
# MAGIC CREATE SCHEMA IF NOT EXISTS iceberg_tables;
# MAGIC USE SCHEMA iceberg_tables;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Iceberg Table on FSxN

# COMMAND ----------

from pyspark.sql.types import *
from pyspark.sql import functions as F
from datetime import datetime, timedelta
import random

# Generate sample product catalog data
def generate_products(n=5000):
    categories = ["electronics", "clothing", "home", "sports", "books", "food"]
    data = []
    for i in range(n):
        data.append((
            f"PROD-{i:06d}",
            f"Product {i}",
            random.choice(categories),
            round(random.uniform(5.0, 999.99), 2),
            random.randint(0, 1000),
            random.choice([True, False]),
            datetime(2024, 1, 1) + timedelta(days=random.randint(0, 365))
        ))
    schema = StructType([
        StructField("product_id", StringType()),
        StructField("name", StringType()),
        StructField("category", StringType()),
        StructField("price", DoubleType()),
        StructField("stock_quantity", IntegerType()),
        StructField("is_active", BooleanType()),
        StructField("last_updated", TimestampType()),
    ])
    return spark.createDataFrame(data, schema)

products_df = generate_products()

# COMMAND ----------

# Write as Iceberg table on FSxN
iceberg_path = f"s3://{S3_ACCESS_POINT_ALIAS}/silver/products_iceberg/"

products_df.writeTo("fsxn_lakehouse.iceberg_tables.products") \
    .using("iceberg") \
    .tableProperty("location", iceberg_path) \
    .tableProperty("write.format.default", "parquet") \
    .tableProperty("write.parquet.compression-codec", "zstd") \
    .partitionedBy("category") \
    .createOrReplace()

print(f"✅ Iceberg table created at: {iceberg_path}")

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Verify Iceberg table
# MAGIC DESCRIBE EXTENDED fsxn_lakehouse.iceberg_tables.products;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Query Iceberg table
# MAGIC SELECT category, COUNT(*) as count, AVG(price) as avg_price
# MAGIC FROM fsxn_lakehouse.iceberg_tables.products
# MAGIC GROUP BY category
# MAGIC ORDER BY count DESC;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Iceberg Schema Evolution

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Add new column (schema evolution)
# MAGIC ALTER TABLE fsxn_lakehouse.iceberg_tables.products
# MAGIC ADD COLUMNS (discount_pct DOUBLE COMMENT 'Discount percentage');

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Rename column
# MAGIC ALTER TABLE fsxn_lakehouse.iceberg_tables.products
# MAGIC RENAME COLUMN stock_quantity TO inventory_count;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Iceberg Time Travel

# COMMAND ----------

# MAGIC %sql
# MAGIC -- View snapshot history
# MAGIC SELECT * FROM fsxn_lakehouse.iceberg_tables.products.history;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- View snapshots
# MAGIC SELECT * FROM fsxn_lakehouse.iceberg_tables.products.snapshots;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Query specific snapshot
# MAGIC -- SELECT * FROM fsxn_lakehouse.iceberg_tables.products VERSION AS OF <snapshot_id>;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Iceberg Partition Evolution
# MAGIC
# MAGIC Iceberg supports partition evolution without rewriting data.
# MAGIC Combined with ONTAP FlexClone, you can test partition changes risk-free.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Add partition field (hidden partitioning)
# MAGIC ALTER TABLE fsxn_lakehouse.iceberg_tables.products
# MAGIC ADD PARTITION FIELD months(last_updated);

# COMMAND ----------

# MAGIC %md
# MAGIC ## Cross-Platform Access
# MAGIC
# MAGIC Iceberg tables on FSxN can be accessed from multiple engines:
# MAGIC
# MAGIC | Engine | Access Method |
# MAGIC |--------|--------------|
# MAGIC | Databricks | Unity Catalog (this notebook) |
# MAGIC | Snowflake | Iceberg Table (external catalog) |
# MAGIC | Athena | Glue Data Catalog |
# MAGIC | Trino | Iceberg Connector |
# MAGIC | Spark (EMR) | Iceberg Spark Runtime |
# MAGIC
# MAGIC All engines read the same Iceberg metadata and data files on FSxN.
# MAGIC ONTAP ensures consistent reads via S3 API.

# COMMAND ----------

# MAGIC %md
# MAGIC ## ONTAP Benefits for Iceberg
# MAGIC
# MAGIC | Feature | Benefit |
# MAGIC |---------|---------|
# MAGIC | Snapshot | Recover entire Iceberg table state (metadata + data) |
# MAGIC | FlexClone | Test schema/partition evolution on clone before production |
# MAGIC | Deduplication | Iceberg rewrites create duplicate blocks → dedup saves space |
# MAGIC | Tiering | Old snapshots/partitions auto-tier to S3 |

# COMMAND ----------

# MAGIC %md
# MAGIC ## Maintenance Operations

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Expire old snapshots (keep ONTAP Snapshots for deeper history)
# MAGIC CALL system.expire_snapshots('fsxn_lakehouse.iceberg_tables.products', TIMESTAMP '2024-01-01');

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Remove orphan files
# MAGIC CALL system.remove_orphan_files('fsxn_lakehouse.iceberg_tables.products');

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Rewrite data files (compaction)
# MAGIC CALL system.rewrite_data_files('fsxn_lakehouse.iceberg_tables.products');

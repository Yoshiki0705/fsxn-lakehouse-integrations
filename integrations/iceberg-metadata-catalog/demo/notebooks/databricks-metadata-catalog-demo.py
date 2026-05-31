# Databricks notebook source
# MAGIC %md
# MAGIC # Iceberg Metadata Catalog — Databricks Demo
# MAGIC
# MAGIC This notebook demonstrates querying the FSx for ONTAP metadata catalog
# MAGIC from Databricks using the S3 Tables Iceberg REST endpoint.
# MAGIC
# MAGIC **Prerequisites**:
# MAGIC - Spark cluster with Iceberg runtime
# MAGIC - IAM role with `s3tables:*` permissions
# MAGIC
# MAGIC **Architecture**:
# MAGIC ```
# MAGIC FSx for ONTAP → S3 Tables (Iceberg) → Spark SQL (this notebook)
# MAGIC ```

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup: Configure Iceberg REST Catalog for S3 Tables

# COMMAND ----------

# Configure S3 Tables Iceberg REST Catalog
# Replace <ACCOUNT_ID> with your AWS account ID

ACCOUNT_ID = "178625946981"
REGION = "ap-northeast-1"
TABLE_BUCKET = f"arn:aws:s3tables:{REGION}:{ACCOUNT_ID}:bucket/fsxn-metadata-catalog"

spark.conf.set("spark.sql.catalog.s3tables", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.s3tables.catalog-impl", "org.apache.iceberg.rest.RESTCatalog")
spark.conf.set("spark.sql.catalog.s3tables.uri", f"https://s3tables.{REGION}.amazonaws.com/iceberg")
spark.conf.set("spark.sql.catalog.s3tables.warehouse", TABLE_BUCKET)
spark.conf.set("spark.sql.catalog.s3tables.rest.sigv4-enabled", "true")
spark.conf.set("spark.sql.catalog.s3tables.rest.signing-region", REGION)
spark.conf.set("spark.sql.catalog.s3tables.rest.signing-name", "s3tables")

print(f"✅ Iceberg REST Catalog configured for S3 Tables")
print(f"   Endpoint: https://s3tables.{REGION}.amazonaws.com/iceberg")
print(f"   Warehouse: {TABLE_BUCKET}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Query 1: File Type Distribution

# COMMAND ----------

df_types = spark.sql("""
    SELECT
        file_type,
        COUNT(*) AS file_count,
        ROUND(SUM(file_size) / 1024 / 1024, 2) AS total_mb
    FROM s3tables.metadata.unstructured_files
    WHERE is_deleted = false
    GROUP BY file_type
    ORDER BY total_mb DESC
""")

display(df_types)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Query 2: AI-Enriched Files (Classification Results)

# COMMAND ----------

df_enriched = spark.sql("""
    SELECT
        file_name,
        classification,
        confidence_score,
        summary,
        enrichment_status
    FROM s3tables.metadata.unstructured_files
    WHERE enrichment_status = 'completed'
    ORDER BY confidence_score DESC
""")

display(df_enriched)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Query 3: Iceberg Time Travel (Snapshot History)

# COMMAND ----------

df_history = spark.sql("""
    SELECT
        made_current_at,
        snapshot_id,
        parent_id
    FROM s3tables.metadata.`unstructured_files$history`
    ORDER BY made_current_at DESC
    LIMIT 10
""")

display(df_history)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Query 4: Files Pending AI Enrichment

# COMMAND ----------

df_pending = spark.sql("""
    SELECT
        file_name,
        file_type,
        file_size,
        created_at
    FROM s3tables.metadata.unstructured_files
    WHERE enrichment_status = 'pending'
      AND is_deleted = false
    ORDER BY created_at DESC
    LIMIT 20
""")

display(df_pending)
print(f"Pending enrichment: {df_pending.count()} files")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Query 5: Vector Embedding Analysis
# MAGIC
# MAGIC Check which files have embeddings generated (ready for similarity search).

# COMMAND ----------

df_embeddings = spark.sql("""
    SELECT
        file_name,
        classification,
        CASE WHEN embedding_vector IS NOT NULL THEN 'Yes' ELSE 'No' END AS has_embedding,
        enrichment_status
    FROM s3tables.metadata.unstructured_files
    WHERE is_deleted = false
    ORDER BY enrichment_status, file_name
    LIMIT 20
""")

display(df_embeddings)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC This notebook demonstrated:
# MAGIC 1. ✅ Connecting Databricks Spark to S3 Tables via Iceberg REST Catalog
# MAGIC 2. ✅ Querying metadata (file types, classifications, embeddings)
# MAGIC 3. ✅ Iceberg Time Travel (snapshot history)
# MAGIC 4. ✅ Identifying files pending AI enrichment
# MAGIC
# MAGIC **Note**: This requires a Spark cluster (not SQL Warehouse) because
# MAGIC `CREATE CONNECTION TYPE iceberg_rest` is not yet supported on SQL Warehouse.
# MAGIC Feature request filed with Databricks support.

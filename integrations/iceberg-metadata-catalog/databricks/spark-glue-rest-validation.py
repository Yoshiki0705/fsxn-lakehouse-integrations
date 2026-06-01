# Databricks notebook source
# MAGIC %md
# MAGIC # Spark + AWS Glue Iceberg REST → S3 Tables Validation
# MAGIC
# MAGIC This notebook validates reading S3 Tables metadata via the AWS Glue Iceberg REST endpoint from a Databricks Spark cluster.
# MAGIC
# MAGIC ## Prerequisites
# MAGIC - Databricks cluster with:
# MAGIC   - Runtime 14.3+ (Iceberg support)
# MAGIC   - Instance profile or IAM role with: glue:Get*, lakeformation:GetDataAccess, s3tables:*, s3:GetObject
# MAGIC   - Iceberg Spark extensions enabled
# MAGIC - AWS Glue Iceberg REST endpoint accessible from the cluster VPC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Configure Iceberg REST Catalog (Glue endpoint)

# COMMAND ----------

# Spark configuration for AWS Glue Iceberg REST endpoint
spark.conf.set("spark.sql.catalog.s3tables", "org.apache.iceberg.spark.SparkCatalog")
spark.conf.set("spark.sql.catalog.s3tables.catalog-impl", "org.apache.iceberg.rest.RESTCatalog")
spark.conf.set("spark.sql.catalog.s3tables.uri", "https://glue.ap-northeast-1.amazonaws.com/iceberg")
spark.conf.set("spark.sql.catalog.s3tables.warehouse", "178625946981:s3tablescatalog/fsxn-metadata-catalog")
spark.conf.set("spark.sql.catalog.s3tables.rest.sigv4-enabled", "true")
spark.conf.set("spark.sql.catalog.s3tables.rest.signing-region", "ap-northeast-1")
spark.conf.set("spark.sql.catalog.s3tables.rest.signing-name", "glue")

print("Catalog configured: s3tables → Glue Iceberg REST → S3 Tables")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: List namespaces and tables

# COMMAND ----------

# List namespaces
namespaces = spark.sql("SHOW NAMESPACES IN s3tables")
display(namespaces)

# COMMAND ----------

# List tables in metadata namespace
tables = spark.sql("SHOW TABLES IN s3tables.metadata")
display(tables)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Query metadata table

# COMMAND ----------

# Read metadata
df = spark.sql("""
SELECT file_name, file_type, classification, confidence_score, enrichment_status
FROM s3tables.metadata.unstructured_files
WHERE classification IS NOT NULL
LIMIT 10
""")
display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Time travel (snapshot history)

# COMMAND ----------

# Check snapshot history
history = spark.sql("SELECT * FROM s3tables.metadata.unstructured_files.history LIMIT 5")
display(history)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Record count and schema

# COMMAND ----------

count = spark.sql("SELECT COUNT(*) as total FROM s3tables.metadata.unstructured_files").collect()[0][0]
print(f"Total records: {count}")

# Show schema
spark.sql("DESCRIBE s3tables.metadata.unstructured_files").show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Results
# MAGIC
# MAGIC If all cells above executed successfully:
# MAGIC - ✅ Spark cluster can connect to S3 Tables via Glue Iceberg REST
# MAGIC - ✅ Namespace and table discovery works
# MAGIC - ✅ SELECT queries work
# MAGIC - ✅ Time travel / snapshot history accessible
# MAGIC
# MAGIC This validates **Path 1b** (Spark + Glue Iceberg REST) from the blog article.

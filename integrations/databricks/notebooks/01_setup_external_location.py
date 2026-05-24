# Experimental validation notebook
# This notebook documents observed behavior for FSx for ONTAP S3 Access Point access from Databricks.
# It is not a production reference architecture.
# Do not use Instance Profile + boto3 as a Unity Catalog governance replacement.

# Databricks notebook source
# MAGIC %md
# MAGIC # 01 - Setup External Location for FSxN
# MAGIC
# MAGIC This notebook creates and validates a Databricks Unity Catalog External Location
# MAGIC pointing to FSx for NetApp ONTAP via S3 Access Point.
# MAGIC
# MAGIC ## Prerequisites
# MAGIC - CloudFormation stack deployed (template.yaml)
# MAGIC - Storage Credential created (via Terraform or Databricks UI)
# MAGIC - S3 Access Point alias available

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

# Configuration - Update these values from CloudFormation outputs
S3_ACCESS_POINT_ALIAS = "<your-s3ap-alias>"  # From CFn output: S3AccessPointAlias
STORAGE_CREDENTIAL_NAME = "fsxn-lakehouse-fsxn-credential"
EXTERNAL_LOCATION_NAME = "fsxn-lakehouse-root"

# Medallion architecture paths
BRONZE_PATH = f"s3://{S3_ACCESS_POINT_ALIAS}/bronze/"
SILVER_PATH = f"s3://{S3_ACCESS_POINT_ALIAS}/silver/"
GOLD_PATH = f"s3://{S3_ACCESS_POINT_ALIAS}/gold/"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validate Storage Credential

# COMMAND ----------

# MAGIC %sql
# MAGIC -- List available storage credentials
# MAGIC SHOW STORAGE CREDENTIALS;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Describe the FSxN storage credential
# MAGIC DESCRIBE STORAGE CREDENTIAL `fsxn-lakehouse-fsxn-credential`;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create External Location (if not using Terraform)

# COMMAND ----------

# Create external location via SQL (alternative to Terraform)
spark.sql(f"""
CREATE EXTERNAL LOCATION IF NOT EXISTS `{EXTERNAL_LOCATION_NAME}`
URL 's3://{S3_ACCESS_POINT_ALIAS}/'
WITH (STORAGE CREDENTIAL `{STORAGE_CREDENTIAL_NAME}`)
COMMENT 'FSx for NetApp ONTAP root location via S3 Access Point'
""")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validate External Location Access

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Validate the external location
# MAGIC VALIDATE EXTERNAL LOCATION `fsxn-lakehouse-root`;

# COMMAND ----------

# Test listing files via the external location
try:
    files = dbutils.fs.ls(f"s3://{S3_ACCESS_POINT_ALIAS}/")
    print(f"✅ Successfully listed {len(files)} items at root")
    for f in files[:10]:
        print(f"  {f.name} ({f.size} bytes)")
except Exception as e:
    print(f"❌ Error accessing S3 AP: {e}")
    print("Check: VPC endpoint, IAM role, S3 AP policy")

# COMMAND ----------

# Test write access
test_path = f"s3://{S3_ACCESS_POINT_ALIAS}/_connectivity_test/"
try:
    dbutils.fs.put(f"{test_path}test.txt", "FSxN connectivity test", overwrite=True)
    content = dbutils.fs.head(f"{test_path}test.txt")
    dbutils.fs.rm(test_path, recurse=True)
    print(f"✅ Write/Read/Delete test passed")
except Exception as e:
    print(f"❌ Write test failed: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Medallion Layer External Locations

# COMMAND ----------

for layer, path in [("bronze", BRONZE_PATH), ("silver", SILVER_PATH), ("gold", GOLD_PATH)]:
    try:
        spark.sql(f"""
        CREATE EXTERNAL LOCATION IF NOT EXISTS `fsxn-{layer}`
        URL '{path}'
        WITH (STORAGE CREDENTIAL `{STORAGE_CREDENTIAL_NAME}`)
        COMMENT 'FSxN {layer} layer'
        """)
        print(f"✅ External location 'fsxn-{layer}' created: {path}")
    except Exception as e:
        print(f"⚠️ {layer}: {e}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary
# MAGIC
# MAGIC External locations created:
# MAGIC - `fsxn-lakehouse-root` → Root access to FSxN volume
# MAGIC - `fsxn-bronze` → Bronze layer (raw data)
# MAGIC - `fsxn-silver` → Silver layer (cleaned)
# MAGIC - `fsxn-gold` → Gold layer (business-ready)
# MAGIC
# MAGIC Next: Run `02_create_external_table.py` to create tables.

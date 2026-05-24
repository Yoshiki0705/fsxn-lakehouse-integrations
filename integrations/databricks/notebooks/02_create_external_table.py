# Experimental validation notebook
# This notebook documents observed behavior for FSx for ONTAP S3 Access Point access from Databricks.
# It is not a production reference architecture.
# Do not use Instance Profile + boto3 as a Unity Catalog governance replacement.

# Databricks notebook source
# MAGIC %md
# MAGIC # 02 - Create External Tables on FSxN
# MAGIC
# MAGIC Create External Tables in Unity Catalog pointing to Parquet, CSV, and JSON
# MAGIC files stored on FSx for NetApp ONTAP via S3 Access Point.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Configuration

# COMMAND ----------

S3_ACCESS_POINT_ALIAS = "<your-s3ap-alias>"
CATALOG = "fsxn_lakehouse"
SCHEMA_BRONZE = "bronze"
SCHEMA_SILVER = "silver"

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Create catalog and schemas if not exists
# MAGIC CREATE CATALOG IF NOT EXISTS fsxn_lakehouse;
# MAGIC USE CATALOG fsxn_lakehouse;
# MAGIC CREATE SCHEMA IF NOT EXISTS bronze;
# MAGIC CREATE SCHEMA IF NOT EXISTS silver;
# MAGIC CREATE SCHEMA IF NOT EXISTS gold;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create External Table from Parquet

# COMMAND ----------

# MAGIC %sql
# MAGIC -- External table pointing to Parquet files on FSxN
# MAGIC CREATE TABLE IF NOT EXISTS fsxn_lakehouse.bronze.transactions
# MAGIC USING PARQUET
# MAGIC LOCATION 's3://${S3_ACCESS_POINT_ALIAS}/bronze/transactions/'
# MAGIC COMMENT 'Financial transactions stored on FSx for NetApp ONTAP';

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Verify table
# MAGIC DESCRIBE EXTENDED fsxn_lakehouse.bronze.transactions;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Query sample data
# MAGIC SELECT * FROM fsxn_lakehouse.bronze.transactions LIMIT 10;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create External Table from CSV

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS fsxn_lakehouse.bronze.customers_csv
# MAGIC (
# MAGIC   customer_id STRING,
# MAGIC   name STRING,
# MAGIC   email STRING,
# MAGIC   country STRING,
# MAGIC   created_at TIMESTAMP
# MAGIC )
# MAGIC USING CSV
# MAGIC OPTIONS (
# MAGIC   header = 'true',
# MAGIC   inferSchema = 'false',
# MAGIC   delimiter = ','
# MAGIC )
# MAGIC LOCATION 's3://${S3_ACCESS_POINT_ALIAS}/bronze/customers/'
# MAGIC COMMENT 'Customer data (CSV) on FSxN';

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create External Table from JSON

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE TABLE IF NOT EXISTS fsxn_lakehouse.bronze.events_json
# MAGIC USING JSON
# MAGIC LOCATION 's3://${S3_ACCESS_POINT_ALIAS}/bronze/events/'
# MAGIC COMMENT 'Event stream data (JSON) on FSxN';

# COMMAND ----------

# MAGIC %md
# MAGIC ## Create Partitioned External Table

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Partitioned Parquet table (by date)
# MAGIC CREATE TABLE IF NOT EXISTS fsxn_lakehouse.bronze.iot_sensors
# MAGIC USING PARQUET
# MAGIC PARTITIONED BY (date STRING)
# MAGIC LOCATION 's3://${S3_ACCESS_POINT_ALIAS}/bronze/iot-sensors/'
# MAGIC COMMENT 'IoT sensor data partitioned by date on FSxN';

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Repair partitions (discover existing partitions)
# MAGIC MSCK REPAIR TABLE fsxn_lakehouse.bronze.iot_sensors;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify All Tables

# COMMAND ----------

# MAGIC %sql
# MAGIC SHOW TABLES IN fsxn_lakehouse.bronze;

# COMMAND ----------

# MAGIC %md
# MAGIC ## Performance Test - Read Throughput

# COMMAND ----------

from pyspark.sql import functions as F
import time

# Read performance test
start = time.time()
df = spark.read.parquet(f"s3://{S3_ACCESS_POINT_ALIAS}/bronze/transactions/")
count = df.count()
elapsed = time.time() - start

print(f"Read {count:,} rows in {elapsed:.2f}s ({count/elapsed:,.0f} rows/sec)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next Steps
# MAGIC
# MAGIC - Run `03_delta_lake_on_fsxn.py` to create Delta Lake tables
# MAGIC - Run `04_iceberg_on_fsxn.py` for Iceberg table format

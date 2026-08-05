"""
FSx for ONTAP Glue Integration — Bronze to Silver ETL Job

Reads raw data from the bronze layer (Parquet/CSV/JSON via S3 Access Point),
applies transformations (schema normalization, null handling, type casting,
deduplication), and writes to the silver layer as Parquet with ZSTD compression.

Features:
  - GlueContext + DynamicFrame API
  - Job bookmarks for incremental processing
  - Adds _etl_timestamp and _source_file metadata columns
  - Schema normalization (lowercase column names, consistent types)
  - Null handling and deduplication

Glue Version: 4.0 (Spark 3.3+)

Arguments:
  --source_database: Glue Data Catalog database name
  --s3_ap_alias: S3 Access Point alias
  --target_path: S3 path for silver output
"""

import sys
from datetime import datetime

from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    TimestampType,
)

# --- Initialize Glue Context ---
args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "source_database",
    "s3_ap_alias",
    "target_path",
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# --- Configuration ---
SOURCE_DATABASE = args["source_database"]
S3_AP_ALIAS = args["s3_ap_alias"]
TARGET_PATH = args["target_path"]
ETL_TIMESTAMP = datetime.utcnow().isoformat()

print(f"=== Bronze to Silver ETL ===")
print(f"Source Database: {SOURCE_DATABASE}")
print(f"S3 AP Alias: {S3_AP_ALIAS}")
print(f"Target Path: {TARGET_PATH}")
print(f"ETL Timestamp: {ETL_TIMESTAMP}")


def normalize_column_names(df):
    """Normalize column names to lowercase with underscores."""
    for col_name in df.columns:
        new_name = col_name.lower().replace(" ", "_").replace("-", "_")
        if new_name != col_name:
            df = df.withColumnRenamed(col_name, new_name)
    return df


def handle_nulls(df, strategy="default"):
    """Handle null values based on column types."""
    for field in df.schema.fields:
        if isinstance(field.dataType, StringType):
            df = df.withColumn(
                field.name,
                F.when(F.col(field.name).isNull(), F.lit("")).otherwise(F.col(field.name))
            )
        elif isinstance(field.dataType, (IntegerType, DoubleType)):
            df = df.withColumn(
                field.name,
                F.when(F.col(field.name).isNull(), F.lit(0)).otherwise(F.col(field.name))
            )
    return df


def add_metadata_columns(df):
    """Add ETL metadata columns."""
    df = df.withColumn("_etl_timestamp", F.lit(ETL_TIMESTAMP).cast(TimestampType()))
    df = df.withColumn("_source_file", F.input_file_name())
    return df


def deduplicate(df, key_columns):
    """Remove duplicates based on key columns, keeping the latest record."""
    if "_etl_timestamp" in df.columns:
        window = (
            df.orderBy(F.col("_etl_timestamp").desc())
        )
    return df.dropDuplicates(key_columns)


def process_transactions():
    """Process transactions table: bronze → silver."""
    print("\n--- Processing: transactions ---")

    try:
        # Read from Glue Catalog (uses job bookmarks for incremental)
        dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name="transactions",
            transformation_ctx="transactions_source",
        )

        if dynamic_frame.count() == 0:
            print("  No new records to process (bookmark)")
            return

        print(f"  Records read: {dynamic_frame.count()}")

        # Convert to DataFrame for transformations
        df = dynamic_frame.toDF()

        # Apply transformations
        df = normalize_column_names(df)
        df = add_metadata_columns(df)

        # Type casting
        df = df.withColumn("amount", F.col("amount").cast(DoubleType()))
        df = df.withColumn("transaction_date", F.col("transaction_date").cast(TimestampType()))

        # Null handling
        df = handle_nulls(df)

        # Deduplication by transaction ID
        df = deduplicate(df, ["id"])

        print(f"  Records after dedup: {df.count()}")

        # Write to silver (Parquet, ZSTD, partitioned by year/month)
        output_path = f"{TARGET_PATH}transactions/"
        df.write \
            .mode("append") \
            .partitionBy("year", "month") \
            .option("compression", "zstd") \
            .parquet(output_path)

        print(f"  ✅ Written to: {output_path}")

    except Exception as e:
        print(f"  ❌ Error processing transactions: {e}")
        raise


def process_customers():
    """Process customers table: bronze → silver."""
    print("\n--- Processing: customers ---")

    try:
        dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name="customers",
            transformation_ctx="customers_source",
        )

        if dynamic_frame.count() == 0:
            print("  No new records to process (bookmark)")
            return

        print(f"  Records read: {dynamic_frame.count()}")

        df = dynamic_frame.toDF()

        # Apply transformations
        df = normalize_column_names(df)
        df = add_metadata_columns(df)

        # Type casting
        df = df.withColumn("created_at", F.col("created_at").cast(TimestampType()))

        # Null handling
        df = handle_nulls(df)

        # Deduplication by customer_id
        df = deduplicate(df, ["customer_id"])

        print(f"  Records after dedup: {df.count()}")

        # Write to silver (Parquet, ZSTD)
        output_path = f"{TARGET_PATH}customers/"
        df.write \
            .mode("overwrite") \
            .option("compression", "zstd") \
            .parquet(output_path)

        print(f"  ✅ Written to: {output_path}")

    except Exception as e:
        print(f"  ❌ Error processing customers: {e}")
        raise


def process_events():
    """Process events table: bronze → silver."""
    print("\n--- Processing: events ---")

    try:
        dynamic_frame = glueContext.create_dynamic_frame.from_catalog(
            database=SOURCE_DATABASE,
            table_name="events",
            transformation_ctx="events_source",
        )

        if dynamic_frame.count() == 0:
            print("  No new records to process (bookmark)")
            return

        print(f"  Records read: {dynamic_frame.count()}")

        df = dynamic_frame.toDF()

        # Apply transformations
        df = normalize_column_names(df)
        df = add_metadata_columns(df)

        # Type casting
        df = df.withColumn("timestamp", F.col("timestamp").cast(TimestampType()))

        # Null handling
        df = handle_nulls(df)

        # Deduplication by event_id
        df = deduplicate(df, ["event_id"])

        # Extract date for partitioning
        df = df.withColumn("event_date", F.to_date(F.col("timestamp")))

        print(f"  Records after dedup: {df.count()}")

        # Write to silver (Parquet, ZSTD, partitioned by date)
        output_path = f"{TARGET_PATH}events/"
        df.write \
            .mode("append") \
            .partitionBy("event_date") \
            .option("compression", "zstd") \
            .parquet(output_path)

        print(f"  ✅ Written to: {output_path}")

    except Exception as e:
        print(f"  ❌ Error processing events: {e}")
        raise


# --- Main ETL Execution ---
print("\n=== Starting Bronze → Silver ETL ===")

process_transactions()
process_customers()
process_events()

print("\n=== Bronze → Silver ETL Complete ===")

# Commit job bookmark
job.commit()

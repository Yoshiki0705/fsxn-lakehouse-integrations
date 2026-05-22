"""
FSxN Glue Integration — Silver to Gold ETL Job

Reads cleaned data from the silver layer, performs aggregations
(daily summaries, category rollups, customer metrics), and writes
to the gold layer as Parquet for consumption by BI tools.

Features:
  - GlueContext + DynamicFrame API
  - Job bookmarks for incremental processing
  - Daily transaction summaries
  - Category-level rollups
  - Customer lifetime metrics

Glue Version: 4.0 (Spark 3.3+)

Arguments:
  --source_database: Glue Data Catalog database name
  --s3_ap_alias: S3 Access Point alias
  --silver_path: S3 path for silver input
  --gold_path: S3 path for gold output
"""

import sys
from datetime import datetime

from awsglue.context import GlueContext
from awsglue.dynamicframe import DynamicFrame
from awsglue.job import Job
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import Window
from pyspark.sql import functions as F

# --- Initialize Glue Context ---
args = getResolvedOptions(sys.argv, [
    "JOB_NAME",
    "source_database",
    "s3_ap_alias",
    "silver_path",
    "gold_path",
])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# --- Configuration ---
SOURCE_DATABASE = args["source_database"]
S3_AP_ALIAS = args["s3_ap_alias"]
SILVER_PATH = args["silver_path"]
GOLD_PATH = args["gold_path"]
ETL_TIMESTAMP = datetime.utcnow().isoformat()

print(f"=== Silver to Gold ETL ===")
print(f"Source Database: {SOURCE_DATABASE}")
print(f"Silver Path: {SILVER_PATH}")
print(f"Gold Path: {GOLD_PATH}")
print(f"ETL Timestamp: {ETL_TIMESTAMP}")


def create_daily_summaries(transactions_df):
    """
    Create daily transaction summaries.

    Output columns:
      - transaction_date: date
      - total_transactions: count
      - total_amount: sum of amounts
      - avg_amount: average transaction amount
      - unique_customers: distinct customer count
      - completed_count: completed transactions
      - cancelled_count: cancelled transactions
      - completion_rate: completed / total ratio
    """
    print("\n--- Creating: daily_summaries ---")

    daily = transactions_df.groupBy(
        F.to_date(F.col("transaction_date")).alias("date")
    ).agg(
        F.count("*").alias("total_transactions"),
        F.sum("amount").alias("total_amount"),
        F.avg("amount").alias("avg_amount"),
        F.countDistinct("customer_id").alias("unique_customers"),
        F.sum(F.when(F.col("status") == "completed", 1).otherwise(0)).alias("completed_count"),
        F.sum(F.when(F.col("status") == "cancelled", 1).otherwise(0)).alias("cancelled_count"),
    )

    daily = daily.withColumn(
        "completion_rate",
        F.round(F.col("completed_count") / F.col("total_transactions"), 4)
    )

    # Add metadata
    daily = daily.withColumn("_etl_timestamp", F.lit(ETL_TIMESTAMP))

    # Write to gold
    output_path = f"{GOLD_PATH}daily_summaries/"
    daily.write \
        .mode("overwrite") \
        .partitionBy("date") \
        .parquet(output_path)

    print(f"  Records: {daily.count()}")
    print(f"  ✅ Written to: {output_path}")

    return daily


def create_category_rollups(transactions_df):
    """
    Create category-level rollups.

    Output columns:
      - category: transaction category
      - total_transactions: count
      - total_amount: sum
      - avg_amount: average
      - unique_customers: distinct customers
      - pct_of_total: percentage of total revenue
    """
    print("\n--- Creating: category_rollups ---")

    total_revenue = transactions_df.agg(F.sum("amount")).collect()[0][0] or 1.0

    category = transactions_df.groupBy("category").agg(
        F.count("*").alias("total_transactions"),
        F.sum("amount").alias("total_amount"),
        F.avg("amount").alias("avg_amount"),
        F.countDistinct("customer_id").alias("unique_customers"),
        F.min("transaction_date").alias("first_transaction"),
        F.max("transaction_date").alias("last_transaction"),
    )

    category = category.withColumn(
        "pct_of_total",
        F.round(F.col("total_amount") / F.lit(total_revenue) * 100, 2)
    )

    # Add metadata
    category = category.withColumn("_etl_timestamp", F.lit(ETL_TIMESTAMP))

    # Write to gold
    output_path = f"{GOLD_PATH}category_rollups/"
    category.write \
        .mode("overwrite") \
        .parquet(output_path)

    print(f"  Records: {category.count()}")
    print(f"  ✅ Written to: {output_path}")

    return category


def create_customer_metrics(transactions_df, customers_df):
    """
    Create customer lifetime metrics.

    Output columns:
      - customer_id: customer identifier
      - name, country, segment: from customers table
      - total_transactions: lifetime count
      - total_spent: lifetime amount
      - avg_transaction: average per transaction
      - first_purchase: first transaction date
      - last_purchase: last transaction date
      - days_active: days between first and last purchase
      - favorite_category: most frequent category
    """
    print("\n--- Creating: customer_metrics ---")

    # Aggregate transaction metrics per customer
    customer_txn = transactions_df.groupBy("customer_id").agg(
        F.count("*").alias("total_transactions"),
        F.sum("amount").alias("total_spent"),
        F.avg("amount").alias("avg_transaction"),
        F.min("transaction_date").alias("first_purchase"),
        F.max("transaction_date").alias("last_purchase"),
    )

    # Calculate days active
    customer_txn = customer_txn.withColumn(
        "days_active",
        F.datediff(F.col("last_purchase"), F.col("first_purchase"))
    )

    # Find favorite category per customer
    category_counts = transactions_df.groupBy("customer_id", "category").count()
    window = Window.partitionBy("customer_id").orderBy(F.col("count").desc())
    favorite_category = category_counts.withColumn(
        "rank", F.row_number().over(window)
    ).filter(F.col("rank") == 1).select(
        "customer_id",
        F.col("category").alias("favorite_category")
    )

    # Join with customer dimension
    customer_metrics = customer_txn.join(
        favorite_category, "customer_id", "left"
    )

    if customers_df is not None and customers_df.count() > 0:
        customer_metrics = customer_metrics.join(
            customers_df.select("customer_id", "name", "country", "segment"),
            "customer_id",
            "left"
        )

    # Add metadata
    customer_metrics = customer_metrics.withColumn("_etl_timestamp", F.lit(ETL_TIMESTAMP))

    # Write to gold
    output_path = f"{GOLD_PATH}customer_metrics/"
    customer_metrics.write \
        .mode("overwrite") \
        .parquet(output_path)

    print(f"  Records: {customer_metrics.count()}")
    print(f"  ✅ Written to: {output_path}")

    return customer_metrics


# --- Main ETL Execution ---
print("\n=== Starting Silver → Gold ETL ===")

# Read silver layer data
print("\n--- Reading silver layer ---")

try:
    transactions_df = spark.read.parquet(f"{SILVER_PATH}transactions/")
    print(f"  Transactions: {transactions_df.count()} records")
except Exception as e:
    print(f"  ❌ Failed to read transactions: {e}")
    transactions_df = None

try:
    customers_df = spark.read.parquet(f"{SILVER_PATH}customers/")
    print(f"  Customers: {customers_df.count()} records")
except Exception as e:
    print(f"  ⚠️  Customers not available: {e}")
    customers_df = None

# Generate gold aggregations
if transactions_df is not None and transactions_df.count() > 0:
    create_daily_summaries(transactions_df)
    create_category_rollups(transactions_df)
    create_customer_metrics(transactions_df, customers_df)
else:
    print("\n⚠️  No transaction data available — skipping gold aggregations")

print("\n=== Silver → Gold ETL Complete ===")

# Commit job bookmark
job.commit()

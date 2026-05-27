"""
FSx for ONTAP S3 AP — EMR Serverless Spark ETL Job (PoC Template)

Reads sensor data from FSx for ONTAP via S3 Access Point,
performs transformations, and writes results back to FSx.

Usage:
  aws emr-serverless start-job-run \
    --application-id <APP_ID> \
    --execution-role-arn <ROLE_ARN> \
    --job-driver '{"sparkSubmit":{"entryPoint":"s3://<BUCKET>/scripts/spark-job.py"}}'

CRITICAL: Use s3:// (EMRFS), NOT s3a:// — S3A cannot parse AP aliases.
"""

import time
import sys
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# ============================================================
# Configuration — Replace with your S3 AP alias
# ============================================================
S3_AP_ALIAS = "s3://<YOUR-AP-ALIAS-ext-s3alias>"
INPUT_PATH = f"{S3_AP_ALIAS}/sensor-data/sensor_data.parquet"
OUTPUT_PATH = f"{S3_AP_ALIAS}/gold/emr-poc-output/"

# ============================================================
# Initialize Spark
# ============================================================
spark = SparkSession.builder \
    .appName("FSxN-S3AP-PoC-ETL") \
    .getOrCreate()

print("=" * 60)
print("FSx for ONTAP S3 AP — EMR Serverless Spark ETL")
print("=" * 60)

# ============================================================
# Step 1: Read from FSx for ONTAP via S3 AP
# ============================================================
print("\n📖 Step 1: Reading from FSx for ONTAP S3 AP...")
start = time.time()

df = spark.read.parquet(INPUT_PATH)
row_count = df.count()

read_time = time.time() - start
print(f"   ✅ Read {row_count:,} rows in {read_time:.2f}s")
print(f"   Schema: {', '.join([f'{f.name}:{f.dataType.simpleString()}' for f in df.schema.fields])}")

# ============================================================
# Step 2: Transform — Aggregation
# ============================================================
print("\n🔄 Step 2: Aggregation (GROUP BY status)...")
start = time.time()

agg_df = df.groupBy("status").agg(
    F.count("*").alias("count"),
    F.round(F.avg("temperature"), 2).alias("avg_temperature"),
    F.round(F.avg("humidity"), 2).alias("avg_humidity"),
    F.round(F.avg("pressure"), 2).alias("avg_pressure"),
    F.min("timestamp").alias("first_reading"),
    F.max("timestamp").alias("last_reading"),
)

agg_df.show()
agg_time = time.time() - start
print(f"   ✅ Aggregation completed in {agg_time:.2f}s")

# ============================================================
# Step 3: Transform — Window function (moving average)
# ============================================================
print("\n🔄 Step 3: Window function (moving average per device)...")
start = time.time()

window_spec = Window.partitionBy("device_id").orderBy("timestamp").rowsBetween(-5, 0)
window_df = df.withColumn(
    "moving_avg_temp", F.round(F.avg("temperature").over(window_spec), 2)
).withColumn(
    "moving_avg_humidity", F.round(F.avg("humidity").over(window_spec), 2)
)

window_df.select(
    "device_id", "timestamp", "temperature", "moving_avg_temp", "humidity", "moving_avg_humidity"
).show(5, truncate=False)

window_time = time.time() - start
print(f"   ✅ Window function completed in {window_time:.2f}s")

# ============================================================
# Step 4: Write back to FSx for ONTAP via S3 AP
# ============================================================
print(f"\n💾 Step 4: Writing results back to {OUTPUT_PATH}...")
start = time.time()

agg_df.write.mode("overwrite").parquet(OUTPUT_PATH)

write_time = time.time() - start
print(f"   ✅ Write-back completed in {write_time:.2f}s")

# ============================================================
# Summary
# ============================================================
total_time = read_time + agg_time + window_time + write_time
print("\n" + "=" * 60)
print("📊 ETL Summary")
print("=" * 60)
print(f"   Input rows:      {row_count:,}")
print(f"   Read time:       {read_time:.2f}s")
print(f"   Aggregation:     {agg_time:.2f}s")
print(f"   Window function: {window_time:.2f}s")
print(f"   Write-back:      {write_time:.2f}s")
print(f"   Total Spark:     {total_time:.2f}s")
print(f"   Output path:     {OUTPUT_PATH}")
print("=" * 60)

spark.stop()

# Experimental validation notebook
# This notebook documents observed behavior for FSx for ONTAP S3 Access Point access from Databricks.
# It is not a production reference architecture.
# Do not use Instance Profile + boto3 as a Unity Catalog governance replacement.

# Databricks notebook source
# MAGIC %md
# MAGIC # 05: Executor-Scale boto3 Validation
# MAGIC
# MAGIC Validates whether Instance Profile + boto3 works from Spark executors
# MAGIC (not just the driver node). This is critical because driver-only success
# MAGIC does not prove distributed workload viability.
# MAGIC
# MAGIC **Prerequisites:**
# MAGIC - Customer-managed VPC workspace
# MAGIC - Dedicated (Single User) cluster with Instance Profile
# MAGIC - Instance Profile has s3:GetObject + s3:ListBucket on S3 AP ARN
# MAGIC
# MAGIC **What this tests:**
# MAGIC - Credential availability on executor nodes
# MAGIC - S3 AP network reachability from executors
# MAGIC - Latency and error rate per executor
# MAGIC - Comparison with driver-node behavior

# COMMAND ----------

import boto3
import socket
import os
import time
from pyspark.sql import Row

S3_AP_ALIAS = "<YOUR_AP_ALIAS>"  # Replace with actual alias
REGION = "ap-northeast-1"
TEST_KEY = "sensor-data/sensor_data.parquet"

# COMMAND ----------

# MAGIC %md
# MAGIC ## Driver-node baseline (should succeed if Instance Profile is configured)

s3 = boto3.client("s3", region_name=REGION)
try:
    resp = s3.head_object(Bucket=S3_AP_ALIAS, Key=TEST_KEY)
    print(f"Driver HeadObject: SUCCESS (size={resp['ContentLength']})")
except Exception as e:
    print(f"Driver HeadObject: FAILED ({e})")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Executor-scale validation using mapPartitions

def validate_from_executor(iterator):
    """Run from each executor to test S3 AP access."""
    import boto3
    import socket
    import time

    hostname = socket.gethostname()
    results = []

    try:
        s3 = boto3.client("s3", region_name=REGION)

        # Test 1: ListObjectsV2
        t0 = time.time()
        list_resp = s3.list_objects_v2(
            Bucket=S3_AP_ALIAS, Prefix="sensor-data/", MaxKeys=5
        )
        list_latency = (time.time() - t0) * 1000
        list_success = "Contents" in list_resp

        # Test 2: HeadObject
        t0 = time.time()
        head_resp = s3.head_object(Bucket=S3_AP_ALIAS, Key=TEST_KEY)
        head_latency = (time.time() - t0) * 1000
        head_success = True
        object_size = head_resp["ContentLength"]

        # Test 3: GetObject (first 1KB)
        t0 = time.time()
        get_resp = s3.get_object(
            Bucket=S3_AP_ALIAS, Key=TEST_KEY, Range="bytes=0-1023"
        )
        get_latency = (time.time() - t0) * 1000
        get_success = get_resp["ResponseMetadata"]["HTTPStatusCode"] == 206

        results.append(Row(
            executor=hostname,
            list_success=list_success,
            list_latency_ms=round(list_latency, 1),
            head_success=head_success,
            head_latency_ms=round(head_latency, 1),
            get_success=get_success,
            get_latency_ms=round(get_latency, 1),
            object_size=object_size,
            error=None
        ))

    except Exception as e:
        results.append(Row(
            executor=hostname,
            list_success=False,
            list_latency_ms=-1,
            head_success=False,
            head_latency_ms=-1,
            get_success=False,
            get_latency_ms=-1,
            object_size=-1,
            error=str(e)[:200]
        ))

    # Consume iterator (required for mapPartitions)
    for _ in iterator:
        pass

    return iter(results)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Execute across all executors

# Create a DataFrame with enough partitions to hit all executors
num_executors = spark.sparkContext.defaultParallelism
test_df = spark.range(0, num_executors * 2, numPartitions=num_executors)

# Run validation from each executor
results_df = test_df.rdd.mapPartitions(validate_from_executor).toDF()
results_df.cache()
results_df.show(truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Summary

print(f"Total executors tested: {results_df.count()}")
print(f"Successful: {results_df.filter('list_success = true').count()}")
print(f"Failed: {results_df.filter('list_success = false').count()}")
print(f"Avg list latency: {results_df.agg({'list_latency_ms': 'avg'}).collect()[0][0]:.1f} ms")
print(f"Avg get latency: {results_df.agg({'get_latency_ms': 'avg'}).collect()[0][0]:.1f} ms")

errors = results_df.filter("error IS NOT NULL").select("executor", "error")
if errors.count() > 0:
    print("\nErrors:")
    errors.show(truncate=False)

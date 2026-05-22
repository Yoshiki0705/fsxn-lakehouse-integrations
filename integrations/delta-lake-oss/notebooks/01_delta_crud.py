"""
FSxN Delta Lake OSS — CRUD Operations Verification

Creates Delta table on FSxN via S3 AP, performs INSERT, UPDATE, DELETE, MERGE.
Records operation latency and write throughput.

Usage (spark-submit):
    spark-submit --packages io.delta:delta-spark_2.12:3.1.0 \
        --conf spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension \
        --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog \
        01_delta_crud.py --s3-ap-alias <alias>
"""

import argparse
import json
import time
from datetime import datetime

from delta.tables import DeltaTable
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)


def get_spark() -> SparkSession:
    return SparkSession.builder \
        .appName("FSxN Delta Lake CRUD Verification") \
        .getOrCreate()


def timed(label: str):
    """Decorator to time operations."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            print(f"\n▶ {label}")
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            print(f"  ✅ Completed in {elapsed:.1f}s")
            return {"label": label, "time_s": elapsed, "result": result}
        return wrapper
    return decorator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--s3-ap-alias", required=True, help="S3 AP alias")
    parser.add_argument("--output", default="/tmp/delta_crud_results.json")
    args = parser.parse_args()

    spark = get_spark()
    base_path = f"s3a://{args.s3_ap_alias}/delta/transactions"
    results = []

    print("=" * 60)
    print("FSxN Delta Lake OSS — CRUD Verification")
    print("=" * 60)
    print(f"Delta table path: {base_path}")

    # --- CREATE: Write initial Delta table ---
    print("\n▶ CREATE: Writing initial Delta table (50,000 rows)")
    start = time.time()

    schema = StructType([
        StructField("id", IntegerType(), False),
        StructField("customer_id", StringType(), True),
        StructField("amount", DoubleType(), True),
        StructField("status", StringType(), True),
        StructField("category", StringType(), True),
        StructField("transaction_date", TimestampType(), True),
    ])

    # Generate sample data
    df = spark.range(1, 50001).select(
        F.col("id").cast(IntegerType()),
        F.concat(F.lit("CUST-"), F.lpad(F.expr("id % 5000 + 1").cast("string"), 5, "0")).alias("customer_id"),
        F.round(F.rand() * 5000, 2).alias("amount"),
        F.when(F.rand() < 0.7, "completed")
         .when(F.rand() < 0.85, "pending")
         .otherwise("cancelled").alias("status"),
        F.element_at(F.array(*[F.lit(c) for c in
            ["electronics", "clothing", "food", "travel", "entertainment"]]),
            (F.expr("id % 5 + 1")).cast(IntegerType())).alias("category"),
        F.current_timestamp().alias("transaction_date"),
    )

    df.write.format("delta").mode("overwrite").save(base_path)
    elapsed = time.time() - start
    row_count = spark.read.format("delta").load(base_path).count()
    print(f"  ✅ Created: {row_count} rows in {elapsed:.1f}s")
    results.append({"op": "CREATE", "rows": row_count, "time_s": elapsed})

    # --- INSERT: Add more rows ---
    print("\n▶ INSERT: Adding 10,000 rows")
    start = time.time()

    new_df = spark.range(50001, 60001).select(
        F.col("id").cast(IntegerType()),
        F.concat(F.lit("CUST-"), F.lpad(F.expr("id % 5000 + 1").cast("string"), 5, "0")).alias("customer_id"),
        F.round(F.rand() * 5000, 2).alias("amount"),
        F.lit("completed").alias("status"),
        F.lit("electronics").alias("category"),
        F.current_timestamp().alias("transaction_date"),
    )
    new_df.write.format("delta").mode("append").save(base_path)
    elapsed = time.time() - start
    total = spark.read.format("delta").load(base_path).count()
    print(f"  ✅ Inserted: now {total} rows in {elapsed:.1f}s")
    results.append({"op": "INSERT", "rows_added": 10000, "total": total, "time_s": elapsed})

    # --- UPDATE: Modify rows ---
    print("\n▶ UPDATE: Setting status='refunded' WHERE amount > 4000")
    start = time.time()

    dt = DeltaTable.forPath(spark, base_path)
    dt.update(
        condition="amount > 4000",
        set={"status": F.lit("refunded")}
    )
    elapsed = time.time() - start
    refunded = spark.read.format("delta").load(base_path).filter("status = 'refunded'").count()
    print(f"  ✅ Updated: {refunded} rows refunded in {elapsed:.1f}s")
    results.append({"op": "UPDATE", "rows_affected": refunded, "time_s": elapsed})

    # --- DELETE: Remove rows ---
    print("\n▶ DELETE: Removing status='cancelled' rows")
    start = time.time()

    before = spark.read.format("delta").load(base_path).count()
    dt.delete("status = 'cancelled'")
    after = spark.read.format("delta").load(base_path).count()
    elapsed = time.time() - start
    deleted = before - after
    print(f"  ✅ Deleted: {deleted} rows in {elapsed:.1f}s (remaining: {after})")
    results.append({"op": "DELETE", "rows_deleted": deleted, "remaining": after, "time_s": elapsed})

    # --- MERGE: Upsert ---
    print("\n▶ MERGE: Upsert 5,000 rows (2,500 new + 2,500 updates)")
    start = time.time()

    merge_df = spark.range(58000, 63000).select(
        F.col("id").cast(IntegerType()),
        F.concat(F.lit("CUST-"), F.lpad(F.expr("id % 5000 + 1").cast("string"), 5, "0")).alias("customer_id"),
        F.round(F.rand() * 3000, 2).alias("amount"),
        F.lit("completed").alias("status"),
        F.lit("food").alias("category"),
        F.current_timestamp().alias("transaction_date"),
    )

    dt.alias("target").merge(
        merge_df.alias("source"),
        "target.id = source.id"
    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

    elapsed = time.time() - start
    final_count = spark.read.format("delta").load(base_path).count()
    print(f"  ✅ Merged in {elapsed:.1f}s (final count: {final_count})")
    results.append({"op": "MERGE", "final_count": final_count, "time_s": elapsed})

    # --- Verify Delta Log ---
    print("\n▶ VERIFY: Delta transaction log")
    history = spark.sql(f"DESCRIBE HISTORY delta.`{base_path}`").select(
        "version", "timestamp", "operation", "operationMetrics"
    ).collect()
    print(f"  Versions: {len(history)}")
    for h in history[:5]:
        print(f"    v{h.version}: {h.operation} @ {h.timestamp}")

    # Save results
    print(f"\n📊 Results saved to: {args.output}")
    with open(args.output, "w") as f:
        json.dump({"operations": results, "final_row_count": final_count,
                   "versions": len(history)}, f, indent=2, default=str)

    spark.stop()


if __name__ == "__main__":
    main()

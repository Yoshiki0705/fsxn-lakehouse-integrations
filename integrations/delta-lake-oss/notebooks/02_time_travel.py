"""
FSx for ONTAP Delta Lake OSS — Time Travel Verification

Queries historical versions of Delta tables on FSx for ONTAP.
Demonstrates versionAsOf, timestampAsOf, and RESTORE TABLE.

Usage:
    spark-submit --packages io.delta:delta-spark_2.12:3.1.0 \
        02_time_travel.py --s3-ap-alias <alias>
"""

import argparse
import json
import time

from delta.tables import DeltaTable
from pyspark.sql import SparkSession
from pyspark.sql import functions as F


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--s3-ap-alias", required=True)
    parser.add_argument("--output", default="/tmp/delta_time_travel_results.json")
    args = parser.parse_args()

    spark = SparkSession.builder.appName("Delta Time Travel").getOrCreate()
    base_path = f"s3a://{args.s3_ap_alias}/delta/transactions"
    results = []

    print("=" * 60)
    print("FSx for ONTAP Delta Lake OSS — Time Travel Verification")
    print("=" * 60)

    # Get current version info
    dt = DeltaTable.forPath(spark, base_path)
    history = dt.history().select("version", "timestamp", "operation").collect()
    current_version = history[0].version
    print(f"Current version: {current_version}")
    print(f"History: {len(history)} versions")

    # --- Query by version ---
    print(f"\n▶ Query version 0 (initial state)")
    start = time.time()
    v0_df = spark.read.format("delta").option("versionAsOf", 0).load(base_path)
    v0_count = v0_df.count()
    elapsed = time.time() - start
    print(f"  Version 0: {v0_count} rows ({elapsed:.1f}s)")
    results.append({"query": "versionAsOf=0", "rows": v0_count, "time_s": elapsed})

    # --- Query current version ---
    print(f"\n▶ Query current version ({current_version})")
    start = time.time()
    current_df = spark.read.format("delta").load(base_path)
    current_count = current_df.count()
    elapsed = time.time() - start
    print(f"  Current: {current_count} rows ({elapsed:.1f}s)")
    results.append({"query": f"current (v{current_version})", "rows": current_count, "time_s": elapsed})

    # --- Query by timestamp ---
    if len(history) > 1:
        ts = history[1].timestamp.isoformat()
        print(f"\n▶ Query by timestamp: {ts}")
        start = time.time()
        ts_df = spark.read.format("delta").option("timestampAsOf", ts).load(base_path)
        ts_count = ts_df.count()
        elapsed = time.time() - start
        print(f"  At {ts}: {ts_count} rows ({elapsed:.1f}s)")
        results.append({"query": f"timestampAsOf={ts}", "rows": ts_count, "time_s": elapsed})

    # --- Compare versions ---
    print(f"\n▶ Version comparison: v0 ({v0_count}) vs current ({current_count})")
    diff = current_count - v0_count
    print(f"  Difference: {diff:+d} rows")

    # --- RESTORE to version 0 (then restore back) ---
    print(f"\n▶ RESTORE TABLE to version 0")
    start = time.time()
    spark.sql(f"RESTORE TABLE delta.`{base_path}` TO VERSION AS OF 0")
    elapsed = time.time() - start
    restored_count = spark.read.format("delta").load(base_path).count()
    print(f"  ✅ Restored to v0: {restored_count} rows ({elapsed:.1f}s)")
    results.append({"query": "RESTORE TO v0", "rows": restored_count, "time_s": elapsed})

    # Restore back to latest
    print(f"\n▶ RESTORE back to version {current_version}")
    spark.sql(f"RESTORE TABLE delta.`{base_path}` TO VERSION AS OF {current_version}")
    final_count = spark.read.format("delta").load(base_path).count()
    print(f"  ✅ Restored back: {final_count} rows")

    # Save results
    with open(args.output, "w") as f:
        json.dump({"results": results, "versions": len(history)}, f, indent=2, default=str)
    print(f"\n📊 Results: {args.output}")

    spark.stop()


if __name__ == "__main__":
    main()

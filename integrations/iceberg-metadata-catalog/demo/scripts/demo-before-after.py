#!/usr/bin/env python3
"""
demo-before-after.py — Before/After Search Time Comparison

Demonstrates the dramatic improvement in file discovery time:
  Before: ListObjectsV2 scan (linear with file count)
  After:  Athena SQL on Iceberg metadata (constant time)

Usage:
    python demo-before-after.py --ap-alias <ALIAS> --region ap-northeast-1
"""

import argparse
import json
import time

import boto3


def main():
    parser = argparse.ArgumentParser(description="Before/After Search Comparison")
    parser.add_argument("--ap-alias", required=True)
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--search-term", default="invoice")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=args.region)
    athena = boto3.client("athena", region_name=args.region)

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Before/After: File Discovery Time Comparison               ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # =========================================================================
    # BEFORE: ListObjectsV2 scan
    # =========================================================================
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  BEFORE: Search using S3 ListObjectsV2                       │")
    print("│  Method: List all objects, filter client-side                 │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print(f"  Searching for '{args.search_term}' in all files...")

    start = time.time()
    paginator = s3.get_paginator("list_objects_v2")
    found_files = []
    total_objects = 0

    for page in paginator.paginate(Bucket=args.ap_alias):
        for obj in page.get("Contents", []):
            total_objects += 1
            if args.search_term.lower() in obj["Key"].lower():
                found_files.append(obj)

    before_time_ms = (time.time() - start) * 1000

    print(f"  Objects scanned: {total_objects}")
    print(f"  Matches found:   {len(found_files)}")
    for f in found_files[:3]:
        print(f"    → {f['Key']} ({f['Size']} bytes)")
    print()
    print(f"  ⏱️  Time: {before_time_ms:.0f} ms")
    print(f"  ⚠️  Scales linearly: 100K files ≈ {before_time_ms * 100000 / max(total_objects, 1) / 1000:.0f} seconds")
    print()

    # =========================================================================
    # AFTER: Athena SQL query
    # =========================================================================
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  AFTER: Search using Athena SQL on Iceberg Metadata          │")
    print("│  Method: Indexed metadata query (constant time)              │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print(f"  Searching for '{args.search_term}' in metadata catalog...")

    query = f"""SELECT file_name, file_path, classification, confidence_score
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE (file_name LIKE '%{args.search_term}%' OR classification LIKE '%{args.search_term}%')
  AND is_deleted = false
LIMIT 10"""

    start = time.time()
    query_id = athena.start_query_execution(
        QueryString=query,
        WorkGroup="primary",
        ResultConfiguration={"OutputLocation": f"s3://fsxn-athena-verification-results-{args.region}/demo/"},
    )["QueryExecutionId"]

    # Wait for completion
    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]["State"]
        if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(0.5)

    after_time_ms = (time.time() - start) * 1000

    if status == "SUCCEEDED":
        results = athena.get_query_results(QueryExecutionId=query_id)
        rows = results["ResultSet"]["Rows"]
        print(f"  Results found: {len(rows) - 1}")
        for row in rows[1:4]:
            values = [col.get("VarCharValue", "") for col in row["Data"]]
            print(f"    → {values[0]} | {values[2]} (confidence: {values[3]})")
        print()
        print(f"  ⏱️  Time: {after_time_ms:.0f} ms")
        print(f"  ✅ Constant time regardless of file count (Iceberg metadata scan only)")
    else:
        print(f"  ⚠️  Query {status}")
        after_time_ms = 0

    # =========================================================================
    # Comparison
    # =========================================================================
    print()
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  COMPARISON                                                   │")
    print("├──────────────────────────────────────────────────────────────┤")
    if after_time_ms > 0:
        speedup = before_time_ms / after_time_ms if after_time_ms > 0 else 0
        print(f"│  Before (ListObjectsV2): {before_time_ms:>8.0f} ms                       │")
        print(f"│  After  (Athena SQL):    {after_time_ms:>8.0f} ms                       │")
        print(f"│  Speedup:                {speedup:>8.1f}x                       │")
        print(f"│                                                              │")
        print(f"│  At 100K files:  Before ≈ {before_time_ms * 100000 / max(total_objects, 1) / 1000:>5.0f}s  |  After ≈ {after_time_ms / 1000:>4.1f}s     │")
        print(f"│  At 1M files:    Before ≈ {before_time_ms * 1000000 / max(total_objects, 1) / 1000:>5.0f}s  |  After ≈ {after_time_ms / 1000:>4.1f}s     │")
    print("└──────────────────────────────────────────────────────────────┘")


if __name__ == "__main__":
    main()

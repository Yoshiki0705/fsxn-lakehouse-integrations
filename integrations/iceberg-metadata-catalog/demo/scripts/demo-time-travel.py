#!/usr/bin/env python3
"""
demo-time-travel.py — Iceberg Time Travel Demo

Shows Iceberg snapshot history and demonstrates querying historical states.
Key message: "You can see exactly when each change happened and go back in time."

Usage:
    python demo-time-travel.py --region ap-northeast-1
"""

import argparse
import json
import time

import boto3


def main():
    parser = argparse.ArgumentParser(description="Iceberg Time Travel Demo")
    parser.add_argument("--region", default="ap-northeast-1")
    args = parser.parse_args()

    athena = boto3.client("athena", region_name=args.region)
    output_location = f"s3://fsxn-athena-verification-results-{args.region}/demo/"

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Iceberg Time Travel: Snapshot History                       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("  Every write to the metadata catalog creates an Iceberg snapshot.")
    print("  You can query any historical state — no additional storage cost.")
    print()

    # Query snapshot history
    query = """SELECT
  made_current_at,
  snapshot_id,
  parent_id,
  is_current_ancestor
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files$history"
ORDER BY made_current_at DESC
LIMIT 10"""

    query_id = athena.start_query_execution(
        QueryString=query,
        WorkGroup="primary",
        ResultConfiguration={"OutputLocation": output_location},
    )["QueryExecutionId"]

    while True:
        status = athena.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]["State"]
        if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(0.5)

    if status == "SUCCEEDED":
        results = athena.get_query_results(QueryExecutionId=query_id)
        rows = results["ResultSet"]["Rows"]

        print("  ┌─────────────────────────────────────────────────────────┐")
        print("  │  Snapshot History (most recent first)                    │")
        print("  ├─────────────────────────────┬───────────────────────────┤")
        print("  │  Timestamp                   │  Snapshot ID              │")
        print("  ├─────────────────────────────┼───────────────────────────┤")
        for row in rows[1:]:
            values = [col.get("VarCharValue", "") for col in row["Data"]]
            ts = values[0][:19] if values[0] else ""
            sid = values[1][:18] if values[1] else ""
            print(f"  │  {ts:<27} │  {sid:<25} │")
        print("  └─────────────────────────────┴───────────────────────────┘")
        print()
        print(f"  Total snapshots: {len(rows) - 1}")
        print()
        print("  Key points:")
        print("  • Each metadata write (scan, enrichment, delete) creates a snapshot")
        print("  • Query any past state: SELECT * FROM table FOR TIMESTAMP AS OF '...'")
        print("  • No additional storage cost (Iceberg uses shared data files)")
        print("  • S3 Tables auto-expires old snapshots (configurable retention)")
    else:
        print(f"  ⚠️  Query {status}. Ensure Glue catalog is registered.")


if __name__ == "__main__":
    main()

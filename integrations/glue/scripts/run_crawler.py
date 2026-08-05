#!/usr/bin/env python3
"""
FSx for ONTAP Glue Integration — Glue Crawler Execution and Verification

Starts Glue Crawler, waits for completion, and verifies discovered tables
match expected schemas for the bronze layer.

Usage:
    python run_crawler.py [--crawler-name fsxn-glue-crawler-dev] [--wait]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def load_params() -> dict:
    """Load parameters from params.json."""
    params_file = Path(__file__).parent.parent / "params.json"
    if params_file.exists():
        with open(params_file) as f:
            return json.load(f)
    return {}


def start_crawler(glue_client, crawler_name: str) -> bool:
    """Start the Glue Crawler."""
    try:
        glue_client.start_crawler(Name=crawler_name)
        print(f"  ✅ Crawler '{crawler_name}' started")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "CrawlerRunningException":
            print(f"  ⚠️  Crawler is already running")
            return True
        print(f"  ❌ Failed to start crawler: {e.response['Error']['Message']}")
        return False


def wait_for_crawler(glue_client, crawler_name: str, timeout: int = 600) -> str:
    """Wait for Crawler to complete."""
    print(f"  ⏳ Waiting for crawler to complete (timeout: {timeout}s)...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        response = glue_client.get_crawler(Name=crawler_name)
        state = response["Crawler"]["State"]

        if state == "READY":
            last_crawl = response["Crawler"].get("LastCrawl", {})
            status = last_crawl.get("Status", "UNKNOWN")
            elapsed = time.time() - start_time
            print(f"\n  ✅ Crawler completed in {elapsed:.0f}s — Status: {status}")

            if status == "SUCCEEDED":
                print(f"     Tables created: {last_crawl.get('TablesCreated', 0)}")
                print(f"     Tables updated: {last_crawl.get('TablesUpdated', 0)}")
                print(f"     Partitions created: {last_crawl.get('PartitionsCreated', 0)}")
            elif status == "FAILED":
                print(f"     Error: {last_crawl.get('ErrorMessage', 'Unknown')}")

            return status

        # Still running
        elapsed = time.time() - start_time
        sys.stdout.write(f"\r  ⏳ State: {state} ({elapsed:.0f}s elapsed)...")
        sys.stdout.flush()
        time.sleep(10)

    print(f"\n  ❌ Timeout after {timeout}s")
    return "TIMEOUT"


def verify_tables(glue_client, database_name: str) -> dict:
    """Verify discovered tables and their schemas."""
    print(f"\n📋 Verifying discovered tables in '{database_name}'...")

    response = glue_client.get_tables(DatabaseName=database_name)
    tables = response.get("TableList", [])

    if not tables:
        print("  ❌ No tables found")
        return {"tables": [], "valid": False}

    expected_tables = {
        "transactions": {
            "format": "parquet",
            "min_columns": 6,
            "partitioned": True,
        },
        "customers": {
            "format": "csv",
            "min_columns": 4,
            "partitioned": False,
        },
        "events": {
            "format": "json",
            "min_columns": 4,
            "partitioned": False,
        },
    }

    results = []
    for table in tables:
        name = table["Name"]
        sd = table.get("StorageDescriptor", {})
        columns = sd.get("Columns", [])
        partition_keys = table.get("PartitionKeys", [])
        input_format = sd.get("InputFormat", "")
        location = sd.get("Location", "")

        # Determine format
        if "parquet" in input_format.lower() or "parquet" in location.lower():
            detected_format = "parquet"
        elif "csv" in input_format.lower() or "csv" in location.lower():
            detected_format = "csv"
        elif "json" in input_format.lower() or "json" in location.lower():
            detected_format = "json"
        else:
            detected_format = "unknown"

        table_result = {
            "name": name,
            "columns": len(columns),
            "column_names": [c["Name"] for c in columns],
            "partition_keys": len(partition_keys),
            "format": detected_format,
            "location": location,
            "valid": True,
        }

        # Validate against expected
        if name in expected_tables:
            expected = expected_tables[name]
            if len(columns) < expected["min_columns"]:
                table_result["valid"] = False
                table_result["issue"] = f"Expected >= {expected['min_columns']} columns, got {len(columns)}"
            if expected["partitioned"] and len(partition_keys) == 0:
                table_result["valid"] = False
                table_result["issue"] = "Expected partitions but none found"

        status = "✅" if table_result["valid"] else "❌"
        print(f"  {status} {name}: {len(columns)} cols, {len(partition_keys)} partitions, {detected_format}")
        if columns:
            col_names = [c["Name"] for c in columns[:5]]
            print(f"     Columns: {', '.join(col_names)}{'...' if len(columns) > 5 else ''}")
        if partition_keys:
            pk_names = [p["Name"] for p in partition_keys]
            print(f"     Partitions: {', '.join(pk_names)}")

        results.append(table_result)

    all_valid = all(r["valid"] for r in results)
    return {"tables": results, "valid": all_valid}


def main():
    parser = argparse.ArgumentParser(description="Run Glue Crawler and verify results")
    parser.add_argument("--crawler-name", default=None)
    parser.add_argument("--database", default=None)
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--wait", action="store_true", default=True)
    parser.add_argument("--no-wait", action="store_true", default=False)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    params = load_params()
    crawler_name = args.crawler_name or params.get("CrawlerName", "fsxn-glue-crawler-dev")
    database_name = args.database or params.get("DatabaseName", "fsxn_glue_db")
    region = params.get("Region", args.region)

    print("=" * 60)
    print("FSx for ONTAP Glue Integration — Crawler Execution")
    print("=" * 60)
    print(f"Crawler:  {crawler_name}")
    print(f"Database: {database_name}")
    print(f"Region:   {region}")

    glue_client = boto3.client("glue", region_name=region)

    # Start crawler
    print("\n🕷️ Starting Crawler...")
    if not start_crawler(glue_client, crawler_name):
        sys.exit(1)

    # Wait for completion
    if not args.no_wait:
        status = wait_for_crawler(glue_client, crawler_name, args.timeout)
        if status not in ("SUCCEEDED",):
            print(f"\n❌ Crawler did not succeed: {status}")
            sys.exit(1)

    # Verify tables
    verification = verify_tables(glue_client, database_name)

    # Save results
    output_path = Path(__file__).parent.parent / "tests" / "results" / "crawler_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(verification, f, indent=2)

    print(f"\n📊 Results saved to: {output_path}")

    if not verification["valid"]:
        print("\n❌ Some tables did not pass validation")
        sys.exit(1)

    print("\n✅ All tables validated successfully")


if __name__ == "__main__":
    main()

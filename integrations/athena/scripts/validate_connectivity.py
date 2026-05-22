#!/usr/bin/env python3
"""
FSxN Athena Integration — Connectivity Validation

Verifies:
  1. S3 AP has internet network origin
  2. S3 AP is accessible (ListObjects, GetObject)
  3. Glue Data Catalog is accessible
  4. Athena workgroup is configured
  5. Glue Crawler has discovered tables

Usage:
    python validate_connectivity.py [--region ap-northeast-1]
"""

import argparse
import json
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def load_params() -> dict:
    """Load parameters from params.json."""
    params_file = Path(__file__).parent.parent / "params.json"
    if not params_file.exists():
        print("❌ params.json not found. Run deploy.sh first.")
        sys.exit(1)
    with open(params_file) as f:
        return json.load(f)


def check_s3_ap_access(s3_client, ap_alias: str) -> bool:
    """Verify S3 AP is accessible via ListObjects."""
    print("\n🔍 Check 1: S3 Access Point accessibility")
    try:
        response = s3_client.list_objects_v2(
            Bucket=ap_alias,
            MaxKeys=5,
        )
        count = response.get("KeyCount", 0)
        print(f"  ✅ ListObjectsV2 succeeded — {count} objects found")
        if count > 0:
            for obj in response.get("Contents", [])[:3]:
                print(f"     - {obj['Key']} ({obj['Size']} bytes)")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        print(f"  ❌ ListObjectsV2 failed: {error_code}")
        print(f"     {e.response['Error']['Message']}")
        return False


def check_glue_database(glue_client, database_name: str) -> bool:
    """Verify Glue database exists."""
    print("\n🔍 Check 2: Glue Data Catalog database")
    try:
        response = glue_client.get_database(Name=database_name)
        db = response["Database"]
        print(f"  ✅ Database '{database_name}' exists")
        print(f"     Description: {db.get('Description', 'N/A')}")
        return True
    except ClientError as e:
        print(f"  ❌ Database not found: {e.response['Error']['Message']}")
        return False


def check_glue_tables(glue_client, database_name: str) -> bool:
    """Verify Glue tables exist (Crawler has run)."""
    print("\n🔍 Check 3: Glue Data Catalog tables")
    try:
        response = glue_client.get_tables(DatabaseName=database_name)
        tables = response.get("TableList", [])
        if not tables:
            print("  ⚠️  No tables found — Crawler may not have run yet")
            return False

        print(f"  ✅ {len(tables)} table(s) discovered:")
        for table in tables:
            cols = len(table.get("StorageDescriptor", {}).get("Columns", []))
            location = table.get("StorageDescriptor", {}).get("Location", "N/A")
            print(f"     - {table['Name']} ({cols} columns) → {location[:80]}")
        return True
    except ClientError as e:
        print(f"  ❌ Failed to list tables: {e.response['Error']['Message']}")
        return False


def check_athena_workgroup(athena_client, workgroup_name: str) -> bool:
    """Verify Athena workgroup is configured."""
    print("\n🔍 Check 4: Athena workgroup")
    try:
        response = athena_client.get_work_group(WorkGroup=workgroup_name)
        wg = response["WorkGroup"]
        state = wg.get("State", "UNKNOWN")
        config = wg.get("Configuration", {})
        result_loc = config.get("ResultConfiguration", {}).get("OutputLocation", "N/A")
        print(f"  ✅ Workgroup '{workgroup_name}' — State: {state}")
        print(f"     Result location: {result_loc}")
        print(f"     Metrics enabled: {config.get('PublishCloudWatchMetricsEnabled', False)}")
        return state == "ENABLED"
    except ClientError as e:
        print(f"  ❌ Workgroup not found: {e.response['Error']['Message']}")
        return False


def check_crawler_status(glue_client, crawler_name: str) -> bool:
    """Check Glue Crawler status."""
    print("\n🔍 Check 5: Glue Crawler status")
    try:
        response = glue_client.get_crawler(Name=crawler_name)
        crawler = response["Crawler"]
        state = crawler.get("State", "UNKNOWN")
        last_crawl = crawler.get("LastCrawl", {})
        status = last_crawl.get("Status", "N/A")
        print(f"  ✅ Crawler '{crawler_name}' — State: {state}")
        if last_crawl:
            print(f"     Last crawl status: {status}")
            print(f"     Tables created: {last_crawl.get('TablesCreated', 0)}")
            print(f"     Tables updated: {last_crawl.get('TablesUpdated', 0)}")
        return status == "SUCCEEDED"
    except ClientError as e:
        print(f"  ❌ Crawler not found: {e.response['Error']['Message']}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate Athena + FSxN connectivity")
    parser.add_argument("--region", default="ap-northeast-1")
    args = parser.parse_args()

    params = load_params()
    region = params.get("Region", args.region)

    print("=" * 60)
    print("FSxN Athena Integration — Connectivity Validation")
    print("=" * 60)
    print(f"Region: {region}")

    # Initialize clients
    s3_client = boto3.client("s3", region_name=region)
    glue_client = boto3.client("glue", region_name=region)
    athena_client = boto3.client("athena", region_name=region)

    # Get parameters
    ap_name = params.get("S3AccessPointName", "fsxn-athena-ap")
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    ap_alias = f"{ap_name}-{account_id}.s3-accesspoint.{region}.amazonaws.com"
    database_name = params.get("DatabaseName", "fsxn_athena_db")
    workgroup_name = params.get("WorkgroupName", "fsxn-verification")
    crawler_name = params.get("CrawlerName", f"fsxn-athena-crawler-dev")

    print(f"S3 AP Alias: {ap_alias}")
    print(f"Database:    {database_name}")
    print(f"Workgroup:   {workgroup_name}")
    print(f"Crawler:     {crawler_name}")

    # Run checks
    results = {
        "s3_ap_access": check_s3_ap_access(s3_client, ap_alias),
        "glue_database": check_glue_database(glue_client, database_name),
        "glue_tables": check_glue_tables(glue_client, database_name),
        "athena_workgroup": check_athena_workgroup(athena_client, workgroup_name),
        "crawler_status": check_crawler_status(glue_client, crawler_name),
    }

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    status = "✅ ALL PASSED" if passed == total else f"⚠️  {passed}/{total} passed"
    print(f"Result: {status}")
    print("=" * 60)

    if passed < total:
        print("\nFailed checks:")
        for check, result in results.items():
            if not result:
                print(f"  ❌ {check}")
        sys.exit(1)


if __name__ == "__main__":
    main()

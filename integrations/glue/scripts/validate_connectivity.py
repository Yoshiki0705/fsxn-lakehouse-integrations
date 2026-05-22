#!/usr/bin/env python3
"""
FSxN Glue Integration — Connectivity Validation

Verifies:
  1. S3 Access Point is accessible (internet origin)
  2. Glue Data Catalog database exists
  3. Glue Crawler exists and is configured
  4. Bronze → Silver ETL job exists
  5. Silver → Gold ETL job exists
  6. EventBridge rule exists

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
            Prefix="bronze/",
            MaxKeys=5,
        )
        count = response.get("KeyCount", 0)
        print(f"  ✅ ListObjectsV2 succeeded — {count} objects found in bronze/")
        if count > 0:
            for obj in response.get("Contents", [])[:3]:
                print(f"     - {obj['Key']} ({obj['Size']} bytes)")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        print(f"  ❌ ListObjectsV2 failed: {error_code}")
        print(f"     {e.response['Error']['Message']}")
        if error_code == "NoSuchBucket":
            print("     Hint: S3 AP may not be created yet. Run deploy.sh first.")
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


def check_glue_crawler(glue_client, crawler_name: str) -> bool:
    """Verify Glue Crawler exists and is configured."""
    print("\n🔍 Check 3: Glue Crawler")
    try:
        response = glue_client.get_crawler(Name=crawler_name)
        crawler = response["Crawler"]
        state = crawler.get("State", "UNKNOWN")
        targets = crawler.get("Targets", {}).get("S3Targets", [])
        last_crawl = crawler.get("LastCrawl", {})

        print(f"  ✅ Crawler '{crawler_name}' exists — State: {state}")
        if targets:
            print(f"     Target: {targets[0].get('Path', 'N/A')}")
        if last_crawl:
            print(f"     Last crawl: {last_crawl.get('Status', 'N/A')}")
            print(f"     Tables created: {last_crawl.get('TablesCreated', 0)}")
        return True
    except ClientError as e:
        print(f"  ❌ Crawler not found: {e.response['Error']['Message']}")
        return False


def check_etl_job(glue_client, job_name: str, label: str) -> bool:
    """Verify Glue ETL job exists."""
    print(f"\n🔍 Check: {label} ETL Job")
    try:
        response = glue_client.get_job(JobName=job_name)
        job = response["Job"]
        glue_version = job.get("GlueVersion", "N/A")
        worker_type = job.get("WorkerType", "N/A")
        num_workers = job.get("NumberOfWorkers", "N/A")
        script_location = job.get("Command", {}).get("ScriptLocation", "N/A")
        bookmark = job.get("DefaultArguments", {}).get("--job-bookmark-option", "N/A")

        print(f"  ✅ Job '{job_name}' exists")
        print(f"     Glue Version: {glue_version}")
        print(f"     Workers: {num_workers} × {worker_type}")
        print(f"     Script: {script_location}")
        print(f"     Bookmarks: {bookmark}")
        return True
    except ClientError as e:
        print(f"  ❌ Job not found: {e.response['Error']['Message']}")
        return False


def check_eventbridge_rule(events_client, rule_name: str) -> bool:
    """Verify EventBridge rule exists."""
    print("\n🔍 Check 6: EventBridge Schedule Rule")
    try:
        response = events_client.describe_rule(Name=rule_name)
        state = response.get("State", "UNKNOWN")
        schedule = response.get("ScheduleExpression", "N/A")
        print(f"  ✅ Rule '{rule_name}' exists — State: {state}")
        print(f"     Schedule: {schedule}")
        return True
    except ClientError as e:
        print(f"  ❌ Rule not found: {e.response['Error']['Message']}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate Glue + FSxN connectivity")
    parser.add_argument("--region", default="ap-northeast-1")
    args = parser.parse_args()

    params = load_params()
    region = params.get("Region", args.region)

    print("=" * 60)
    print("FSxN Glue Integration — Connectivity Validation")
    print("=" * 60)
    print(f"Region: {region}")

    # Initialize clients
    s3_client = boto3.client("s3", region_name=region)
    glue_client = boto3.client("glue", region_name=region)
    events_client = boto3.client("events", region_name=region)

    # Get parameters
    ap_name = params.get("S3AccessPointName", "fsxn-glue-ap")
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    ap_alias = f"{ap_name}-{account_id}.s3-accesspoint.{region}.amazonaws.com"
    database_name = params.get("DatabaseName", "fsxn_glue_db")
    crawler_name = params.get("CrawlerName", "fsxn-glue-crawler-dev")
    bronze_to_silver_job = params.get("BronzeToSilverJob", "fsxn-bronze-to-silver-dev")
    silver_to_gold_job = params.get("SilverToGoldJob", "fsxn-silver-to-gold-dev")
    environment = params.get("Environment", "dev")
    rule_name = f"fsxn-glue-etl-schedule-{environment}"

    print(f"S3 AP Alias:        {ap_alias}")
    print(f"Database:           {database_name}")
    print(f"Crawler:            {crawler_name}")
    print(f"Bronze→Silver Job:  {bronze_to_silver_job}")
    print(f"Silver→Gold Job:    {silver_to_gold_job}")
    print(f"EventBridge Rule:   {rule_name}")

    # Run checks
    results = {
        "s3_ap_access": check_s3_ap_access(s3_client, ap_alias),
        "glue_database": check_glue_database(glue_client, database_name),
        "glue_crawler": check_glue_crawler(glue_client, crawler_name),
        "bronze_to_silver_job": check_etl_job(glue_client, bronze_to_silver_job, "Bronze→Silver"),
        "silver_to_gold_job": check_etl_job(glue_client, silver_to_gold_job, "Silver→Gold"),
        "eventbridge_rule": check_eventbridge_rule(events_client, rule_name),
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

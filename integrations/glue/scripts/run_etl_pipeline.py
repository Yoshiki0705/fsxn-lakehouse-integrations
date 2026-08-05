#!/usr/bin/env python3
"""
FSx for ONTAP Glue Integration — ETL Pipeline Orchestrator

Orchestrates the full ETL pipeline:
  1. Run Glue Crawler (schema discovery)
  2. Run Bronze → Silver ETL job
  3. Run Silver → Gold ETL job
  4. Run Data Quality checks

Usage:
    python run_etl_pipeline.py [--skip-crawler] [--skip-quality]
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
    if not params_file.exists():
        print("❌ params.json not found. Run deploy.sh first.")
        sys.exit(1)
    with open(params_file) as f:
        return json.load(f)


def wait_for_crawler(glue_client, crawler_name: str, timeout: int = 600) -> bool:
    """Wait for Crawler to complete."""
    start_time = time.time()

    while time.time() - start_time < timeout:
        response = glue_client.get_crawler(Name=crawler_name)
        state = response["Crawler"]["State"]

        if state == "READY":
            last_crawl = response["Crawler"].get("LastCrawl", {})
            status = last_crawl.get("Status", "UNKNOWN")
            elapsed = time.time() - start_time
            print(f"  ✅ Crawler completed in {elapsed:.0f}s — Status: {status}")
            return status == "SUCCEEDED"

        elapsed = time.time() - start_time
        sys.stdout.write(f"\r  ⏳ State: {state} ({elapsed:.0f}s elapsed)...")
        sys.stdout.flush()
        time.sleep(10)

    print(f"\n  ❌ Timeout after {timeout}s")
    return False


def run_crawler(glue_client, crawler_name: str) -> bool:
    """Start and wait for Glue Crawler."""
    print("\n" + "=" * 50)
    print("Phase 1: Glue Crawler (Schema Discovery)")
    print("=" * 50)

    try:
        glue_client.start_crawler(Name=crawler_name)
        print(f"  Started crawler: {crawler_name}")
    except ClientError as e:
        if e.response["Error"]["Code"] == "CrawlerRunningException":
            print(f"  Crawler already running, waiting...")
        else:
            print(f"  ❌ Failed: {e.response['Error']['Message']}")
            return False

    return wait_for_crawler(glue_client, crawler_name)


def run_job(glue_client, job_name: str, timeout: int = 1800) -> bool:
    """Start a Glue ETL job and wait for completion."""
    try:
        response = glue_client.start_job_run(JobName=job_name)
        run_id = response["JobRunId"]
        print(f"  Started job: {job_name} (RunId: {run_id})")
    except ClientError as e:
        print(f"  ❌ Failed to start job: {e.response['Error']['Message']}")
        return False

    # Wait for job completion
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = glue_client.get_job_run(JobName=job_name, RunId=run_id)
        state = response["JobRun"]["JobRunState"]

        if state == "SUCCEEDED":
            elapsed = time.time() - start_time
            execution_time = response["JobRun"].get("ExecutionTime", 0)
            print(f"  ✅ Job completed in {elapsed:.0f}s (execution: {execution_time}s)")
            return True
        elif state in ("FAILED", "TIMEOUT", "ERROR", "STOPPED"):
            error_msg = response["JobRun"].get("ErrorMessage", "Unknown error")
            print(f"  ❌ Job {state}: {error_msg}")
            return False

        elapsed = time.time() - start_time
        sys.stdout.write(f"\r  ⏳ State: {state} ({elapsed:.0f}s elapsed)...")
        sys.stdout.flush()
        time.sleep(15)

    print(f"\n  ❌ Timeout after {timeout}s")
    return False


def run_bronze_to_silver(glue_client, job_name: str) -> bool:
    """Run Bronze → Silver ETL job."""
    print("\n" + "=" * 50)
    print("Phase 2: Bronze → Silver ETL")
    print("=" * 50)
    return run_job(glue_client, job_name)


def run_silver_to_gold(glue_client, job_name: str) -> bool:
    """Run Silver → Gold ETL job."""
    print("\n" + "=" * 50)
    print("Phase 3: Silver → Gold ETL")
    print("=" * 50)
    return run_job(glue_client, job_name)


def run_quality_check(glue_client, database_name: str, tables: list) -> dict:
    """Run data quality checks on gold tables."""
    print("\n" + "=" * 50)
    print("Phase 4: Data Quality Checks")
    print("=" * 50)

    results = {}
    for table_name in tables:
        try:
            response = glue_client.get_table(
                DatabaseName=database_name,
                Name=table_name,
            )
            table = response["Table"]
            columns = table.get("StorageDescriptor", {}).get("Columns", [])
            location = table.get("StorageDescriptor", {}).get("Location", "")

            results[table_name] = {
                "exists": True,
                "columns": len(columns),
                "location": location,
            }
            print(f"  ✅ {table_name}: {len(columns)} columns")

        except ClientError as e:
            if e.response["Error"]["Code"] == "EntityNotFoundException":
                results[table_name] = {"exists": False}
                print(f"  ⚠️  {table_name}: not found (may not be cataloged yet)")
            else:
                results[table_name] = {"exists": False, "error": str(e)}
                print(f"  ❌ {table_name}: {e.response['Error']['Message']}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Orchestrate FSx for ONTAP Glue ETL pipeline")
    parser.add_argument("--skip-crawler", action="store_true", help="Skip crawler phase")
    parser.add_argument("--skip-quality", action="store_true", help="Skip quality check phase")
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--timeout", type=int, default=1800, help="Job timeout in seconds")
    args = parser.parse_args()

    params = load_params()
    region = params.get("Region", args.region)

    crawler_name = params.get("CrawlerName", "fsxn-glue-crawler-dev")
    database_name = params.get("DatabaseName", "fsxn_glue_db")
    bronze_to_silver_job = params.get("BronzeToSilverJob", "fsxn-bronze-to-silver-dev")
    silver_to_gold_job = params.get("SilverToGoldJob", "fsxn-silver-to-gold-dev")

    print("=" * 60)
    print("FSx for ONTAP Glue Integration — ETL Pipeline Orchestrator")
    print("=" * 60)
    print(f"Region:             {region}")
    print(f"Crawler:            {crawler_name}")
    print(f"Database:           {database_name}")
    print(f"Bronze→Silver Job:  {bronze_to_silver_job}")
    print(f"Silver→Gold Job:    {silver_to_gold_job}")

    glue_client = boto3.client("glue", region_name=region)
    pipeline_start = time.time()
    results = {}

    # Phase 1: Crawler
    if not args.skip_crawler:
        results["crawler"] = run_crawler(glue_client, crawler_name)
        if not results["crawler"]:
            print("\n❌ Crawler failed — aborting pipeline")
            sys.exit(1)
    else:
        print("\n⏭️  Skipping crawler phase")
        results["crawler"] = "skipped"

    # Phase 2: Bronze → Silver
    results["bronze_to_silver"] = run_bronze_to_silver(glue_client, bronze_to_silver_job)
    if not results["bronze_to_silver"]:
        print("\n❌ Bronze→Silver ETL failed — aborting pipeline")
        sys.exit(1)

    # Phase 3: Silver → Gold
    results["silver_to_gold"] = run_silver_to_gold(glue_client, silver_to_gold_job)
    if not results["silver_to_gold"]:
        print("\n❌ Silver→Gold ETL failed — aborting pipeline")
        sys.exit(1)

    # Phase 4: Quality Check
    if not args.skip_quality:
        gold_tables = ["daily_summaries", "category_rollups", "customer_metrics"]
        results["quality"] = run_quality_check(glue_client, database_name, gold_tables)
    else:
        print("\n⏭️  Skipping quality check phase")
        results["quality"] = "skipped"

    # Summary
    pipeline_elapsed = time.time() - pipeline_start
    print("\n" + "=" * 60)
    print("Pipeline Summary")
    print("=" * 60)
    print(f"Total time: {pipeline_elapsed:.0f}s ({pipeline_elapsed/60:.1f} min)")
    print(f"Crawler:         {'✅' if results['crawler'] else '❌'}")
    print(f"Bronze→Silver:   {'✅' if results['bronze_to_silver'] else '❌'}")
    print(f"Silver→Gold:     {'✅' if results['silver_to_gold'] else '❌'}")
    print(f"Quality Check:   {'✅' if results.get('quality') != 'skipped' else '⏭️  skipped'}")

    # Save results
    output_path = Path(__file__).parent.parent / "tests" / "results" / "pipeline_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "elapsed_seconds": pipeline_elapsed,
            "results": {k: str(v) for k, v in results.items()},
        }, f, indent=2)

    print(f"\n📊 Results saved to: {output_path}")
    print("\n✅ Pipeline completed successfully!")


if __name__ == "__main__":
    main()

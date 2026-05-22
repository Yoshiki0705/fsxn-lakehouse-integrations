#!/usr/bin/env python3
"""
FSxN DuckDB Integration — Connectivity Validation

Verifies DuckDB httpfs can connect to FSxN S3 AP and Lambda is deployed.

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
    params_file = Path(__file__).parent.parent / "params.json"
    if params_file.exists():
        return json.load(open(params_file))
    return {}


def check_lambda(lambda_client, function_name: str) -> bool:
    print("\n🔍 Check 1: Lambda function")
    try:
        resp = lambda_client.get_function(FunctionName=function_name)
        config = resp["Configuration"]
        print(f"  ✅ {function_name} — State: {config['State']}")
        print(f"     Runtime: {config['Runtime']}, Memory: {config['MemorySize']}MB")
        print(f"     Arch: {config.get('Architectures', ['x86_64'])}")
        return config["State"] == "Active"
    except ClientError as e:
        print(f"  ❌ {e.response['Error']['Message']}")
        return False


def check_lambda_invoke(lambda_client, function_name: str, ap_alias: str) -> bool:
    print("\n🔍 Check 2: Lambda invocation test")
    try:
        payload = json.dumps({
            "query": f"SELECT 1 AS test, current_timestamp AS ts",
            "max_rows": 1
        })
        resp = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="RequestResponse",
            Payload=payload,
        )
        result = json.loads(resp["Payload"].read())
        if result.get("statusCode") == 200:
            metrics = result.get("metrics", {})
            print(f"  ✅ Lambda invoked successfully")
            print(f"     Cold start: {metrics.get('cold_start')}")
            print(f"     Total time: {metrics.get('total_time_ms')}ms")
            return True
        else:
            print(f"  ❌ Lambda returned error: {result.get('error')}")
            return False
    except Exception as e:
        print(f"  ❌ Invocation failed: {e}")
        return False


def check_duckdb_s3ap(ap_alias: str, region: str) -> bool:
    print("\n🔍 Check 3: DuckDB httpfs → S3 AP connectivity")
    try:
        import duckdb
        session = boto3.Session(region_name=region)
        creds = session.get_credentials().get_frozen_credentials()

        conn = duckdb.connect(":memory:")
        conn.execute("INSTALL httpfs; LOAD httpfs;")
        conn.execute(f"SET s3_region='{region}';")
        conn.execute(f"SET s3_access_key_id='{creds.access_key}';")
        conn.execute(f"SET s3_secret_access_key='{creds.secret_key}';")
        if creds.token:
            conn.execute(f"SET s3_session_token='{creds.token}';")
        conn.execute("SET s3_url_style='path';")

        # Simple connectivity test
        result = conn.execute("SELECT 1 AS connected").fetchone()
        print(f"  ✅ DuckDB initialized, httpfs loaded")

        # Try listing files on S3 AP
        try:
            files = conn.execute(
                f"SELECT * FROM glob('s3://{ap_alias}/**') LIMIT 3"
            ).fetchall()
            print(f"  ✅ S3 AP accessible — {len(files)} files found")
            return True
        except Exception as e:
            print(f"  ⚠️  S3 AP glob failed (may be timeout): {e}")
            return False

    except ImportError:
        print("  ⚠️  duckdb not installed locally — skip local test")
        return True
    except Exception as e:
        print(f"  ❌ DuckDB setup failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", default="ap-northeast-1")
    args = parser.parse_args()

    params = load_params()
    region = params.get("Region", args.region)
    function_name = params.get("LambdaFunctionName", "fsxn-duckdb-query-dev")
    ap_alias = params.get("S3AccessPointAlias", "")

    print("=" * 60)
    print("FSxN DuckDB Integration — Connectivity Validation")
    print("=" * 60)
    print(f"Region:   {region}")
    print(f"Lambda:   {function_name}")
    print(f"S3 AP:    {ap_alias}")

    lambda_client = boto3.client("lambda", region_name=region)

    results = {
        "lambda_exists": check_lambda(lambda_client, function_name),
        "lambda_invoke": check_lambda_invoke(lambda_client, function_name, ap_alias),
        "duckdb_s3ap": check_duckdb_s3ap(ap_alias, region),
    }

    print("\n" + "=" * 60)
    passed = sum(1 for v in results.values() if v)
    print(f"Result: {passed}/{len(results)} checks passed")
    if passed < len(results):
        for k, v in results.items():
            if not v:
                print(f"  ❌ {k}")
        sys.exit(1)
    print("✅ All checks passed")


if __name__ == "__main__":
    main()

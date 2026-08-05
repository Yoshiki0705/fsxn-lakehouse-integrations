#!/usr/bin/env python3
"""
FSx for ONTAP S3 Access Point Connectivity Verification Script.

Verifies basic S3 API operations against an FSx for ONTAP S3 AP:
- ListObjectsV2
- PutObject (optional)
- GetObject
- HeadObject
- DeleteObject (optional)

Usage:
    python3 verify-s3ap-connectivity.py --ap-alias <alias> --region <region> [--write-test] [--output-yaml <path>]

Example:
    python3 verify-s3ap-connectivity.py \
        --ap-alias verification-tes-fpg5t76dgh3xchkrudk6yc4jhgzz1apn1b-ext-s3alias \
        --region ap-northeast-1 \
        --write-test \
        --output-yaml evidence/connectivity-test.yaml
"""

import argparse
import boto3
import json
import time
import yaml
import sys
from datetime import datetime, timezone


def test_list_objects(s3, bucket, prefix=""):
    """Test ListObjectsV2."""
    start = time.time()
    try:
        resp = s3.list_objects_v2(Bucket=bucket, MaxKeys=5, Prefix=prefix)
        elapsed = time.time() - start
        return {
            "operation": "ListObjectsV2",
            "result": "PASS",
            "latency_ms": round(elapsed * 1000),
            "key_count": resp.get("KeyCount", 0),
            "details": f"Returned {resp.get('KeyCount', 0)} keys"
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "operation": "ListObjectsV2",
            "result": "FAIL",
            "latency_ms": round(elapsed * 1000),
            "error": f"{type(e).__name__}: {str(e)[:200]}"
        }


def test_put_object(s3, bucket, key="__connectivity_test__.txt"):
    """Test PutObject."""
    start = time.time()
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=b"connectivity test")
        elapsed = time.time() - start
        return {
            "operation": "PutObject",
            "result": "PASS",
            "latency_ms": round(elapsed * 1000),
            "key": key,
            "details": "17 bytes written"
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "operation": "PutObject",
            "result": "FAIL",
            "latency_ms": round(elapsed * 1000),
            "error": f"{type(e).__name__}: {str(e)[:200]}"
        }


def test_get_object(s3, bucket, key):
    """Test GetObject."""
    start = time.time()
    try:
        resp = s3.get_object(Bucket=bucket, Key=key, Range="bytes=0-100")
        body = resp["Body"].read()
        elapsed = time.time() - start
        return {
            "operation": "GetObject",
            "result": "PASS",
            "latency_ms": round(elapsed * 1000),
            "key": key,
            "content_length": resp["ContentLength"],
            "details": f"Read {len(body)} bytes"
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "operation": "GetObject",
            "result": "FAIL",
            "latency_ms": round(elapsed * 1000),
            "error": f"{type(e).__name__}: {str(e)[:200]}"
        }


def test_head_object(s3, bucket, key):
    """Test HeadObject."""
    start = time.time()
    try:
        resp = s3.head_object(Bucket=bucket, Key=key)
        elapsed = time.time() - start
        return {
            "operation": "HeadObject",
            "result": "PASS",
            "latency_ms": round(elapsed * 1000),
            "key": key,
            "content_length": resp["ContentLength"],
            "storage_class": resp.get("StorageClass", "N/A"),
            "details": f"Size: {resp['ContentLength']} bytes, StorageClass: {resp.get('StorageClass', 'N/A')}"
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "operation": "HeadObject",
            "result": "FAIL",
            "latency_ms": round(elapsed * 1000),
            "error": f"{type(e).__name__}: {str(e)[:200]}"
        }


def test_delete_object(s3, bucket, key):
    """Test DeleteObject."""
    start = time.time()
    try:
        s3.delete_object(Bucket=bucket, Key=key)
        elapsed = time.time() - start
        return {
            "operation": "DeleteObject",
            "result": "PASS",
            "latency_ms": round(elapsed * 1000),
            "key": key,
            "details": "Object deleted"
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "operation": "DeleteObject",
            "result": "FAIL",
            "latency_ms": round(elapsed * 1000),
            "error": f"{type(e).__name__}: {str(e)[:200]}"
        }


def main():
    parser = argparse.ArgumentParser(description="Verify FSx for ONTAP S3 AP connectivity")
    parser.add_argument("--ap-alias", required=True, help="S3 Access Point alias (ext-s3alias)")
    parser.add_argument("--region", required=True, help="AWS region")
    parser.add_argument("--prefix", default="", help="Object prefix to list")
    parser.add_argument("--test-key", default="", help="Existing key to test GetObject/HeadObject")
    parser.add_argument("--write-test", action="store_true", help="Include PutObject/DeleteObject tests")
    parser.add_argument("--output-yaml", help="Output results to YAML file")
    parser.add_argument("--profile", help="AWS CLI profile name")
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    s3 = session.client("s3")
    bucket = args.ap_alias

    print(f"=== FSx for ONTAP S3 AP Connectivity Verification ===")
    print(f"AP Alias: {bucket}")
    print(f"Region: {args.region}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")
    print()

    results = []

    # Test 1: ListObjectsV2
    r = test_list_objects(s3, bucket, args.prefix)
    results.append(r)
    print(f"[{r['result']}] {r['operation']} ({r['latency_ms']}ms) - {r.get('details', r.get('error', ''))}")

    # Determine test key
    test_key = args.test_key
    write_key = "__connectivity_test__.txt"

    if args.write_test:
        # Test 2: PutObject
        r = test_put_object(s3, bucket, write_key)
        results.append(r)
        print(f"[{r['result']}] {r['operation']} ({r['latency_ms']}ms) - {r.get('details', r.get('error', ''))}")
        if r["result"] == "PASS":
            test_key = write_key

    if test_key:
        # Test 3: GetObject
        r = test_get_object(s3, bucket, test_key)
        results.append(r)
        print(f"[{r['result']}] {r['operation']} ({r['latency_ms']}ms) - {r.get('details', r.get('error', ''))}")

        # Test 4: HeadObject
        r = test_head_object(s3, bucket, test_key)
        results.append(r)
        print(f"[{r['result']}] {r['operation']} ({r['latency_ms']}ms) - {r.get('details', r.get('error', ''))}")

    if args.write_test and test_key == write_key:
        # Test 5: DeleteObject (cleanup)
        r = test_delete_object(s3, bucket, write_key)
        results.append(r)
        print(f"[{r['result']}] {r['operation']} ({r['latency_ms']}ms) - {r.get('details', r.get('error', ''))}")

    # Summary
    passed = sum(1 for r in results if r["result"] == "PASS")
    failed = sum(1 for r in results if r["result"] == "FAIL")
    print(f"\n=== Summary: {passed} PASS, {failed} FAIL (total {len(results)}) ===")

    # Output YAML
    if args.output_yaml:
        output = {
            "test_id": "CONNECTIVITY-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"),
            "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "ap_alias": bucket,
            "region": args.region,
            "tests": results,
            "summary": {"passed": passed, "failed": failed, "total": len(results)}
        }
        import os
        os.makedirs(os.path.dirname(args.output_yaml) or ".", exist_ok=True)
        with open(args.output_yaml, "w") as f:
            yaml.dump(output, f, default_flow_style=False, allow_unicode=True)
        print(f"\nResults written to: {args.output_yaml}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
validate-access.py - S3 Access Point Access Validation Script

Validates connectivity and permissions for FSx for ONTAP S3 Access Point.
Tests read, write, list, and delete operations.

Usage:
    python validate-access.py --access-point-alias <alias> --region <region>
    python validate-access.py --access-point-arn <arn> --region <region>
    AWS_DEFAULT_REGION=us-east-1 python validate-access.py --access-point-alias <alias>
"""

import argparse
import boto3
import json
import os
import sys
import time
from datetime import datetime
from io import BytesIO


def create_parser():
    parser = argparse.ArgumentParser(
        description="Validate S3 Access Point connectivity to FSxN"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--access-point-alias", help="S3 Access Point alias")
    group.add_argument("--access-point-arn", help="S3 Access Point ARN")
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (defaults to AWS_DEFAULT_REGION env var; required if env var is not set)",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "--skip-write", action="store_true", help="Skip write/delete tests"
    )
    return parser


def test_list_objects(s3_client, bucket, prefix=""):
    """Test ListObjectsV2 operation."""
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket, Prefix=prefix, MaxKeys=10
        )
        count = response.get("KeyCount", 0)
        return True, f"Listed {count} objects (prefix='{prefix}')"
    except Exception as e:
        return False, str(e)


def test_get_bucket_location(s3_client, bucket):
    """Test GetBucketLocation operation."""
    try:
        response = s3_client.get_bucket_location(Bucket=bucket)
        location = response.get("LocationConstraint", "us-east-1")
        return True, f"Location: {location}"
    except Exception as e:
        return False, str(e)


def test_put_object(s3_client, bucket, key):
    """Test PutObject operation."""
    try:
        test_data = json.dumps(
            {
                "test": "fsxn-lakehouse-validation",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ).encode()
        s3_client.put_object(Bucket=bucket, Key=key, Body=test_data)
        return True, f"Written {len(test_data)} bytes to {key}"
    except Exception as e:
        return False, str(e)


def test_get_object(s3_client, bucket, key):
    """Test GetObject operation."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        return True, f"Read {len(body)} bytes from {key}"
    except Exception as e:
        return False, str(e)


def test_head_object(s3_client, bucket, key):
    """Test HeadObject operation."""
    try:
        response = s3_client.head_object(Bucket=bucket, Key=key)
        size = response.get("ContentLength", 0)
        return True, f"Object size: {size} bytes"
    except Exception as e:
        return False, str(e)


def test_delete_object(s3_client, bucket, key):
    """Test DeleteObject operation."""
    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
        return True, f"Deleted {key}"
    except Exception as e:
        return False, str(e)


def test_multipart_upload(s3_client, bucket, key):
    """Test Multipart Upload operations."""
    try:
        # Create multipart upload
        response = s3_client.create_multipart_upload(Bucket=bucket, Key=key)
        upload_id = response["UploadId"]

        # Upload a part
        part_data = b"x" * (5 * 1024 * 1024)  # 5MB minimum part size
        part_response = s3_client.upload_part(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            PartNumber=1,
            Body=part_data,
        )

        # Complete multipart upload
        s3_client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={
                "Parts": [{"PartNumber": 1, "ETag": part_response["ETag"]}]
            },
        )

        # Cleanup
        s3_client.delete_object(Bucket=bucket, Key=key)
        return True, "Multipart upload completed successfully"
    except Exception as e:
        # Abort if failed mid-way
        try:
            s3_client.abort_multipart_upload(
                Bucket=bucket, Key=key, UploadId=upload_id
            )
        except Exception:
            pass
        return False, str(e)


def main():
    parser = create_parser()
    args = parser.parse_args()

    # Resolve region: CLI flag > env var > error
    if args.region is None:
        args.region = os.environ.get("AWS_DEFAULT_REGION")
    if args.region is None:
        parser.error(
            "AWS region is required. Specify --region or set AWS_DEFAULT_REGION environment variable."
        )

    # Determine bucket identifier
    bucket = args.access_point_alias or args.access_point_arn

    print(f"\n{'='*60}")
    print(f"FSxN S3 Access Point Validation")
    print(f"{'='*60}")
    print(f"  Target:  {bucket}")
    print(f"  Region:  {args.region}")
    print(f"  Time:    {datetime.utcnow().isoformat()}Z")
    print(f"{'='*60}\n")

    # Create S3 client
    s3_client = boto3.client("s3", region_name=args.region)

    # Test results
    results = []
    test_key = "_validation_test/test_object.json"
    multipart_key = "_validation_test/multipart_test.bin"

    # Read tests
    tests = [
        ("GetBucketLocation", lambda: test_get_bucket_location(s3_client, bucket)),
        ("ListObjectsV2 (root)", lambda: test_list_objects(s3_client, bucket)),
        (
            "ListObjectsV2 (prefix)",
            lambda: test_list_objects(s3_client, bucket, "bronze/"),
        ),
    ]

    # Write tests
    if not args.skip_write:
        tests.extend(
            [
                ("PutObject", lambda: test_put_object(s3_client, bucket, test_key)),
                ("HeadObject", lambda: test_head_object(s3_client, bucket, test_key)),
                ("GetObject", lambda: test_get_object(s3_client, bucket, test_key)),
                (
                    "DeleteObject",
                    lambda: test_delete_object(s3_client, bucket, test_key),
                ),
                (
                    "MultipartUpload",
                    lambda: test_multipart_upload(s3_client, bucket, multipart_key),
                ),
            ]
        )

    # Execute tests
    passed = 0
    failed = 0

    for test_name, test_func in tests:
        start = time.time()
        success, message = test_func()
        elapsed = (time.time() - start) * 1000

        status = "✅ PASS" if success else "❌ FAIL"
        results.append((test_name, success, message, elapsed))

        if success:
            passed += 1
        else:
            failed += 1

        print(f"  {status}  {test_name} ({elapsed:.0f}ms)")
        if args.verbose or not success:
            print(f"         {message}")

    # Summary
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    print(f"{'='*60}")

    if failed > 0:
        print(f"\n⚠️  Some tests failed. Check:")
        print(f"  - IAM Role permissions")
        print(f"  - S3 AP policy")
        print(f"  - VPC endpoint configuration")
        print(f"  - Network connectivity")
        sys.exit(1)
    else:
        print(f"\n✅ All tests passed. S3 AP access is working correctly.")
        sys.exit(0)


if __name__ == "__main__":
    main()

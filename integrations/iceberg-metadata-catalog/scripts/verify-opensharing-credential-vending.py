#!/usr/bin/env python3
"""
verify-opensharing-credential-vending.py

Verifies that the OpenSharing protocol's two access modes work on
FSx for ONTAP S3 Access Points:
  1. STS Credential Vending ('dir' mode) — scoped temporary credentials
  2. Presigned URL ('url' mode) — time-limited signed URLs

Prerequisites:
  - AWS credentials with s3:GetObject, s3:ListBucket, sts:GetFederationToken
  - An FSx for ONTAP S3 Access Point with files
  - pip install boto3 requests

Usage:
  python verify-opensharing-credential-vending.py --ap-alias <S3_AP_ALIAS>

  # Example:
  python verify-opensharing-credential-vending.py \
    --ap-alias my-fsxn-ap-abc123-ext-s3alias \
    --allowed-prefix media/ \
    --denied-prefix benchmark/

Output:
  - Console: test results with pass/fail per mode and format
  - JSON: verification-results.json with full evidence

References:
  - OpenSharing spec: https://github.com/OpenSharing-IO/OpenSharing
  - FSx S3 AP API support: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html
  - Blog: Part 1 (Architecture + PoC Results)
"""

import argparse
import base64
import json
import os
import sys
import time
from typing import Any

import boto3
from botocore.config import Config

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install: pip install requests")
    sys.exit(1)


def test_sts_credential_vending(
    s3_client: Any,
    sts_client: Any,
    ap_alias: str,
    allowed_prefix: str,
    denied_prefix: str,
    region: str,
) -> dict:
    """
    Test 1: STS Credential Vending ('dir' mode)

    Simulates an OpenSharing server vending scoped temporary credentials
    to a recipient. The recipient should be able to access only the
    allowed prefix, and be denied access to other prefixes.
    """
    print("\n" + "=" * 70)
    print("TEST 1: STS Credential Vending ('dir' access mode)")
    print("=" * 70)

    results = {"mode": "sts_credential_vending", "tests": []}

    # Step 1: Generate scoped STS credentials
    session_policy = json.dumps({
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": "arn:aws:s3:*:*:accesspoint/*/object/" + allowed_prefix + "*",
            },
            {
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": "arn:aws:s3:*:*:accesspoint/*",
                "Condition": {"StringLike": {"s3:prefix": [allowed_prefix + "*"]}},
            },
        ],
    })

    print(f"\n  [1] Generating scoped STS credentials (prefix: {allowed_prefix})...")
    fed = sts_client.get_federation_token(
        Name="opensharing-recipient",
        Policy=session_policy,
        DurationSeconds=900,
    )
    creds = fed["Credentials"]
    print(f"      ✅ AccessKeyId: {creds['AccessKeyId'][:8]}...")
    print(f"      Expires: {creds['Expiration']}")
    results["sts_generated"] = True
    results["expiration"] = str(creds["Expiration"])

    # Create scoped S3 client
    scoped_s3 = boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )

    # Step 2: List objects in allowed prefix
    print(f"\n  [2] ListObjects({allowed_prefix}) with scoped credentials...")
    try:
        resp = scoped_s3.list_objects_v2(Bucket=ap_alias, Prefix=allowed_prefix, MaxKeys=10)
        objects = resp.get("Contents", [])
        print(f"      ✅ {len(objects)} objects found")
        results["tests"].append({"test": "list_allowed", "status": "PASS", "count": len(objects)})
    except Exception as e:
        print(f"      ❌ FAILED: {e}")
        results["tests"].append({"test": "list_allowed", "status": "FAIL", "error": str(e)})
        objects = []

    # Step 3: GetObject on each file in allowed prefix
    print(f"\n  [3] GetObject on files in allowed prefix...")
    for obj in objects[:5]:
        key = obj["Key"]
        ext = key.rsplit(".", 1)[-1] if "." in key else "none"
        try:
            r = scoped_s3.get_object(Bucket=ap_alias, Key=key)
            size = r["ContentLength"]
            content_type = r.get("ContentType", "unknown")
            print(f"      ✅ .{ext:<8s} {key} ({size:,} bytes)")
            results["tests"].append({
                "test": "get_allowed", "key": key, "status": "PASS",
                "size": size, "content_type": content_type,
            })
        except Exception as e:
            print(f"      ❌ .{ext:<8s} {key}: {e}")
            results["tests"].append({"test": "get_allowed", "key": key, "status": "FAIL", "error": str(e)})

    # Step 4: Verify denied prefix is blocked
    print(f"\n  [4] GetObject on denied prefix ({denied_prefix})...")
    try:
        # Try to list denied prefix
        resp = scoped_s3.list_objects_v2(Bucket=ap_alias, Prefix=denied_prefix, MaxKeys=1)
        denied_objects = resp.get("Contents", [])
        if denied_objects:
            try:
                scoped_s3.get_object(Bucket=ap_alias, Key=denied_objects[0]["Key"])
                print(f"      ❌ SECURITY ISSUE: Access should be denied but succeeded")
                results["tests"].append({"test": "deny_check", "status": "FAIL_SECURITY"})
            except Exception:
                print(f"      ✅ Correctly DENIED (AccessDenied)")
                results["tests"].append({"test": "deny_check", "status": "PASS"})
        else:
            print(f"      ⚠️ No objects in denied prefix to test")
            results["tests"].append({"test": "deny_check", "status": "SKIP_NO_OBJECTS"})
    except Exception as e:
        if "AccessDenied" in str(e):
            print(f"      ✅ Correctly DENIED at ListObjects level")
            results["tests"].append({"test": "deny_check", "status": "PASS"})
        else:
            print(f"      ⚠️ Unexpected error: {e}")
            results["tests"].append({"test": "deny_check", "status": "UNEXPECTED", "error": str(e)})

    return results


def test_presigned_url(
    s3_client: Any,
    ap_alias: str,
    region: str,
) -> dict:
    """
    Test 2: Presigned URL ('url' access mode)

    Generates SigV4 presigned URLs and verifies they work for GetObject
    on FSx for ONTAP S3 Access Points.

    IMPORTANT: Regional endpoint is required. Global endpoint causes 301.
    """
    print("\n" + "=" * 70)
    print("TEST 2: Presigned URL ('url' access mode)")
    print("=" * 70)
    print("  Note: AWS docs list Presign as 'Not supported' for FSx S3 AP.")
    print("  This test verifies empirical behavior.")

    results = {"mode": "presigned_url", "tests": []}

    # List files to test
    resp = s3_client.list_objects_v2(Bucket=ap_alias, MaxKeys=50)
    all_objects = resp.get("Contents", [])

    # Select diverse file types
    test_files = {}
    for obj in all_objects:
        ext = obj["Key"].rsplit(".", 1)[-1] if "." in obj["Key"] else "none"
        if ext not in test_files and ext in ("png", "txt", "csv", "parquet", "json"):
            test_files[ext] = obj["Key"]
        if len(test_files) >= 5:
            break

    print(f"\n  Testing {len(test_files)} file formats with presigned URLs...")
    print(f"  Endpoint: s3.{region}.amazonaws.com (regional, SigV4)")
    print()

    # Create client with regional endpoint for correct signing
    config = Config(
        s3={"addressing_style": "virtual"},
        signature_version="s3v4",
        region_name=region,
    )
    regional_s3 = boto3.client("s3", region_name=region, config=config)

    for ext, key in test_files.items():
        url = regional_s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": ap_alias, "Key": key},
            ExpiresIn=300,
        )

        t0 = time.time()
        resp = requests.get(url, timeout=30)
        elapsed = time.time() - t0

        if resp.status_code == 200:
            size = len(resp.content)
            print(f"      ✅ .{ext:<8s} {key} ({size:,} bytes) [{elapsed:.2f}s]")
            results["tests"].append({
                "test": "presign_get", "key": key, "format": ext,
                "status": "PASS", "http_status": 200, "size": size,
                "latency_sec": round(elapsed, 3),
            })
        else:
            print(f"      ❌ .{ext:<8s} HTTP {resp.status_code} ({resp.text[:80]})")
            results["tests"].append({
                "test": "presign_get", "key": key, "format": ext,
                "status": "FAIL", "http_status": resp.status_code,
            })

    # Also test with GLOBAL endpoint to document the 301 behavior
    print(f"\n  Testing with GLOBAL endpoint (expected: 301 redirect)...")
    global_s3 = boto3.client("s3", region_name=region)
    first_key = list(test_files.values())[0] if test_files else None
    if first_key:
        url_global = global_s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": ap_alias, "Key": first_key},
            ExpiresIn=300,
        )
        resp_global = requests.get(url_global, timeout=30, allow_redirects=False)
        print(f"      Global endpoint: HTTP {resp_global.status_code} (expected 301)")
        results["global_endpoint_behavior"] = resp_global.status_code

    results["requirement"] = "Regional endpoint (s3.REGION.amazonaws.com) + SigV4 required"
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Verify OpenSharing credential vending modes on FSx for ONTAP S3 AP"
    )
    parser.add_argument("--ap-alias", required=True, help="S3 Access Point alias (ending in -ext-s3alias)")
    parser.add_argument("--region", default="ap-northeast-1", help="AWS region")
    parser.add_argument("--allowed-prefix", default="media/", help="Prefix to allow in STS scoping test")
    parser.add_argument("--denied-prefix", default="benchmark/", help="Prefix to deny in STS scoping test")
    parser.add_argument("--output", default="verification-results.json", help="Output JSON file")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║  OpenSharing Credential Vending Verification for FSx S3 AP          ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"  AP Alias: {args.ap_alias}")
    print(f"  Region:   {args.region}")
    print(f"  Allowed:  {args.allowed_prefix}")
    print(f"  Denied:   {args.denied_prefix}")

    # Create clients
    s3 = boto3.client("s3", region_name=args.region)
    sts = boto3.client("sts", region_name=args.region)

    # Run tests
    sts_results = test_sts_credential_vending(
        s3, sts, args.ap_alias, args.allowed_prefix, args.denied_prefix, args.region
    )
    presign_results = test_presigned_url(s3, args.ap_alias, args.region)

    # Summary
    print("\n" + "═" * 70)
    print("SUMMARY")
    print("═" * 70)

    sts_pass = sum(1 for t in sts_results["tests"] if t["status"] == "PASS")
    sts_total = len(sts_results["tests"])
    presign_pass = sum(1 for t in presign_results["tests"] if t["status"] == "PASS")
    presign_total = len(presign_results["tests"])

    print(f"  STS Credential Vending ('dir' mode):  {sts_pass}/{sts_total} passed")
    print(f"  Presigned URL ('url' mode):           {presign_pass}/{presign_total} passed")
    print()
    print("  Recommendations:")
    print("    PRIMARY: STS credential vending — officially supported, prefix-scoped")
    print("    FALLBACK: Presigned URL — works empirically (regional endpoint + SigV4)")
    print("              but AWS docs list as 'Not supported'. Do not rely on for production.")

    # Save results
    output = {
        "verification_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ap_alias": args.ap_alias,
        "region": args.region,
        "sts_credential_vending": sts_results,
        "presigned_url": presign_results,
        "conclusion": {
            "sts_mode": "VERIFIED" if sts_pass == sts_total else "PARTIAL",
            "presign_mode": "VERIFIED" if presign_pass == presign_total else "PARTIAL",
            "recommendation": "Use STS credential vending as primary mode",
        },
    }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  Results saved to: {args.output}")


if __name__ == "__main__":
    main()

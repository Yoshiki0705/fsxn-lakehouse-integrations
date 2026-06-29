#!/usr/bin/env python3
"""
OpenSharing Volumes Server — Deployment Verification Script

Validates the full E2E flow against a deployed Lambda Function URL:
  1. Health check
  2. Authentication enforcement (401/403)
  3. Volume listing
  4. Credential vending
  5. Data access with vended credentials
  6. Prefix isolation (security boundary)
  7. Idempotent credential issuance

Usage:
  python3 scripts/verify-deployment.py --url https://xxx.lambda-url.region.on.aws/

  # With custom AP alias (if different from config):
  python3 scripts/verify-deployment.py --url https://xxx.lambda-url.region.on.aws/ \
    --ap-alias my-ap-abc123-ext-s3alias

Prerequisites:
  pip install requests boto3
"""

import argparse
import json
import sys
import time

import boto3
import requests


def run_test(name: str, func) -> bool:
    """Run a test and print result."""
    try:
        func()
        print(f"  ✅ {name}")
        return True
    except AssertionError as e:
        print(f"  ❌ {name}: {e}")
        return False
    except Exception as e:
        print(f"  ❌ {name}: {type(e).__name__}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Verify OpenSharing Volumes deployment")
    parser.add_argument("--url", required=True, help="Lambda Function URL")
    parser.add_argument("--ap-alias", default=None, help="S3 AP alias (auto-detected from volume listing if omitted)")
    parser.add_argument("--token", default="test-quality-team-token", help="Bearer token")
    parser.add_argument("--region", default="ap-northeast-1")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    headers = {"Authorization": f"Bearer {args.token}"}
    results = []

    print("=" * 70)
    print("  OpenSharing Volumes Server — Deployment Verification")
    print(f"  URL:    {base_url}")
    print(f"  Region: {args.region}")
    print("=" * 70)
    print()

    # --- Test 1: Health ---
    print("▶ Test 1: Health check")

    def t1():
        r = requests.get(f"{base_url}/health", timeout=15)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        d = r.json()
        assert d["status"] == "healthy", f"status={d['status']}"
        assert d["protocol"] == "OpenSharing Volumes"

    results.append(run_test("GET /health → 200, status=healthy", t1))
    print()

    # --- Test 2: Auth ---
    print("▶ Test 2: Authentication & authorization")

    def t2a():
        r = requests.get(f"{base_url}/api/v1/shares", timeout=10)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def t2b():
        r = requests.get(f"{base_url}/api/v1/shares/factory/all-volumes",
                         headers={"Authorization": "Bearer invalid-token"}, timeout=10)
        assert r.status_code == 401, f"Expected 401, got {r.status_code}"

    def t2c():
        r = requests.get(f"{base_url}/api/v1/shares/factory/all-volumes",
                         headers={"Authorization": "Bearer test-unauthorized-token"}, timeout=10)
        assert r.status_code == 403, f"Expected 403, got {r.status_code}"

    results.append(run_test("No token → 401", t2a))
    results.append(run_test("Invalid token → 401", t2b))
    results.append(run_test("Unauthorized token → 403", t2c))
    print()

    # --- Test 3: Volume listing ---
    print("▶ Test 3: Volume listing")

    def t3():
        r = requests.get(f"{base_url}/api/v1/shares/factory/all-volumes", headers=headers, timeout=10)
        assert r.status_code == 200, f"HTTP {r.status_code}"
        items = r.json()["items"]
        assert len(items) >= 2, f"Expected ≥2 volumes, got {len(items)}"
        names = [v["name"] for v in items]
        print(f"       Volumes: {names}")

    results.append(run_test("List volumes → ≥2 items", t3))
    print()

    # --- Test 4: Credential vending ---
    print("▶ Test 4: Credential vending")

    def t4():
        t0 = time.time()
        r = requests.post(
            f"{base_url}/api/v1/shares/factory/schemas/quality/volumes/sensor-data/temporary-volume-credentials",
            headers=headers, timeout=15)
        elapsed = (time.time() - t0) * 1000
        assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
        d = r.json()
        assert "awsTempCredentials" in d, "Missing awsTempCredentials"
        assert "expirationTime" in d, "Missing expirationTime"
        creds = d["awsTempCredentials"]
        assert "accessKeyId" in creds
        assert "secretAccessKey" in creds
        assert "sessionToken" in creds
        print(f"       Issued in {elapsed:.0f}ms, expires at {d['expirationTime']}")

    results.append(run_test("POST temporary-volume-credentials → 200 + valid creds", t4))
    print()

    # --- Test 5: Data access with vended credentials ---
    print("▶ Test 5: Data access via vended credentials")

    # Get credentials
    r = requests.post(
        f"{base_url}/api/v1/shares/factory/schemas/quality/volumes/sensor-data/temporary-volume-credentials",
        headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"  ❌ Cannot proceed — credential vending failed: {r.status_code}")
        results.append(False)
    else:
        creds = r.json()["awsTempCredentials"]
        # Detect AP alias from volume listing
        ap_alias = args.ap_alias
        if not ap_alias:
            vr = requests.get(f"{base_url}/api/v1/shares/factory/schemas/quality/volumes/sensor-data",
                              headers=headers, timeout=10)
            loc = vr.json()["storageLocation"]
            ap_alias = loc.split("//")[1].split("/")[0]

        s3 = boto3.client("s3", region_name=args.region,
                          aws_access_key_id=creds["accessKeyId"],
                          aws_secret_access_key=creds["secretAccessKey"],
                          aws_session_token=creds["sessionToken"])

        def t5a():
            result = s3.list_objects_v2(Bucket=ap_alias, Prefix="sensor-data/", MaxKeys=5)
            assert "Contents" in result, "No objects found"
            print(f"       Found {len(result['Contents'])} objects")

        def t5b():
            key = "sensor-data/sensor_data.parquet"
            obj = s3.get_object(Bucket=ap_alias, Key=key, Range="bytes=0-3")
            assert obj["ContentLength"] == 4
            # Verify Parquet magic bytes: PAR1
            body = obj["Body"].read()
            assert body == b"PAR1", f"Not Parquet: {body}"
            print(f"       Read {key}: Parquet magic bytes confirmed")

        results.append(run_test("ListObjects on allowed prefix", t5a))
        results.append(run_test("GetObject Parquet file (magic bytes)", t5b))
    print()

    # --- Test 6: Prefix isolation ---
    print("▶ Test 6: Prefix isolation (security boundary)")

    def t6():
        # sensor-data credentials should NOT access media/
        try:
            s3.list_objects_v2(Bucket=ap_alias, Prefix="media/", MaxKeys=1)
            raise AssertionError("Expected AccessDenied, got success")
        except s3.exceptions.ClientError as e:
            assert "AccessDenied" in str(e), f"Expected AccessDenied, got: {e}"

    def t6b():
        # Get inspection-images credentials
        r2 = requests.post(
            f"{base_url}/api/v1/shares/factory/schemas/quality/volumes/inspection-images/temporary-volume-credentials",
            headers=headers, timeout=15)
        assert r2.status_code == 200
        creds2 = r2.json()["awsTempCredentials"]
        s3b = boto3.client("s3", region_name=args.region,
                           aws_access_key_id=creds2["accessKeyId"],
                           aws_secret_access_key=creds2["secretAccessKey"],
                           aws_session_token=creds2["sessionToken"])
        # media/ should work
        result = s3b.list_objects_v2(Bucket=ap_alias, Prefix="media/", MaxKeys=3)
        assert "Contents" in result, "media/ not accessible with its own credentials"
        # sensor-data/ should fail
        try:
            s3b.list_objects_v2(Bucket=ap_alias, Prefix="sensor-data/", MaxKeys=1)
            raise AssertionError("Expected AccessDenied")
        except s3b.exceptions.ClientError as e:
            assert "AccessDenied" in str(e)

    results.append(run_test("sensor-data creds → media/ denied", t6))
    results.append(run_test("inspection-images creds → media/ allowed, sensor-data/ denied", t6b))
    print()

    # --- Test 7: Idempotent issuance ---
    print("▶ Test 7: Idempotent credential issuance")

    def t7():
        r1 = requests.post(
            f"{base_url}/api/v1/shares/factory/schemas/quality/volumes/sensor-data/temporary-volume-credentials",
            headers=headers, timeout=15)
        r2 = requests.post(
            f"{base_url}/api/v1/shares/factory/schemas/quality/volumes/sensor-data/temporary-volume-credentials",
            headers=headers, timeout=15)
        assert r1.status_code == 200 and r2.status_code == 200
        k1 = r1.json()["awsTempCredentials"]["accessKeyId"]
        k2 = r2.json()["awsTempCredentials"]["accessKeyId"]
        # Each call should produce fresh credentials (different key IDs)
        assert k1 != k2, f"Same keyId returned — not fresh credentials"
        print(f"       Call 1: {k1[:12]}... | Call 2: {k2[:12]}...")

    results.append(run_test("Two consecutive calls → different credentials", t7))
    print()

    # --- Summary ---
    passed = sum(1 for r in results if r)
    total = len(results)
    print("=" * 70)
    if passed == total:
        print(f"  ✅ ALL {total} TESTS PASSED")
        print(f"  OpenSharing Volumes Server deployment verified on AWS Lambda")
    else:
        print(f"  ⚠️  {passed}/{total} tests passed, {total - passed} failed")
    print("=" * 70)

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()

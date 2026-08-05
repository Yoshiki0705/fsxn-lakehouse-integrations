#!/usr/bin/env python3
"""
validate-access.py - S3 Access Point Connectivity Validation Script

Validates connectivity, network origin, IAM permissions, and AP policy
for FSx for ONTAP S3 Access Point integration with Snowflake.

Key checks:
  - S3 Access Point exists and has internet network origin (not VPC-scoped)
  - ListObjects operation works (IAM permissions)
  - GetObject on known file (if sample data uploaded)
  - PutObject + DeleteObject (write permissions)
  - AP policy allows the expected IAM role

Usage:
    python validate-access.py --access-point-alias <alias> --region <region>
    python validate-access.py --access-point-arn <arn> --region <region>
    python validate-access.py --access-point-alias <alias> --region <region> --role-arn <arn>

Requirements: REQ-1 (Storage Integration), REQ-2 (External Table access)
"""

import argparse
import boto3
import json
import os
import sys
import time
from datetime import datetime, timezone


# ─── ANSI Colors ────────────────────────────────────────────────────────────

class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    @classmethod
    def disable(cls):
        cls.GREEN = ""
        cls.RED = ""
        cls.YELLOW = ""
        cls.CYAN = ""
        cls.BOLD = ""
        cls.RESET = ""


def color_pass(text):
    return f"{Colors.GREEN}✅ PASS{Colors.RESET}  {text}"


def color_fail(text):
    return f"{Colors.RED}❌ FAIL{Colors.RESET}  {text}"


def color_warn(text):
    return f"{Colors.YELLOW}⚠️  WARN{Colors.RESET}  {text}"


def color_skip(text):
    return f"{Colors.YELLOW}⏭️  SKIP{Colors.RESET}  {text}"


# ─── CLI Parser ─────────────────────────────────────────────────────────────

def create_parser():
    parser = argparse.ArgumentParser(
        description="Validate S3 Access Point connectivity and permissions for FSx for ONTAP + Snowflake"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--access-point-alias", help="S3 Access Point alias")
    group.add_argument("--access-point-arn", help="S3 Access Point ARN")
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (defaults to AWS_DEFAULT_REGION env var)",
    )
    parser.add_argument(
        "--role-arn",
        default=None,
        help="Expected IAM Role ARN to validate in AP policy (e.g., Snowflake role)",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Verbose output with details"
    )
    parser.add_argument(
        "--skip-write", action="store_true", help="Skip write/delete tests"
    )
    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for JSON results (default: shared/scripts/results/)",
    )
    return parser


# ─── Access Point Metadata Checks ───────────────────────────────────────────

def get_access_point_info(s3control_client, account_id, ap_name, region):
    """Retrieve Access Point configuration including network origin."""
    try:
        response = s3control_client.get_access_point(
            AccountId=account_id,
            Name=ap_name,
        )
        return response
    except Exception as e:
        return None


def resolve_access_point_name(alias_or_arn, region, sts_client, s3control_client):
    """Resolve AP alias/ARN to AP name and account ID."""
    account_id = sts_client.get_caller_identity()["Account"]

    if alias_or_arn.startswith("arn:"):
        # ARN format: arn:aws:s3:region:account-id:accesspoint/name
        parts = alias_or_arn.split("/")
        ap_name = parts[-1] if len(parts) > 1 else None
        arn_parts = alias_or_arn.split(":")
        account_id = arn_parts[4] if len(arn_parts) > 4 else account_id
    else:
        # Alias format: name-account-s3alias or just the AP name
        # Try to extract AP name from alias (alias = name-accountid-s3alias)
        ap_name = alias_or_arn
        # If it ends with -s3alias, strip the suffix to get the real name
        if alias_or_arn.endswith("-s3alias"):
            # Format: <ap-name>-<12-char-hash>-s3alias
            # We need to list APs to find the matching one
            try:
                response = s3control_client.list_access_points(AccountId=account_id)
                for ap in response.get("AccessPointList", []):
                    if ap.get("Alias", "") == alias_or_arn:
                        ap_name = ap["Name"]
                        break
            except Exception:
                pass

    return ap_name, account_id


def test_network_origin(s3control_client, account_id, ap_name):
    """Verify S3 Access Point has internet network origin (not VPC-scoped).

    Snowflake is a SaaS platform that accesses S3 via the internet.
    A VPC-scoped AP would block Snowflake access entirely.
    """
    try:
        ap_info = s3control_client.get_access_point(
            AccountId=account_id,
            Name=ap_name,
        )
        network_origin = ap_info.get("NetworkOrigin", "Unknown")
        if network_origin == "Internet":
            return True, f"Network origin: Internet (Snowflake-compatible)"
        elif network_origin == "VPC":
            vpc_id = ap_info.get("VpcConfiguration", {}).get("VpcId", "unknown")
            return False, f"Network origin: VPC ({vpc_id}) — Snowflake CANNOT access VPC-scoped APs"
        else:
            return False, f"Network origin: {network_origin} (unexpected)"
    except s3control_client.exceptions.NoSuchAccessPoint:
        return False, "Access Point not found"
    except Exception as e:
        return False, f"Error checking network origin: {e}"


def test_ap_policy(s3control_client, account_id, ap_name, expected_role_arn=None):
    """Verify the AP policy allows the expected IAM role."""
    try:
        response = s3control_client.get_access_point_policy(
            AccountId=account_id,
            Name=ap_name,
        )
        policy_str = response.get("Policy", "")
        policy = json.loads(policy_str) if policy_str else {}

        if not policy:
            return True, "No AP policy set (access governed by IAM only)"

        if expected_role_arn:
            # Check if the role ARN appears in the policy
            policy_text = json.dumps(policy)
            if expected_role_arn in policy_text:
                return True, f"AP policy includes expected role: {expected_role_arn}"
            else:
                return False, f"AP policy does NOT include role: {expected_role_arn}"
        else:
            # Just confirm policy exists and is parseable
            stmt_count = len(policy.get("Statement", []))
            return True, f"AP policy exists with {stmt_count} statement(s)"

    except s3control_client.exceptions.NoSuchAccessPointPolicy:
        if expected_role_arn:
            return True, "No AP policy set — access governed by IAM role policy only (acceptable)"
        return True, "No AP policy set (access governed by IAM only)"
    except Exception as e:
        return False, f"Error checking AP policy: {e}"


# ─── S3 Data Operations ─────────────────────────────────────────────────────

def test_list_objects(s3_client, bucket, prefix=""):
    """Test ListObjectsV2 operation."""
    try:
        response = s3_client.list_objects_v2(
            Bucket=bucket, Prefix=prefix, MaxKeys=10
        )
        count = response.get("KeyCount", 0)
        contents = response.get("Contents", [])
        sample_keys = [obj["Key"] for obj in contents[:3]]
        detail = f"Listed {count} objects (prefix='{prefix}')"
        if sample_keys:
            detail += f" — e.g., {sample_keys[0]}"
        return True, detail
    except Exception as e:
        return False, str(e)


def test_get_object(s3_client, bucket, prefix=""):
    """Test GetObject on a known file (first file found in listing)."""
    try:
        # Find a file to read
        response = s3_client.list_objects_v2(
            Bucket=bucket, Prefix=prefix, MaxKeys=5
        )
        contents = response.get("Contents", [])
        if not contents:
            return None, f"No objects found with prefix='{prefix}' — skipping GetObject"

        key = contents[0]["Key"]
        get_response = s3_client.get_object(Bucket=bucket, Key=key)
        body = get_response["Body"].read(1024)  # Read first 1KB only
        content_length = get_response.get("ContentLength", 0)
        return True, f"Read {key} ({content_length} bytes)"
    except Exception as e:
        return False, str(e)


def test_put_object(s3_client, bucket):
    """Test PutObject with a small test file."""
    test_key = "_validation_test/snowflake_access_test.json"
    try:
        test_data = json.dumps(
            {
                "test": "fsxn-snowflake-validation",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "purpose": "Verify write access for Snowflake integration",
            }
        ).encode()
        s3_client.put_object(Bucket=bucket, Key=test_key, Body=test_data)
        return True, f"Written {len(test_data)} bytes to {test_key}"
    except Exception as e:
        return False, str(e)


def test_delete_object(s3_client, bucket):
    """Test DeleteObject (cleanup the test file)."""
    test_key = "_validation_test/snowflake_access_test.json"
    try:
        s3_client.delete_object(Bucket=bucket, Key=test_key)
        return True, f"Deleted {test_key}"
    except Exception as e:
        return False, str(e)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = create_parser()
    args = parser.parse_args()

    # Disable colors if requested or not a TTY
    if args.no_color or not sys.stdout.isatty():
        Colors.disable()

    # Resolve region
    if args.region is None:
        args.region = os.environ.get("AWS_DEFAULT_REGION")
    if args.region is None:
        parser.error(
            "AWS region is required. Specify --region or set AWS_DEFAULT_REGION."
        )

    # Determine bucket identifier for S3 operations
    bucket = args.access_point_alias or args.access_point_arn

    # Header
    print(f"\n{Colors.BOLD}{'='*64}{Colors.RESET}")
    print(f"{Colors.BOLD}  FSx for ONTAP S3 Access Point Validation (Snowflake Integration){Colors.RESET}")
    print(f"{Colors.BOLD}{'='*64}{Colors.RESET}")
    print(f"  {Colors.CYAN}Target:{Colors.RESET}  {bucket}")
    print(f"  {Colors.CYAN}Region:{Colors.RESET}  {args.region}")
    print(f"  {Colors.CYAN}Time:{Colors.RESET}    {datetime.now(timezone.utc).isoformat()}Z")
    if args.role_arn:
        print(f"  {Colors.CYAN}Role:{Colors.RESET}    {args.role_arn}")
    print(f"{Colors.BOLD}{'='*64}{Colors.RESET}\n")

    # Create AWS clients
    session = boto3.Session(region_name=args.region)
    s3_client = session.client("s3")
    s3control_client = session.client("s3control")
    sts_client = session.client("sts")

    # Resolve AP name and account
    ap_name, account_id = resolve_access_point_name(
        bucket, args.region, sts_client, s3control_client
    )

    # ─── Test Execution ──────────────────────────────────────────────────

    results = []
    all_tests = []

    def run_test(name, test_func, category="general"):
        """Execute a test and record results."""
        start = time.time()
        success, message = test_func()
        elapsed_ms = (time.time() - start) * 1000

        # Handle skip (None = skipped)
        if success is None:
            print(f"  {color_skip(name)} ({elapsed_ms:.0f}ms)")
            if args.verbose:
                print(f"         {message}")
            result = {
                "name": name,
                "status": "skipped",
                "message": message,
                "elapsed_ms": round(elapsed_ms, 1),
                "category": category,
            }
        elif success:
            print(f"  {color_pass(name)} ({elapsed_ms:.0f}ms)")
            if args.verbose:
                print(f"         {message}")
            result = {
                "name": name,
                "status": "passed",
                "message": message,
                "elapsed_ms": round(elapsed_ms, 1),
                "category": category,
            }
        else:
            print(f"  {color_fail(name)} ({elapsed_ms:.0f}ms)")
            print(f"         {message}")
            result = {
                "name": name,
                "status": "failed",
                "message": message,
                "elapsed_ms": round(elapsed_ms, 1),
                "category": category,
            }

        results.append(result)
        return success

    # Section 1: Access Point Configuration
    print(f"  {Colors.BOLD}[Access Point Configuration]{Colors.RESET}")
    run_test(
        "Network Origin (internet)",
        lambda: test_network_origin(s3control_client, account_id, ap_name),
        category="network",
    )
    run_test(
        "AP Policy Validation",
        lambda: test_ap_policy(s3control_client, account_id, ap_name, args.role_arn),
        category="policy",
    )

    # Section 2: Read Operations
    print(f"\n  {Colors.BOLD}[Read Operations]{Colors.RESET}")
    run_test(
        "ListObjects (root)",
        lambda: test_list_objects(s3_client, bucket),
        category="read",
    )
    run_test(
        "ListObjects (bronze/)",
        lambda: test_list_objects(s3_client, bucket, "bronze/"),
        category="read",
    )
    run_test(
        "GetObject (sample file)",
        lambda: test_get_object(s3_client, bucket, "bronze/"),
        category="read",
    )

    # Section 3: Write Operations
    if not args.skip_write:
        print(f"\n  {Colors.BOLD}[Write Operations]{Colors.RESET}")
        run_test(
            "PutObject (test file)",
            lambda: test_put_object(s3_client, bucket),
            category="write",
        )
        run_test(
            "DeleteObject (cleanup)",
            lambda: test_delete_object(s3_client, bucket),
            category="write",
        )
    else:
        print(f"\n  {color_skip('Write Operations (--skip-write)')}")

    # ─── Summary ─────────────────────────────────────────────────────────

    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    total = len(results)

    print(f"\n{Colors.BOLD}{'='*64}{Colors.RESET}")
    print(f"  Results: {Colors.GREEN}{passed} passed{Colors.RESET}, ", end="")
    print(f"{Colors.RED}{failed} failed{Colors.RESET}, ", end="")
    print(f"{Colors.YELLOW}{skipped} skipped{Colors.RESET}, {total} total")
    print(f"{Colors.BOLD}{'='*64}{Colors.RESET}")

    # ─── JSON Output ─────────────────────────────────────────────────────

    # Determine output directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = os.path.join(script_dir, "results")

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "access_validation.json")

    report = {
        "validation_type": "s3_access_point",
        "target": bucket,
        "region": args.region,
        "account_id": account_id,
        "access_point_name": ap_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": total,
            "overall_status": "PASS" if failed == 0 else "FAIL",
        },
        "checks": results,
        "context": {
            "integration": "snowflake",
            "requirements": ["REQ-1", "REQ-2"],
            "notes": [
                "Internet network origin is REQUIRED for Snowflake (SaaS, not in customer VPC)",
                "VPC-scoped AP would block Snowflake access entirely",
                "IAM Role with External ID provides secure authentication",
            ],
        },
    }

    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n  📄 Results written to: {output_file}")

    # ─── Exit ────────────────────────────────────────────────────────────

    if failed > 0:
        print(f"\n  {Colors.RED}⚠️  Some checks failed. Troubleshooting:{Colors.RESET}")
        print(f"     - Verify S3 AP has internet network origin (not VPC)")
        print(f"     - Check IAM Role permissions (s3:GetObject, s3:PutObject, s3:ListBucket)")
        print(f"     - Verify AP policy allows the Snowflake IAM role")
        print(f"     - Confirm the AP alias/ARN is correct")
        print()
        sys.exit(1)
    else:
        print(f"\n  {Colors.GREEN}✅ All checks passed. S3 AP is ready for Snowflake integration.{Colors.RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()

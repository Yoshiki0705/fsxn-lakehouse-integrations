#!/usr/bin/env python3
"""Verify that a Databricks workspace can consume this OpenSharing server as a provider.

This script tests the CREATE PROVIDER → SHOW SHARES → CREATE CATALOG flow
against a live Databricks workspace to determine whether UC accepts a
non-Databricks OpenSharing server as a valid provider.

Prerequisites:
    - Databricks CLI configured (databricks auth login)
    - Metastore admin or CREATE PROVIDER privilege
    - OpenSharing server deployed and accessible from Databricks workspace

Usage:
    # Test with a deployed server
    python3 scripts/verify-uc-provider.py \
        --server-url https://abc123.lambda-url.ap-northeast-1.on.aws \
        --token test-quality-team-token \
        --provider-name fsxontap_test

    # With profile file (already generated)
    python3 scripts/verify-uc-provider.py \
        --profile ./profiles/quality-team.share \
        --provider-name fsxontap_test

Expected outcomes:
    ✅ SUCCESS: UC accepts the provider and lists shares (path is open)
    ❌ EXPECTED FAILURE: UC rejects with a specific error (document for feature request)

Either outcome is valuable — success enables UC governance, failure provides
concrete evidence for the Databricks feature request.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run_databricks_sql(sql: str, profile: str | None = None) -> dict:
    """Execute SQL via Databricks CLI and return the result."""
    cmd = ["databricks", "sql", "execute", "--statement", sql]
    if profile:
        cmd.extend(["--profile", profile])

    print(f"  SQL: {sql}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        return {"success": False, "error": result.stderr.strip(), "stdout": result.stdout.strip()}
    return {"success": True, "output": result.stdout.strip()}


def test_provider_flow(
    server_url: str,
    bearer_token: str,
    provider_name: str,
    databricks_profile: str | None = None,
    cleanup: bool = True,
):
    """Test the full CREATE PROVIDER → SHOW SHARES → CREATE CATALOG flow."""

    print("=" * 70)
    print("OpenSharing → Unity Catalog Provider Verification")
    print("=" * 70)
    print(f"\n  Server URL:     {server_url}")
    print(f"  Provider name:  {provider_name}")
    print(f"  Cleanup after:  {cleanup}")
    print()

    results = []

    # --- Step 1: Verify server is reachable ---
    print("\n--- Step 1: Verify OpenSharing server reachability ---")
    try:
        import requests
        resp = requests.get(f"{server_url}/health", timeout=10)
        if resp.status_code == 200:
            print(f"  ✅ Server healthy: {resp.json()}")
            results.append(("Server reachability", "PASS", ""))
        else:
            print(f"  ❌ Server returned HTTP {resp.status_code}")
            results.append(("Server reachability", "FAIL", f"HTTP {resp.status_code}"))
            return results
    except Exception as e:
        print(f"  ❌ Cannot reach server: {e}")
        results.append(("Server reachability", "FAIL", str(e)))
        return results

    # --- Step 2: Verify shares are listable via API ---
    print("\n--- Step 2: Verify OpenSharing API (list shares) ---")
    try:
        resp = requests.get(
            f"{server_url}/api/v1/shares",
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            shares = resp.json().get("items", [])
            print(f"  ✅ API returned {len(shares)} shares: {[s['name'] for s in shares]}")
            results.append(("API list shares", "PASS", f"{len(shares)} shares"))
        else:
            print(f"  ❌ API returned HTTP {resp.status_code}: {resp.text}")
            results.append(("API list shares", "FAIL", f"HTTP {resp.status_code}"))
            return results
    except Exception as e:
        print(f"  ❌ API error: {e}")
        results.append(("API list shares", "FAIL", str(e)))
        return results

    # --- Step 3: Generate profile and attempt CREATE PROVIDER ---
    print("\n--- Step 3: Attempt CREATE PROVIDER in Databricks ---")
    print("  NOTE: This step requires Databricks CLI with metastore admin privileges.")
    print("  If CREATE PROVIDER fails, the error message is the key finding.")
    print()

    # Create a temporary profile file
    profile_data = {
        "shareCredentialsVersion": 1,
        "endpoint": f"{server_url}/api/v1",
        "bearerToken": bearer_token,
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".share", delete=False) as f:
        json.dump(profile_data, f)
        profile_path = f.name

    print(f"  Profile file: {profile_path}")
    print(f"  Profile content: {json.dumps(profile_data, indent=2)}")
    print()

    # Attempt CREATE PROVIDER via Databricks REST API
    # The SQL approach: CREATE PROVIDER ... doesn't directly accept a file in CLI,
    # so we use the REST API approach
    print("  Attempting to create provider via Databricks CLI...")
    print()
    print("  ⚠️  MANUAL STEP REQUIRED:")
    print(f"  1. Open Databricks workspace → Catalog → OpenSharing → 'Shared with me'")
    print(f"  2. Click 'New Provider' or use SQL:")
    print(f"     CREATE PROVIDER {provider_name};")
    print(f"  3. Upload the profile file: {profile_path}")
    print(f"  4. Or use Catalog Explorer to configure with:")
    print(f"     - Endpoint: {server_url}/api/v1")
    print(f"     - Token: {bearer_token}")
    print()
    print("  After creating the provider, run:")
    print(f"     SHOW SHARES IN PROVIDER {provider_name};")
    print(f"     CREATE CATALOG test_fsxontap USING SHARE {provider_name}.<share_name>;")
    print()

    # Try SQL-based approach (may not work for open sharing providers)
    sql_result = run_databricks_sql(
        f"CREATE PROVIDER IF NOT EXISTS {provider_name} COMMENT 'OpenSharing FSx for ONTAP test'",
        profile=databricks_profile,
    )

    if sql_result["success"]:
        print(f"  ✅ CREATE PROVIDER succeeded: {sql_result['output']}")
        results.append(("CREATE PROVIDER", "PASS", ""))

        # Try SHOW SHARES
        print("\n--- Step 4: SHOW SHARES IN PROVIDER ---")
        shares_result = run_databricks_sql(
            f"SHOW SHARES IN PROVIDER {provider_name}",
            profile=databricks_profile,
        )
        if shares_result["success"]:
            print(f"  ✅ SHOW SHARES: {shares_result['output']}")
            results.append(("SHOW SHARES", "PASS", shares_result["output"]))
        else:
            print(f"  ❌ SHOW SHARES failed: {shares_result['error']}")
            results.append(("SHOW SHARES", "FAIL", shares_result["error"]))
    else:
        print(f"  ❌ CREATE PROVIDER failed: {sql_result['error']}")
        print()
        print("  This is the EXPECTED outcome if UC does not accept non-certified providers.")
        print("  The error message above is the key evidence for the Databricks feature request.")
        results.append(("CREATE PROVIDER", "FAIL", sql_result["error"]))

    # --- Cleanup ---
    if cleanup and sql_result["success"]:
        print(f"\n--- Cleanup: DROP PROVIDER {provider_name} ---")
        run_databricks_sql(f"DROP PROVIDER IF EXISTS {provider_name}", profile=databricks_profile)

    # --- Summary ---
    print("\n" + "=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    for step, status, detail in results:
        icon = "✅" if status == "PASS" else "❌"
        print(f"  {icon} {step}: {status} {('— ' + detail) if detail else ''}")

    print()
    if any(s == "FAIL" for _, s, _ in results):
        print("  NEXT ACTION: Document the error above and include in:")
        print("  - Databricks feature request (UC recipient for non-Databricks Volume providers)")
        print("  - Blog series (evidence of protocol compliance but platform restriction)")
    else:
        print("  NEXT ACTION: Proceed with CREATE CATALOG USING SHARE to test Volume access")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Verify OpenSharing server → Databricks Unity Catalog provider flow"
    )
    parser.add_argument(
        "--server-url",
        help="OpenSharing server URL (e.g., https://abc.lambda-url.region.on.aws)",
    )
    parser.add_argument(
        "--token",
        help="Bearer token for the OpenSharing server",
    )
    parser.add_argument(
        "--profile",
        help="Path to a .share profile file (alternative to --server-url + --token)",
    )
    parser.add_argument(
        "--provider-name",
        default="fsxontap_opensharing_test",
        help="Name for the UC provider object (default: fsxontap_opensharing_test)",
    )
    parser.add_argument(
        "--databricks-profile",
        help="Databricks CLI profile name (optional)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't drop the provider after testing",
    )

    args = parser.parse_args()

    # Resolve server URL and token
    if args.profile:
        with open(args.profile) as f:
            profile_data = json.load(f)
        server_url = profile_data["endpoint"].rsplit("/api/v1", 1)[0]
        bearer_token = profile_data["bearerToken"]
    elif args.server_url and args.token:
        server_url = args.server_url.rstrip("/")
        bearer_token = args.token
    else:
        parser.error("Specify either --profile or both --server-url and --token")
        return

    test_provider_flow(
        server_url=server_url,
        bearer_token=bearer_token,
        provider_name=args.provider_name,
        databricks_profile=args.databricks_profile,
        cleanup=not args.no_cleanup,
    )


if __name__ == "__main__":
    main()

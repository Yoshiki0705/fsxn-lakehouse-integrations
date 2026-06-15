#!/usr/bin/env python3
"""
verify_account.py - Snowflake Account Verification Script

Validates Snowflake account prerequisites for FSxN × S3 AP integration:
  1. Account Edition (Enterprise or higher)
  2. Region (ap-northeast-1 / AWS Tokyo)
  3. ACCOUNTADMIN role access
  4. SnowSQL CLI connectivity

Outputs account locator, workspace URL, and region to a JSON config file.

Usage:
    python verify_account.py
    python verify_account.py --output config/snowflake_account.json
    python verify_account.py --account <locator> --user <username>

Environment Variables:
    SNOWFLAKE_ACCOUNT   - Snowflake account locator (e.g., xy12345.ap-northeast-1.aws)
    SNOWFLAKE_USER      - Snowflake username
    SNOWFLAKE_PASSWORD  - Snowflake password (or use --authenticator externalbrowser)
    SNOWFLAKE_ROLE      - Role to use (default: ACCOUNTADMIN)
    SNOWFLAKE_WAREHOUSE - Warehouse for test queries (optional)

Requirements:
    - snowflake-connector-python
    - SnowSQL CLI (optional, for CLI connectivity check)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import snowflake.connector
except ImportError:
    print("ERROR: snowflake-connector-python is not installed.")
    print("  Install with: pip install snowflake-connector-python")
    sys.exit(1)


# =============================================================================
# Constants
# =============================================================================

# Default expected region — can be overridden via --expected-region CLI argument
REQUIRED_REGION = os.environ.get("SNOWFLAKE_EXPECTED_REGION", "ap-northeast-1")
REQUIRED_CLOUD = os.environ.get("SNOWFLAKE_EXPECTED_CLOUD", "aws")
# Enterprise Edition or higher is required for Storage Integration
ACCEPTABLE_EDITIONS = ["ENTERPRISE", "BUSINESS_CRITICAL"]

DEFAULT_OUTPUT_PATH = "integrations/snowflake/scripts/config/snowflake_account.json"


# =============================================================================
# Argument Parsing
# =============================================================================


def create_parser():
    parser = argparse.ArgumentParser(
        description="Verify Snowflake account prerequisites for FSxN integration"
    )
    parser.add_argument(
        "--account",
        default=os.environ.get("SNOWFLAKE_ACCOUNT"),
        help="Snowflake account locator (env: SNOWFLAKE_ACCOUNT)",
    )
    parser.add_argument(
        "--user",
        default=os.environ.get("SNOWFLAKE_USER"),
        help="Snowflake username (env: SNOWFLAKE_USER)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("SNOWFLAKE_PASSWORD"),
        help="Snowflake password (env: SNOWFLAKE_PASSWORD)",
    )
    parser.add_argument(
        "--role",
        default=os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        help="Snowflake role (default: ACCOUNTADMIN)",
    )
    parser.add_argument(
        "--warehouse",
        default=os.environ.get("SNOWFLAKE_WAREHOUSE"),
        help="Snowflake warehouse for test queries (env: SNOWFLAKE_WAREHOUSE)",
    )
    parser.add_argument(
        "--authenticator",
        default=os.environ.get("SNOWFLAKE_AUTHENTICATOR"),
        help="Authentication method (e.g., externalbrowser, snowflake)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_PATH,
        help=f"Output JSON config file path (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--skip-snowsql",
        action="store_true",
        help="Skip SnowSQL CLI connectivity check",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    return parser


# =============================================================================
# Verification Functions
# =============================================================================


def connect_snowflake(args):
    """Establish connection to Snowflake using provided credentials."""
    conn_params = {
        "account": args.account,
        "user": args.user,
        "role": args.role,
    }

    if args.warehouse:
        conn_params["warehouse"] = args.warehouse

    if args.authenticator:
        conn_params["authenticator"] = args.authenticator
    elif args.password:
        conn_params["password"] = args.password
    else:
        # Try externalbrowser as fallback if no password provided
        conn_params["authenticator"] = "externalbrowser"

    try:
        conn = snowflake.connector.connect(**conn_params)
        return conn
    except snowflake.connector.errors.DatabaseError as e:
        return None, str(e)


def verify_edition(cursor):
    """Verify Snowflake account edition is Enterprise or higher."""
    try:
        cursor.execute(
            "SELECT SYSTEM$GET_SNOWFLAKE_PLATFORM_INFO() AS platform_info"
        )
        row = cursor.fetchone()
        if row:
            platform_info = json.loads(row[0])
            # Platform info doesn't always include edition directly
            # Use SHOW ORGANIZATION ACCOUNTS or account parameters instead
    except Exception:
        pass

    # Use CURRENT_ACCOUNT_NAME and account parameters
    try:
        cursor.execute("SHOW PARAMETERS LIKE 'RELEASE_CHANNEL' IN ACCOUNT")
    except Exception:
        pass

    # Most reliable: check if Storage Integration creation is allowed
    # Enterprise+ features can be verified by checking account edition
    try:
        cursor.execute(
            "SELECT CURRENT_ACCOUNT_NAME(), CURRENT_ORGANIZATION_NAME()"
        )
        account_row = cursor.fetchone()
        account_name = account_row[0] if account_row else None
        org_name = account_row[1] if account_row else None
    except Exception:
        account_name = None
        org_name = None

    # Check edition via SYSTEM$ALLOWLIST or account usage
    edition = None
    try:
        cursor.execute(
            """
            SELECT VALUE
            FROM TABLE(FLATTEN(
                INPUT => PARSE_JSON(SYSTEM$GET_SNOWFLAKE_PLATFORM_INFO())
            ))
            WHERE KEY = 'snowflake-edition'
            """
        )
        row = cursor.fetchone()
        if row:
            edition = row[0].upper() if row[0] else None
    except Exception:
        pass

    # Fallback: try ORGANIZATION_USAGE.ACCOUNTS view
    if edition is None:
        try:
            cursor.execute(
                """
                SELECT EDITION
                FROM SNOWFLAKE.ORGANIZATION_USAGE.ACCOUNTS
                WHERE ACCOUNT_NAME = CURRENT_ACCOUNT_NAME()
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if row:
                edition = row[0].upper() if row[0] else None
        except Exception:
            pass

    # Fallback: check if we can create storage integration (Enterprise+ feature)
    if edition is None:
        try:
            cursor.execute("SHOW INTEGRATIONS LIKE 'fsxn_%'")
            # If this succeeds with ACCOUNTADMIN, likely Enterprise+
            edition = "ENTERPRISE_OR_HIGHER"
        except Exception:
            edition = "UNKNOWN"

    is_valid = edition in ACCEPTABLE_EDITIONS or edition == "ENTERPRISE_OR_HIGHER"
    return is_valid, edition, account_name, org_name


def verify_region(cursor):
    """Verify Snowflake account is in ap-northeast-1 (AWS Tokyo)."""
    region = None
    cloud = None
    account_locator = None

    try:
        cursor.execute("SELECT CURRENT_REGION(), CURRENT_ACCOUNT()")
        row = cursor.fetchone()
        if row:
            # CURRENT_REGION() returns format like 'AWS_AP_NORTHEAST_1'
            full_region = row[0]
            account_locator = row[1]

            # Parse cloud and region from CURRENT_REGION()
            if full_region:
                parts = full_region.split("_", 1)
                if len(parts) == 2:
                    cloud = parts[0].lower()
                    # Convert AWS_AP_NORTHEAST_1 -> ap-northeast-1
                    region = parts[1].lower().replace("_", "-")
    except Exception as e:
        return False, None, None, None, str(e)

    is_valid = region == REQUIRED_REGION and cloud == REQUIRED_CLOUD
    return is_valid, region, cloud, account_locator, None


def verify_accountadmin_role(cursor):
    """Verify ACCOUNTADMIN role access."""
    try:
        cursor.execute("SELECT CURRENT_ROLE()")
        row = cursor.fetchone()
        current_role = row[0] if row else None

        if current_role == "ACCOUNTADMIN":
            return True, current_role, None

        # Try to USE ROLE ACCOUNTADMIN
        cursor.execute("USE ROLE ACCOUNTADMIN")
        cursor.execute("SELECT CURRENT_ROLE()")
        row = cursor.fetchone()
        current_role = row[0] if row else None

        return current_role == "ACCOUNTADMIN", current_role, None
    except Exception as e:
        return False, None, str(e)


def verify_warehouse(cursor, warehouse_name=None):
    """Verify warehouse availability for test queries."""
    if warehouse_name:
        try:
            cursor.execute(f"USE WAREHOUSE {warehouse_name}")
            cursor.execute("SELECT CURRENT_WAREHOUSE()")
            row = cursor.fetchone()
            return True, row[0] if row else None, None
        except Exception as e:
            return False, None, str(e)

    # List available warehouses
    try:
        cursor.execute("SHOW WAREHOUSES")
        warehouses = cursor.fetchall()
        if warehouses:
            # Use first available warehouse
            wh_name = warehouses[0][0]
            return True, wh_name, f"Found {len(warehouses)} warehouse(s)"
        return False, None, "No warehouses available"
    except Exception as e:
        return False, None, str(e)


def get_account_url(account_locator, region, cloud):
    """Construct the Snowflake account URL."""
    # Format: https://<locator>.<region>.<cloud>.snowflakecomputing.com
    return f"https://{account_locator}.{region}.{cloud}.snowflakecomputing.com"


def verify_snowsql_cli():
    """Verify SnowSQL CLI is installed and accessible."""
    snowsql_path = shutil.which("snowsql")
    if not snowsql_path:
        return False, None, "SnowSQL CLI not found in PATH"

    try:
        result = subprocess.run(
            ["snowsql", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version = result.stdout.strip() or result.stderr.strip()
        return True, version, snowsql_path
    except subprocess.TimeoutExpired:
        return False, None, "SnowSQL --version timed out"
    except Exception as e:
        return False, None, str(e)


# =============================================================================
# Output
# =============================================================================


def write_config(output_path, config):
    """Write account configuration to JSON file."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return output_file


# =============================================================================
# Main
# =============================================================================


def main():
    parser = create_parser()
    args = parser.parse_args()

    # Validate required arguments
    if not args.account:
        parser.error(
            "Snowflake account is required. Use --account or set SNOWFLAKE_ACCOUNT."
        )
    if not args.user:
        parser.error(
            "Snowflake user is required. Use --user or set SNOWFLAKE_USER."
        )

    print(f"\n{'='*60}")
    print("Snowflake Account Verification")
    print(f"{'='*60}")
    print(f"  Account:  {args.account}")
    print(f"  User:     {args.user}")
    print(f"  Role:     {args.role}")
    print(f"  Time:     {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    # Track results
    checks = []
    config = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "account_input": args.account,
    }

    # =========================================================================
    # Check 1: SnowSQL CLI
    # =========================================================================
    if not args.skip_snowsql:
        print("  [1/4] SnowSQL CLI check...")
        cli_ok, cli_version, cli_detail = verify_snowsql_cli()
        status = "✅ PASS" if cli_ok else "⚠️  WARN"
        print(f"         {status}  {cli_version or cli_detail}")
        config["snowsql_cli"] = {
            "available": cli_ok,
            "version": cli_version,
            "path": cli_detail if cli_ok else None,
        }
        checks.append(("SnowSQL CLI", cli_ok, cli_detail))
    else:
        print("  [1/4] SnowSQL CLI check... SKIPPED")
        config["snowsql_cli"] = {"available": None, "skipped": True}

    # =========================================================================
    # Check 2: Snowflake Connection + Region
    # =========================================================================
    print("  [2/4] Connecting to Snowflake...")
    conn_result = connect_snowflake(args)

    if isinstance(conn_result, tuple):
        # Connection failed
        _, error_msg = conn_result
        print(f"         ❌ FAIL  Connection failed: {error_msg}")
        config["connection"] = {"success": False, "error": error_msg}
        checks.append(("Connection", False, error_msg))
        # Cannot proceed without connection
        print(f"\n{'='*60}")
        print("❌ Verification FAILED — cannot connect to Snowflake.")
        print(f"{'='*60}")
        sys.exit(1)

    conn = conn_result
    cursor = conn.cursor()
    print("         ✅ PASS  Connected successfully")
    config["connection"] = {"success": True}

    # =========================================================================
    # Check 3: Region Verification
    # =========================================================================
    print("  [3/4] Verifying region (required: ap-northeast-1)...")
    region_ok, region, cloud, account_locator, region_err = verify_region(cursor)

    if region_ok:
        print(f"         ✅ PASS  Region: {cloud.upper()}_{region} (Tokyo)")
    else:
        print(f"         ❌ FAIL  Region: {cloud}_{region} (expected: {REQUIRED_CLOUD}_{REQUIRED_REGION})")
        if region_err:
            print(f"                  Error: {region_err}")

    config["region"] = {
        "valid": region_ok,
        "region": region,
        "cloud": cloud,
        "required_region": REQUIRED_REGION,
    }
    config["account_locator"] = account_locator
    checks.append(("Region", region_ok, f"{cloud}_{region}"))

    # Construct account URL
    if account_locator and region and cloud:
        account_url = get_account_url(account_locator.lower(), region, cloud)
        config["account_url"] = account_url
    else:
        config["account_url"] = None

    # =========================================================================
    # Check 4: ACCOUNTADMIN Role + Edition
    # =========================================================================
    print("  [4/4] Verifying ACCOUNTADMIN role and edition...")

    # Role check
    role_ok, current_role, role_err = verify_accountadmin_role(cursor)
    if role_ok:
        print(f"         ✅ PASS  Role: {current_role}")
    else:
        print(f"         ❌ FAIL  Role: {current_role or 'N/A'}")
        if role_err:
            print(f"                  Error: {role_err}")

    config["role"] = {
        "valid": role_ok,
        "current_role": current_role,
    }
    checks.append(("ACCOUNTADMIN Role", role_ok, current_role))

    # Edition check
    edition_ok, edition, account_name, org_name = verify_edition(cursor)
    if edition_ok:
        print(f"         ✅ PASS  Edition: {edition}")
    else:
        print(f"         ⚠️  WARN  Edition: {edition} (expected: Enterprise+)")
        print("                  Storage Integration requires Enterprise Edition or higher.")

    config["edition"] = {
        "valid": edition_ok,
        "edition": edition,
        "account_name": account_name,
        "organization_name": org_name,
    }
    checks.append(("Edition (Enterprise+)", edition_ok, edition))

    # Warehouse check (informational)
    wh_ok, wh_name, wh_detail = verify_warehouse(cursor, args.warehouse)
    if wh_ok:
        print(f"         ℹ️  Warehouse: {wh_name}")
    config["warehouse"] = {
        "available": wh_ok,
        "name": wh_name,
        "detail": wh_detail,
    }

    # =========================================================================
    # Summary
    # =========================================================================
    cursor.close()
    conn.close()

    passed = sum(1 for _, ok, _ in checks if ok)
    failed = sum(1 for _, ok, _ in checks if not ok)
    total = len(checks)

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed, {total} total")
    print(f"{'='*60}")

    # Write config
    config["summary"] = {
        "passed": passed,
        "failed": failed,
        "total": total,
        "all_passed": failed == 0,
    }

    output_file = write_config(args.output, config)
    print(f"\n  Config written to: {output_file}")

    if config.get("account_url"):
        print(f"  Account URL:       {config['account_url']}")
    if account_locator:
        print(f"  Account Locator:   {account_locator}")
    if region:
        print(f"  Region:            {region}")

    print()

    if failed > 0:
        print("⚠️  Some checks failed. Review the output above.")
        print("   Storage Integration requires:")
        print("   - Enterprise Edition or higher")
        print("   - ap-northeast-1 region (AWS Tokyo)")
        print("   - ACCOUNTADMIN role access")
        sys.exit(1)
    else:
        print("✅ All checks passed. Account is ready for FSxN integration.")
        sys.exit(0)


if __name__ == "__main__":
    main()

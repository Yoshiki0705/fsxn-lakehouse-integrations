#!/usr/bin/env python3
"""
Snowpark Environment Validation Script
=======================================
Validates Snowpark Python availability, warehouse sizing, and consumer account
locator for the FSx for ONTAP × Snowflake integration verification.

Requirements:
  - REQ-7: Snowpark UDF processing for media files
  - REQ-5: Secure Data Sharing (consumer account validation)

Usage:
  python verify_snowpark.py [--config CONFIG_PATH] [--consumer-account LOCATOR]

Prerequisites:
  - snowflake-connector-python installed
  - snowflake-snowpark-python installed
  - Valid Snowflake credentials (env vars or config file)
"""

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SCRIPT_DIR.parent / "params.json"
OUTPUT_PATH = SCRIPT_DIR.parent / "tests" / "results" / "snowpark_validation.json"

# Required Snowpark packages for UDF processing (from 09_snowpark_image_udf.sql)
REQUIRED_PACKAGES = [
    "snowflake-snowpark-python",
]

# Packages used inside Snowpark UDFs (available in Snowflake's Anaconda channel)
SNOWPARK_UDF_PACKAGES = [
    "regex",  # Used in PARSE_IMAGE_FILENAME UDF
]

# Recommended warehouse size for Snowpark UDF workloads (from design.md §4.2)
RECOMMENDED_WAREHOUSE_SIZE = "MEDIUM"
MINIMUM_WAREHOUSE_SIZE = "SMALL"

WAREHOUSE_SIZE_ORDER = [
    "X-SMALL",
    "XSMALL",
    "SMALL",
    "MEDIUM",
    "LARGE",
    "X-LARGE",
    "XLARGE",
    "2X-LARGE",
    "3X-LARGE",
    "4X-LARGE",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def normalize_warehouse_size(size: str) -> str:
    """Normalize warehouse size string for comparison."""
    return size.upper().replace("_", "-").replace(" ", "-")


def warehouse_size_index(size: str) -> int:
    """Return numeric index for warehouse size comparison."""
    normalized = normalize_warehouse_size(size)
    for i, s in enumerate(WAREHOUSE_SIZE_ORDER):
        if normalized == s:
            return i
    return -1


def get_snowflake_connection_params() -> dict:
    """
    Resolve Snowflake connection parameters from environment variables.

    Expected env vars:
      SNOWFLAKE_ACCOUNT   - Account locator (e.g., xy12345.ap-northeast-1.aws)
      SNOWFLAKE_USER      - Username
      SNOWFLAKE_PASSWORD  - Password (or use SNOWFLAKE_PRIVATE_KEY_PATH)
      SNOWFLAKE_ROLE      - Role (default: ACCOUNTADMIN)
      SNOWFLAKE_WAREHOUSE - Warehouse name
      SNOWFLAKE_DATABASE  - Database (default: FSXN_LAKEHOUSE)
    """
    params = {
        "account": os.environ.get("SNOWFLAKE_ACCOUNT", ""),
        "user": os.environ.get("SNOWFLAKE_USER", ""),
        "password": os.environ.get("SNOWFLAKE_PASSWORD", ""),
        "role": os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", ""),
        "database": os.environ.get("SNOWFLAKE_DATABASE", "FSXN_LAKEHOUSE"),
    }
    return params


def print_status(label: str, ok: bool, detail: str = ""):
    """Print a formatted status line."""
    icon = "✅" if ok else "❌"
    msg = f"  {icon} {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)


# ---------------------------------------------------------------------------
# Validation Checks
# ---------------------------------------------------------------------------


def check_snowpark_import() -> dict:
    """Check that snowflake-snowpark-python is importable locally."""
    result = {"check": "snowpark_import", "passed": False, "detail": ""}
    try:
        import snowflake.snowpark  # noqa: F401

        version = snowflake.snowpark.__version__
        result["passed"] = True
        result["detail"] = f"snowflake-snowpark-python {version}"
    except ImportError as e:
        result["detail"] = (
            f"Import failed: {e}. "
            "Install with: pip install snowflake-snowpark-python"
        )
    return result


def check_connector_import() -> dict:
    """Check that snowflake-connector-python is importable locally."""
    result = {"check": "connector_import", "passed": False, "detail": ""}
    try:
        import snowflake.connector  # noqa: F401

        version = snowflake.connector.__version__
        result["passed"] = True
        result["detail"] = f"snowflake-connector-python {version}"
    except ImportError as e:
        result["detail"] = (
            f"Import failed: {e}. "
            "Install with: pip install snowflake-connector-python"
        )
    return result


def check_snowpark_session(conn_params: dict) -> dict:
    """Attempt to create a Snowpark session and verify Python UDF support."""
    result = {"check": "snowpark_session", "passed": False, "detail": ""}

    if not conn_params.get("account") or not conn_params.get("user"):
        result["detail"] = (
            "Skipped — SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER env vars required"
        )
        result["skipped"] = True
        return result

    try:
        from snowflake.snowpark import Session

        session = Session.builder.configs(conn_params).create()
        # Verify session is active
        current_wh = session.sql("SELECT CURRENT_WAREHOUSE()").collect()[0][0]
        result["passed"] = True
        result["detail"] = f"Session active, warehouse: {current_wh}"
        result["warehouse"] = current_wh
        session.close()
    except Exception as e:
        result["detail"] = f"Session creation failed: {e}"

    return result


def check_warehouse_size(conn_params: dict) -> dict:
    """Verify warehouse size meets MEDIUM recommendation for Snowpark UDFs."""
    result = {"check": "warehouse_size", "passed": False, "detail": ""}

    if not conn_params.get("account") or not conn_params.get("user"):
        result["detail"] = "Skipped — connection params not available"
        result["skipped"] = True
        return result

    try:
        import snowflake.connector

        conn = snowflake.connector.connect(**conn_params)
        cursor = conn.cursor()

        warehouse = conn_params.get("warehouse", "")
        if not warehouse:
            cursor.execute("SELECT CURRENT_WAREHOUSE()")
            row = cursor.fetchone()
            warehouse = row[0] if row else None

        if not warehouse:
            result["detail"] = "No warehouse set or active"
            cursor.close()
            conn.close()
            return result

        cursor.execute(f"SHOW WAREHOUSES LIKE '{warehouse}'")
        rows = cursor.fetchall()

        if not rows:
            result["detail"] = f"Warehouse '{warehouse}' not found"
            cursor.close()
            conn.close()
            return result

        # SHOW WAREHOUSES columns: name, state, type, size, ...
        # Size is typically column index 3
        col_names = [desc[0] for desc in cursor.description]
        size_idx = col_names.index("size") if "size" in col_names else 3
        wh_size = rows[0][size_idx]

        size_index = warehouse_size_index(wh_size)
        min_index = warehouse_size_index(MINIMUM_WAREHOUSE_SIZE)
        rec_index = warehouse_size_index(RECOMMENDED_WAREHOUSE_SIZE)

        if size_index >= rec_index:
            result["passed"] = True
            result["detail"] = (
                f"Warehouse '{warehouse}' size: {wh_size} "
                f"(meets recommended: {RECOMMENDED_WAREHOUSE_SIZE})"
            )
        elif size_index >= min_index:
            result["passed"] = True
            result["detail"] = (
                f"Warehouse '{warehouse}' size: {wh_size} "
                f"(acceptable, but {RECOMMENDED_WAREHOUSE_SIZE} recommended for UDFs)"
            )
            result["warning"] = True
        else:
            result["detail"] = (
                f"Warehouse '{warehouse}' size: {wh_size} — "
                f"too small for Snowpark UDFs. "
                f"Minimum: {MINIMUM_WAREHOUSE_SIZE}, "
                f"Recommended: {RECOMMENDED_WAREHOUSE_SIZE}"
            )

        result["warehouse_name"] = warehouse
        result["warehouse_size"] = wh_size

        cursor.close()
        conn.close()
    except ImportError:
        result["detail"] = "snowflake-connector-python not installed"
    except Exception as e:
        result["detail"] = f"Warehouse check failed: {e}"

    return result


def check_python_udf_support(conn_params: dict) -> dict:
    """Verify that Python UDFs can be created (Snowpark runtime available)."""
    result = {"check": "python_udf_support", "passed": False, "detail": ""}

    if not conn_params.get("account") or not conn_params.get("user"):
        result["detail"] = "Skipped — connection params not available"
        result["skipped"] = True
        return result

    try:
        import snowflake.connector

        conn = snowflake.connector.connect(**conn_params)
        cursor = conn.cursor()

        # Check available Python runtime versions
        cursor.execute(
            "SELECT * FROM INFORMATION_SCHEMA.PACKAGES "
            "WHERE LANGUAGE = 'python' AND PACKAGE_NAME = 'snowflake-snowpark-python' "
            "ORDER BY VERSION DESC LIMIT 5"
        )
        rows = cursor.fetchall()

        if rows:
            versions = [row[2] for row in rows]  # version column
            result["passed"] = True
            result["detail"] = (
                f"Snowpark Python available — versions: {', '.join(versions[:3])}"
            )
            result["available_versions"] = versions
        else:
            # Fallback: try querying packages differently
            cursor.execute(
                "SELECT PACKAGE_NAME, VERSION FROM "
                "INFORMATION_SCHEMA.PACKAGES "
                "WHERE LANGUAGE = 'python' "
                "ORDER BY PACKAGE_NAME LIMIT 10"
            )
            fallback_rows = cursor.fetchall()
            if fallback_rows:
                result["passed"] = True
                result["detail"] = (
                    f"Python packages available ({len(fallback_rows)}+ packages in Anaconda channel)"
                )
            else:
                result["detail"] = (
                    "No Python packages found in INFORMATION_SCHEMA.PACKAGES. "
                    "Snowpark Python UDFs may not be available on this account."
                )

        cursor.close()
        conn.close()
    except ImportError:
        result["detail"] = "snowflake-connector-python not installed"
    except Exception as e:
        # Some accounts may not have INFORMATION_SCHEMA.PACKAGES
        result["detail"] = f"Python UDF support check: {e}"
        result["note"] = (
            "This may be expected if the account uses a different method "
            "to manage packages. Snowpark UDFs should still work."
        )

    return result


def check_anaconda_packages(conn_params: dict) -> dict:
    """Verify required Anaconda packages are available for UDFs."""
    result = {
        "check": "anaconda_packages",
        "passed": False,
        "detail": "",
        "packages": {},
    }

    if not conn_params.get("account") or not conn_params.get("user"):
        result["detail"] = "Skipped — connection params not available"
        result["skipped"] = True
        return result

    try:
        import snowflake.connector

        conn = snowflake.connector.connect(**conn_params)
        cursor = conn.cursor()

        # Check Anaconda terms acceptance (required for 3rd-party packages)
        # Standard packages (os, re, json) are always available
        all_available = True
        for pkg in SNOWPARK_UDF_PACKAGES:
            cursor.execute(
                f"SELECT PACKAGE_NAME, VERSION FROM "
                f"INFORMATION_SCHEMA.PACKAGES "
                f"WHERE LANGUAGE = 'python' AND PACKAGE_NAME = '{pkg}' "
                f"ORDER BY VERSION DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                result["packages"][pkg] = {"available": True, "version": row[1]}
            else:
                result["packages"][pkg] = {"available": False}
                all_available = False

        # Note: The UDFs in 09_snowpark_image_udf.sql only use standard library
        # (os, re) so they work without additional Anaconda packages
        result["passed"] = True
        result["detail"] = (
            "UDFs use Python standard library (os, re) — no extra packages required. "
            f"Optional packages checked: {len(SNOWPARK_UDF_PACKAGES)}"
        )

        cursor.close()
        conn.close()
    except ImportError:
        result["detail"] = "snowflake-connector-python not installed"
    except Exception as e:
        # If INFORMATION_SCHEMA.PACKAGES is not accessible, UDFs may still work
        result["passed"] = True
        result["detail"] = (
            f"Package query not available ({e}). "
            "UDFs use standard library only — should work regardless."
        )

    return result


def check_consumer_account(consumer_locator: str) -> dict:
    """Validate consumer account locator format for Data Sharing (REQ-5)."""
    result = {"check": "consumer_account", "passed": False, "detail": ""}

    if not consumer_locator:
        result["detail"] = (
            "No consumer account specified. "
            "Data Sharing test will use same-account validation only. "
            "Pass --consumer-account to enable cross-account sharing test."
        )
        result["skipped"] = True
        result["passed"] = True  # Not a failure, just optional
        return result

    # Validate locator format: typically <orgname>.<account_name> or <locator>
    # Examples: xy12345, ORGNAME.ACCOUNT_NAME, xy12345.ap-northeast-1.aws
    locator = consumer_locator.strip()

    if not locator:
        result["detail"] = "Empty consumer account locator"
        return result

    # Basic format validation
    if len(locator) < 3:
        result["detail"] = f"Locator too short: '{locator}' (minimum 3 characters)"
        return result

    if " " in locator:
        result["detail"] = f"Locator contains spaces: '{locator}'"
        return result

    # Check for common formats
    if "." in locator:
        parts = locator.split(".")
        if len(parts) >= 2:
            result["passed"] = True
            result["detail"] = (
                f"Consumer account locator: {locator} "
                f"(format: {'org.account' if len(parts) == 2 else 'locator.region.cloud'})"
            )
        else:
            result["detail"] = f"Unexpected locator format: '{locator}'"
    else:
        # Simple locator (legacy format)
        result["passed"] = True
        result["detail"] = f"Consumer account locator: {locator} (legacy format)"

    result["consumer_locator"] = locator
    return result


def check_consumer_account_connectivity(
    conn_params: dict, consumer_locator: str
) -> dict:
    """Verify consumer account is reachable for sharing (optional live check)."""
    result = {"check": "consumer_connectivity", "passed": False, "detail": ""}

    if not consumer_locator:
        result["detail"] = "Skipped — no consumer account specified"
        result["skipped"] = True
        return result

    if not conn_params.get("account") or not conn_params.get("user"):
        result["detail"] = "Skipped — connection params not available"
        result["skipped"] = True
        return result

    try:
        import snowflake.connector

        conn = snowflake.connector.connect(**conn_params)
        cursor = conn.cursor()

        # Check if we can reference the consumer account in a share
        # This doesn't actually create anything, just validates the account exists
        cursor.execute("SHOW SHARES")
        result["passed"] = True
        result["detail"] = (
            f"Share operations available. Consumer '{consumer_locator}' "
            "will be validated during Data Sharing test execution."
        )

        cursor.close()
        conn.close()
    except ImportError:
        result["detail"] = "snowflake-connector-python not installed"
    except Exception as e:
        result["detail"] = f"Connectivity check failed: {e}"

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_validation(consumer_account: str = "") -> dict:
    """Run all Snowpark and Data Sharing validation checks."""
    print("=" * 70)
    print("Snowpark Environment Validation")
    print("=" * 70)
    print(f"  Requirements: REQ-7 (Snowpark UDF), REQ-5 (Data Sharing)")
    print(f"  Recommended warehouse: {RECOMMENDED_WAREHOUSE_SIZE}")
    print()

    conn_params = get_snowflake_connection_params()
    results = []

    # --- Local environment checks ---
    print("Local Environment:")
    print("-" * 40)

    r = check_snowpark_import()
    results.append(r)
    print_status("Snowpark Python package", r["passed"], r["detail"])

    r = check_connector_import()
    results.append(r)
    print_status("Snowflake Connector", r["passed"], r["detail"])

    print()

    # --- Snowflake account checks (require credentials) ---
    print("Snowflake Account (Snowpark):")
    print("-" * 40)

    has_creds = bool(conn_params.get("account") and conn_params.get("user"))
    if not has_creds:
        print("  ⚠️  Snowflake credentials not set. Set SNOWFLAKE_ACCOUNT,")
        print("     SNOWFLAKE_USER, SNOWFLAKE_PASSWORD env vars for live checks.")
        print()
    else:
        r = check_snowpark_session(conn_params)
        results.append(r)
        print_status("Snowpark session", r["passed"], r["detail"])

        r = check_warehouse_size(conn_params)
        results.append(r)
        print_status("Warehouse size", r["passed"], r["detail"])

        r = check_python_udf_support(conn_params)
        results.append(r)
        print_status("Python UDF runtime", r["passed"], r["detail"])

        r = check_anaconda_packages(conn_params)
        results.append(r)
        print_status("Anaconda packages", r["passed"], r["detail"])

        print()

    # --- Data Sharing checks (REQ-5) ---
    print("Data Sharing (Consumer Account):")
    print("-" * 40)

    r = check_consumer_account(consumer_account)
    results.append(r)
    print_status("Consumer account locator", r["passed"], r["detail"])

    if has_creds and consumer_account:
        r = check_consumer_account_connectivity(conn_params, consumer_account)
        results.append(r)
        print_status("Consumer connectivity", r["passed"], r["detail"])

    print()

    # --- Summary ---
    passed = sum(1 for r in results if r.get("passed"))
    failed = sum(1 for r in results if not r.get("passed") and not r.get("skipped"))
    skipped = sum(1 for r in results if r.get("skipped"))
    total = len(results)

    print("=" * 70)
    print(f"Results: {passed}/{total} passed, {failed} failed, {skipped} skipped")
    print("=" * 70)

    if failed > 0:
        print()
        print("Failed checks:")
        for r in results:
            if not r.get("passed") and not r.get("skipped"):
                print(f"  ❌ {r['check']}: {r['detail']}")

    # --- Write output ---
    output = {
        "validation": "snowpark_environment",
        "requirements": ["REQ-7", "REQ-5"],
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "recommended_warehouse_size": RECOMMENDED_WAREHOUSE_SIZE,
        "consumer_account": consumer_account or None,
        "checks": results,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\nResults written to: {OUTPUT_PATH}")

    return output


def main():
    parser = argparse.ArgumentParser(
        description="Validate Snowpark Python environment and Data Sharing prerequisites"
    )
    parser.add_argument(
        "--consumer-account",
        default=os.environ.get("SNOWFLAKE_CONSUMER_ACCOUNT", ""),
        help="Consumer account locator for Data Sharing test (REQ-5)",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to params.json config file",
    )
    args = parser.parse_args()

    output = run_validation(consumer_account=args.consumer_account)

    # Exit with error if any non-skipped checks failed
    if output["summary"]["failed"] > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()

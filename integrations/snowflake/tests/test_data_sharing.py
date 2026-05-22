#!/usr/bin/env python3
"""
Data Sharing Verification Test Script
=======================================
Validates Secure Data Sharing configuration on Snowflake.

Checks:
  - Share exists (FSXN_LAKEHOUSE_SHARE)
  - Secure View returns filtered data (DAILY_REVENUE_SHARED)
  - Column masking: customer_id_hash is 64 characters (SHA-256 hex)
  - Row filtering: only approved categories (Electronics, Clothing, Food, Sports, Home)
  - DESCRIBE SHARE shows grants

Requirements: REQ-5 (Secure Data Sharing)

Environment Variables:
  SNOWFLAKE_ACCOUNT   - Snowflake account identifier
  SNOWFLAKE_USER      - Snowflake username
  SNOWFLAKE_PASSWORD  - Snowflake password
  SNOWFLAKE_WAREHOUSE - Warehouse name (default: COMPUTE_WH)

Usage:
  python test_data_sharing.py
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Color output helpers
# ---------------------------------------------------------------------------
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
NC = "\033[0m"


def info(msg):
    print(f"{BLUE}[INFO]{NC} {msg}")


def success(msg):
    print(f"{GREEN}[PASS]{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}[WARN]{NC} {msg}")


def fail(msg):
    print(f"{RED}[FAIL]{NC} {msg}")


def step(msg):
    print(f"{CYAN}[STEP]{NC} {msg}")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SF_ACCOUNT = os.environ.get("SNOWFLAKE_ACCOUNT", "")
SF_USER = os.environ.get("SNOWFLAKE_USER", "")
SF_PASSWORD = os.environ.get("SNOWFLAKE_PASSWORD", "")
SF_WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
SF_DATABASE = "FSXN_LAKEHOUSE"
SF_SCHEMA = "GOLD"

SHARE_NAME = "FSXN_LAKEHOUSE_SHARE"
SECURE_VIEW = "DAILY_REVENUE_SHARED"
APPROVED_CATEGORIES = {"Electronics", "Clothing", "Food", "Sports", "Home"}

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def validate_config():
    """Validate required environment variables."""
    errors = []
    if not SF_ACCOUNT:
        errors.append("SNOWFLAKE_ACCOUNT is required")
    if not SF_USER:
        errors.append("SNOWFLAKE_USER is required")
    if not SF_PASSWORD:
        errors.append("SNOWFLAKE_PASSWORD is required")
    if errors:
        for e in errors:
            fail(e)
        sys.exit(2)


def get_connection():
    """Create Snowflake connection."""
    import snowflake.connector

    return snowflake.connector.connect(
        account=SF_ACCOUNT,
        user=SF_USER,
        password=SF_PASSWORD,
        warehouse=SF_WAREHOUSE,
        database=SF_DATABASE,
        schema=SF_SCHEMA,
    )


def test_share_exists(cursor):
    """Verify the share object exists."""
    step("Testing share existence...")
    try:
        cursor.execute(f"SHOW SHARES LIKE '{SHARE_NAME}'")
        rows = cursor.fetchall()
        exists = len(rows) > 0

        result = {
            "test": "share_exists",
            "share_name": SHARE_NAME,
            "exists": exists,
            "passed": exists,
        }

        if exists:
            success(f"  Share '{SHARE_NAME}' exists")
        else:
            fail(f"  Share '{SHARE_NAME}' not found")

        return result
    except Exception as e:
        fail(f"  Error checking share: {e}")
        return {"test": "share_exists", "passed": False, "error": str(e)}


def test_secure_view_data(cursor):
    """Verify Secure View returns filtered data."""
    step("Testing Secure View returns data...")
    try:
        start_time = time.time()
        cursor.execute(f"""
            SELECT
                COUNT(*) AS row_count,
                COUNT(DISTINCT category) AS category_count,
                MIN(revenue_date) AS earliest_date,
                MAX(revenue_date) AS latest_date
            FROM {SECURE_VIEW}
        """)
        elapsed_ms = (time.time() - start_time) * 1000
        row = cursor.fetchone()

        row_count = row[0] if row else 0
        category_count = row[1] if row else 0
        earliest = row[2] if row else None
        latest = row[3] if row else None

        result = {
            "test": "secure_view_data",
            "row_count": row_count,
            "category_count": category_count,
            "earliest_date": str(earliest) if earliest else None,
            "latest_date": str(latest) if latest else None,
            "query_time_ms": round(elapsed_ms, 2),
            "passed": row_count > 0,
        }

        if result["passed"]:
            success(
                f"  Secure View: {row_count:,} rows, "
                f"{category_count} categories [{elapsed_ms:.0f}ms]"
            )
        else:
            fail(f"  Secure View returned 0 rows")

        return result
    except Exception as e:
        fail(f"  Error querying Secure View: {e}")
        return {"test": "secure_view_data", "passed": False, "error": str(e)}


def test_column_masking(cursor):
    """Verify customer_id_hash is 64 characters (SHA-256 hex)."""
    step("Testing column masking (customer_id_hash = 64 chars)...")
    try:
        cursor.execute(f"""
            SELECT
                customer_id_hash,
                LENGTH(customer_id_hash) AS hash_length
            FROM {SECURE_VIEW}
            WHERE customer_id_hash IS NOT NULL
            LIMIT 20
        """)
        rows = cursor.fetchall()

        if not rows:
            warn("  No rows with customer_id_hash found")
            return {
                "test": "column_masking",
                "passed": False,
                "error": "No rows returned",
            }

        # Check all hashes are 64 characters (SHA-256 produces 64 hex chars)
        all_valid = True
        invalid_examples = []
        for row in rows:
            hash_val = row[0]
            hash_len = row[1]
            if hash_len != 64:
                all_valid = False
                invalid_examples.append({"hash": hash_val, "length": hash_len})

        result = {
            "test": "column_masking",
            "rows_checked": len(rows),
            "all_64_chars": all_valid,
            "invalid_examples": invalid_examples[:3],
            "passed": all_valid,
        }

        if all_valid:
            success(f"  Column masking: all {len(rows)} hashes are 64 chars (SHA-256)")
        else:
            fail(
                f"  Column masking: {len(invalid_examples)} hashes have incorrect length"
            )

        return result
    except Exception as e:
        fail(f"  Error testing column masking: {e}")
        return {"test": "column_masking", "passed": False, "error": str(e)}


def test_row_filtering(cursor):
    """Verify only approved categories appear in the Secure View."""
    step("Testing row filtering (only approved categories)...")
    try:
        cursor.execute(f"""
            SELECT DISTINCT category
            FROM {SECURE_VIEW}
            ORDER BY category
        """)
        rows = cursor.fetchall()
        actual_categories = {row[0] for row in rows}

        # Check that all returned categories are in the approved set
        unauthorized = actual_categories - APPROVED_CATEGORIES
        all_approved = len(unauthorized) == 0

        result = {
            "test": "row_filtering",
            "actual_categories": sorted(list(actual_categories)),
            "approved_categories": sorted(list(APPROVED_CATEGORIES)),
            "unauthorized_categories": sorted(list(unauthorized)),
            "passed": all_approved and len(actual_categories) > 0,
        }

        if all_approved and actual_categories:
            success(
                f"  Row filtering: {len(actual_categories)} categories, "
                f"all approved: {sorted(actual_categories)}"
            )
        elif not actual_categories:
            fail("  Row filtering: no categories returned")
            result["passed"] = False
        else:
            fail(f"  Row filtering: unauthorized categories found: {sorted(unauthorized)}")

        return result
    except Exception as e:
        fail(f"  Error testing row filtering: {e}")
        return {"test": "row_filtering", "passed": False, "error": str(e)}


def test_describe_share(cursor):
    """Verify DESCRIBE SHARE shows grants."""
    step("Testing DESCRIBE SHARE shows grants...")
    try:
        cursor.execute(f"DESCRIBE SHARE {SHARE_NAME}")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        grants = []
        for row in rows:
            grant = dict(zip(columns, row))
            grants.append(grant)

        has_grants = len(grants) > 0

        result = {
            "test": "describe_share",
            "grant_count": len(grants),
            "grants": [
                {k: str(v) for k, v in g.items()} for g in grants[:10]
            ],
            "passed": has_grants,
        }

        if has_grants:
            success(f"  DESCRIBE SHARE: {len(grants)} grant(s) found")
            for g in grants[:5]:
                kind = g.get("kind", g.get("KIND", ""))
                name = g.get("name", g.get("NAME", ""))
                info(f"    {kind}: {name}")
        else:
            fail("  DESCRIBE SHARE: no grants found")

        return result
    except Exception as e:
        fail(f"  Error describing share: {e}")
        return {"test": "describe_share", "passed": False, "error": str(e)}


def write_results(results):
    """Write test results to JSON file."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_file = os.path.join(RESULTS_DIR, "data_sharing_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    info(f"Results written to: {output_file}")


def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║          Data Sharing Verification Test                                 ║")
    print("║          REQ-5: Secure Data Sharing                                     ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()

    validate_config()

    info(f"Account:    {SF_ACCOUNT}")
    info(f"Database:   {SF_DATABASE}.{SF_SCHEMA}")
    info(f"Warehouse:  {SF_WAREHOUSE}")
    info(f"Share:      {SHARE_NAME}")
    info(f"View:       {SECURE_VIEW}")
    print()

    results = {
        "test_name": "data_sharing",
        "test_time": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "account": SF_ACCOUNT,
            "database": SF_DATABASE,
            "schema": SF_SCHEMA,
            "warehouse": SF_WAREHOUSE,
            "share_name": SHARE_NAME,
            "secure_view": SECURE_VIEW,
        },
        "tests": {},
        "overall_status": "pass",
    }

    conn = get_connection()
    cursor = conn.cursor()
    all_passed = True

    # --- Test 1: Share exists ---
    print()
    share_result = test_share_exists(cursor)
    results["tests"]["share_exists"] = share_result
    if not share_result["passed"]:
        all_passed = False
    print()

    # --- Test 2: Secure View returns data ---
    view_result = test_secure_view_data(cursor)
    results["tests"]["secure_view_data"] = view_result
    if not view_result["passed"]:
        all_passed = False
    print()

    # --- Test 3: Column masking ---
    masking_result = test_column_masking(cursor)
    results["tests"]["column_masking"] = masking_result
    if not masking_result["passed"]:
        all_passed = False
    print()

    # --- Test 4: Row filtering ---
    filtering_result = test_row_filtering(cursor)
    results["tests"]["row_filtering"] = filtering_result
    if not filtering_result["passed"]:
        all_passed = False
    print()

    # --- Test 5: DESCRIBE SHARE ---
    describe_result = test_describe_share(cursor)
    results["tests"]["describe_share"] = describe_result
    if not describe_result["passed"]:
        all_passed = False
    print()

    # --- Summary ---
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if all_passed:
        results["overall_status"] = "pass"
        success("DATA SHARING VERIFICATION PASSED")
    else:
        results["overall_status"] = "fail"
        fail("DATA SHARING VERIFICATION FAILED")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    cursor.close()
    conn.close()

    write_results(results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

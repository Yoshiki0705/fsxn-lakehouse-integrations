#!/usr/bin/env python3
"""
Document Catalog Verification Test Script
===========================================
Validates the Document Catalog built from Directory Table + Snowpark UDF.

Checks:
  - DOCUMENT_CATALOG table has rows
  - estimated_pages > 0 for all entries
  - All PDF/DOCX files from Directory Table are cataloged (completeness check)

Requirements: REQ-6 (Unstructured Data via Directory Table)
              REQ-7 (Snowpark UDF processing for media files)

Environment Variables:
  SNOWFLAKE_ACCOUNT   - Snowflake account identifier
  SNOWFLAKE_USER      - Snowflake username
  SNOWFLAKE_PASSWORD  - Snowflake password
  SNOWFLAKE_WAREHOUSE - Warehouse name (default: COMPUTE_WH)

Usage:
  python test_document_catalog.py
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
SF_SCHEMA = "MEDIA"
STAGE_NAME = "FSXN_MEDIA_STAGE"

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


def test_catalog_has_rows(cursor):
    """Test DOCUMENT_CATALOG table has rows."""
    step("Testing DOCUMENT_CATALOG has rows...")

    try:
        start_time = time.time()
        cursor.execute("""
            SELECT
                COUNT(*) AS total_documents,
                COUNT(DISTINCT extension) AS distinct_extensions,
                SUM(estimated_pages) AS total_estimated_pages,
                ROUND(AVG(estimated_pages), 1) AS avg_pages_per_document
            FROM DOCUMENT_CATALOG
        """)
        elapsed_ms = (time.time() - start_time) * 1000
        row = cursor.fetchone()

        total_docs = row[0] if row else 0
        distinct_ext = row[1] if row else 0
        total_pages = row[2] if row else 0
        avg_pages = row[3] if row else 0

        result = {
            "test": "catalog_has_rows",
            "total_documents": total_docs,
            "distinct_extensions": distinct_ext,
            "total_estimated_pages": int(total_pages) if total_pages else 0,
            "avg_pages_per_document": float(avg_pages) if avg_pages else 0,
            "query_time_ms": round(elapsed_ms, 2),
            "passed": total_docs > 0,
        }

        if result["passed"]:
            success(
                f"  DOCUMENT_CATALOG: {total_docs} documents, "
                f"{distinct_ext} extensions, "
                f"~{total_pages} total pages [{elapsed_ms:.0f}ms]"
            )
        else:
            fail("  DOCUMENT_CATALOG: table is empty")

        return result

    except Exception as e:
        fail(f"  Error querying DOCUMENT_CATALOG: {e}")
        return {"test": "catalog_has_rows", "passed": False, "error": str(e)}


def test_estimated_pages_positive(cursor):
    """Test that estimated_pages > 0 for all entries."""
    step("Testing estimated_pages > 0 for all entries...")

    try:
        # Check for any entries with estimated_pages <= 0
        cursor.execute("""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(CASE WHEN estimated_pages > 0 THEN 1 END) AS positive_pages,
                COUNT(CASE WHEN estimated_pages <= 0 OR estimated_pages IS NULL THEN 1 END) AS zero_or_null_pages
            FROM DOCUMENT_CATALOG
        """)
        row = cursor.fetchone()

        total = row[0] if row else 0
        positive = row[1] if row else 0
        zero_or_null = row[2] if row else 0

        all_positive = zero_or_null == 0 and total > 0

        result = {
            "test": "estimated_pages_positive",
            "total_entries": total,
            "positive_pages": positive,
            "zero_or_null_pages": zero_or_null,
            "passed": all_positive,
        }

        if all_positive:
            success(f"  All {total} entries have estimated_pages > 0")
        elif total == 0:
            fail("  No entries in DOCUMENT_CATALOG")
            result["passed"] = False
        else:
            fail(f"  {zero_or_null}/{total} entries have estimated_pages <= 0 or NULL")

            # Show examples of problematic entries
            cursor.execute("""
                SELECT file_name, extension, file_size_bytes, estimated_pages
                FROM DOCUMENT_CATALOG
                WHERE estimated_pages <= 0 OR estimated_pages IS NULL
                LIMIT 5
            """)
            bad_rows = cursor.fetchall()
            for br in bad_rows:
                info(f"    {br[0]} ({br[1]}): size={br[2]}, pages={br[3]}")

        return result

    except Exception as e:
        fail(f"  Error checking estimated_pages: {e}")
        return {"test": "estimated_pages_positive", "passed": False, "error": str(e)}


def test_completeness(cursor):
    """Test all PDF/DOCX files from Directory Table are cataloged."""
    step("Testing catalog completeness (all PDF/DOCX files cataloged)...")

    try:
        # Refresh stage to ensure latest files
        cursor.execute(f"ALTER STAGE {STAGE_NAME} REFRESH")

        # Count PDF/DOCX files in Directory Table
        cursor.execute(f"""
            SELECT COUNT(*) AS directory_doc_count
            FROM DIRECTORY(@{STAGE_NAME})
            WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('pdf', 'docx')
        """)
        directory_count = cursor.fetchone()[0]

        # Count entries in DOCUMENT_CATALOG
        cursor.execute("SELECT COUNT(*) FROM DOCUMENT_CATALOG")
        catalog_count = cursor.fetchone()[0]

        # Find files in Directory Table but NOT in catalog
        cursor.execute(f"""
            SELECT d.RELATIVE_PATH
            FROM DIRECTORY(@{STAGE_NAME}) d
            WHERE LOWER(SPLIT_PART(d.RELATIVE_PATH, '.', -1)) IN ('pdf', 'docx')
              AND d.RELATIVE_PATH NOT IN (SELECT file_path FROM DOCUMENT_CATALOG)
            LIMIT 10
        """)
        missing_rows = cursor.fetchall()
        missing_files = [r[0] for r in missing_rows]

        is_complete = len(missing_files) == 0 and catalog_count >= directory_count

        result = {
            "test": "completeness",
            "directory_table_doc_count": directory_count,
            "catalog_count": catalog_count,
            "missing_files": missing_files,
            "missing_count": len(missing_files),
            "completeness_percent": round(
                catalog_count / directory_count * 100, 1
            ) if directory_count > 0 else 0,
            "passed": is_complete,
        }

        if is_complete:
            success(
                f"  Completeness: {catalog_count}/{directory_count} documents cataloged (100%)"
            )
        elif directory_count == 0:
            warn("  No PDF/DOCX files found in Directory Table")
            result["passed"] = True
            result["note"] = "No documents in Directory Table to catalog"
        else:
            completeness_pct = catalog_count / directory_count * 100
            fail(
                f"  Completeness: {catalog_count}/{directory_count} documents "
                f"({completeness_pct:.1f}%) — {len(missing_files)} missing"
            )
            for mf in missing_files[:5]:
                info(f"    Missing: {mf}")

        return result

    except Exception as e:
        fail(f"  Error checking completeness: {e}")
        return {"test": "completeness", "passed": False, "error": str(e)}


def write_results(results):
    """Write test results to JSON file."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_file = os.path.join(RESULTS_DIR, "document_catalog_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    info(f"Results written to: {output_file}")


def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║          Document Catalog Verification Test                             ║")
    print("║          REQ-6, REQ-7: Directory Table + Snowpark UDF                   ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()

    validate_config()

    info(f"Account:    {SF_ACCOUNT}")
    info(f"Database:   {SF_DATABASE}.{SF_SCHEMA}")
    info(f"Warehouse:  {SF_WAREHOUSE}")
    info(f"Stage:      {STAGE_NAME}")
    print()

    results = {
        "test_name": "document_catalog",
        "test_time": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "account": SF_ACCOUNT,
            "database": SF_DATABASE,
            "schema": SF_SCHEMA,
            "warehouse": SF_WAREHOUSE,
            "stage": STAGE_NAME,
        },
        "tests": {},
        "overall_status": "pass",
    }

    conn = get_connection()
    cursor = conn.cursor()
    all_passed = True

    # --- Test 1: DOCUMENT_CATALOG has rows ---
    print()
    rows_result = test_catalog_has_rows(cursor)
    results["tests"]["catalog_has_rows"] = rows_result
    if not rows_result["passed"]:
        all_passed = False
    print()

    # --- Test 2: estimated_pages > 0 ---
    pages_result = test_estimated_pages_positive(cursor)
    results["tests"]["estimated_pages_positive"] = pages_result
    if not pages_result["passed"]:
        all_passed = False
    print()

    # --- Test 3: Completeness check ---
    completeness_result = test_completeness(cursor)
    results["tests"]["completeness"] = completeness_result
    if not completeness_result["passed"]:
        all_passed = False
    print()

    # --- Summary ---
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if all_passed:
        results["overall_status"] = "pass"
        success("DOCUMENT CATALOG VERIFICATION PASSED")
    else:
        results["overall_status"] = "fail"
        fail("DOCUMENT CATALOG VERIFICATION FAILED")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    cursor.close()
    conn.close()

    write_results(results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

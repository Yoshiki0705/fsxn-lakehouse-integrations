#!/usr/bin/env python3
"""
Snowpark UDF Verification Test Script
=======================================
Validates Snowpark Python UDFs for media file processing.

Checks:
  - PARSE_IMAGE_FILENAME returns valid VARIANT (filename, extension, directory, base_name)
  - CLASSIFY_MEDIA_FILE classifies correctly (image/document/video/audio/other)
  - ENRICHED_MEDIA_CATALOG table has rows
  - Classification accuracy check (known extensions map to expected types)

Requirements: REQ-7 (Snowpark UDF processing for media files)

Environment Variables:
  SNOWFLAKE_ACCOUNT   - Snowflake account identifier
  SNOWFLAKE_USER      - Snowflake username
  SNOWFLAKE_PASSWORD  - Snowflake password
  SNOWFLAKE_WAREHOUSE - Warehouse name (default: COMPUTE_WH)

Usage:
  python test_snowpark_udfs.py
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

# Expected classification mappings for accuracy check
EXPECTED_CLASSIFICATIONS = {
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".gif": "image",
    ".pdf": "document",
    ".docx": "document",
    ".xlsx": "document",
    ".mp4": "video",
    ".mov": "video",
    ".mp3": "audio",
    ".wav": "audio",
}

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


def test_parse_image_filename(cursor):
    """Test PARSE_IMAGE_FILENAME UDF returns valid VARIANT."""
    step("Testing PARSE_IMAGE_FILENAME UDF...")

    test_cases = [
        ("images/photo_001.jpg", ".jpg", "images", "photo_001"),
        ("documents/report.pdf", ".pdf", "documents", "report"),
        ("video/demo.mp4", ".mp4", "video", "demo"),
        ("root_file.png", ".png", "", "root_file"),
    ]

    results_list = []
    all_valid = True

    for file_path, expected_ext, expected_dir, expected_base in test_cases:
        try:
            start_time = time.time()
            cursor.execute(f"""
                SELECT PARSE_IMAGE_FILENAME('{file_path}') AS parsed
            """)
            elapsed_ms = (time.time() - start_time) * 1000
            row = cursor.fetchone()
            parsed = json.loads(row[0]) if row and row[0] else None

            if parsed is None:
                all_valid = False
                results_list.append({
                    "input": file_path,
                    "passed": False,
                    "error": "NULL returned",
                })
                continue

            # Validate fields
            checks = {
                "extension": parsed.get("extension") == expected_ext,
                "directory": parsed.get("directory") == expected_dir,
                "base_name": parsed.get("base_name") == expected_base,
                "filename_present": parsed.get("filename") is not None,
            }

            passed = all(checks.values())
            if not passed:
                all_valid = False

            results_list.append({
                "input": file_path,
                "output": parsed,
                "checks": checks,
                "query_time_ms": round(elapsed_ms, 2),
                "passed": passed,
            })

        except Exception as e:
            all_valid = False
            results_list.append({
                "input": file_path,
                "passed": False,
                "error": str(e),
            })

    if all_valid:
        success(f"  PARSE_IMAGE_FILENAME: all {len(test_cases)} test cases passed")
    else:
        failed_count = sum(1 for r in results_list if not r["passed"])
        fail(f"  PARSE_IMAGE_FILENAME: {failed_count}/{len(test_cases)} test cases failed")

    return {
        "test": "parse_image_filename",
        "test_cases": results_list,
        "passed": all_valid,
    }


def test_classify_media_file(cursor):
    """Test CLASSIFY_MEDIA_FILE UDF classifies correctly."""
    step("Testing CLASSIFY_MEDIA_FILE UDF...")

    test_cases = [
        ("photo.jpg", 500000, "image", "small"),       # 500 KB image
        ("report.pdf", 2000000, "document", "medium"),  # 2 MB document
        ("video.mp4", 150000000, "video", "large"),     # 150 MB video
        ("song.mp3", 5000000, "audio", "medium"),       # 5 MB audio
        ("data.xyz", 1000, "other", "small"),           # unknown type
    ]

    results_list = []
    all_valid = True

    for file_path, file_size, expected_type, expected_size_cat in test_cases:
        try:
            start_time = time.time()
            cursor.execute(f"""
                SELECT CLASSIFY_MEDIA_FILE('{file_path}', {file_size}) AS classified
            """)
            elapsed_ms = (time.time() - start_time) * 1000
            row = cursor.fetchone()
            classified = json.loads(row[0]) if row and row[0] else None

            if classified is None:
                all_valid = False
                results_list.append({
                    "input": {"path": file_path, "size": file_size},
                    "passed": False,
                    "error": "NULL returned",
                })
                continue

            # Validate classification
            type_correct = classified.get("estimated_type") == expected_type
            size_correct = classified.get("size_category") == expected_size_cat
            has_processable = "is_processable" in classified

            passed = type_correct and size_correct and has_processable
            if not passed:
                all_valid = False

            results_list.append({
                "input": {"path": file_path, "size": file_size},
                "output": classified,
                "expected_type": expected_type,
                "expected_size_category": expected_size_cat,
                "type_correct": type_correct,
                "size_correct": size_correct,
                "query_time_ms": round(elapsed_ms, 2),
                "passed": passed,
            })

        except Exception as e:
            all_valid = False
            results_list.append({
                "input": {"path": file_path, "size": file_size},
                "passed": False,
                "error": str(e),
            })

    if all_valid:
        success(f"  CLASSIFY_MEDIA_FILE: all {len(test_cases)} test cases passed")
    else:
        failed_count = sum(1 for r in results_list if not r["passed"])
        fail(f"  CLASSIFY_MEDIA_FILE: {failed_count}/{len(test_cases)} test cases failed")

    return {
        "test": "classify_media_file",
        "test_cases": results_list,
        "passed": all_valid,
    }


def test_enriched_catalog_rows(cursor):
    """Test ENRICHED_MEDIA_CATALOG table has rows."""
    step("Testing ENRICHED_MEDIA_CATALOG table has rows...")

    try:
        start_time = time.time()
        cursor.execute("""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(DISTINCT media_type) AS distinct_types,
                COUNT(DISTINCT extension) AS distinct_extensions
            FROM ENRICHED_MEDIA_CATALOG
        """)
        elapsed_ms = (time.time() - start_time) * 1000
        row = cursor.fetchone()

        total_rows = row[0] if row else 0
        distinct_types = row[1] if row else 0
        distinct_extensions = row[2] if row else 0

        result = {
            "test": "enriched_catalog_rows",
            "total_rows": total_rows,
            "distinct_media_types": distinct_types,
            "distinct_extensions": distinct_extensions,
            "query_time_ms": round(elapsed_ms, 2),
            "passed": total_rows > 0,
        }

        if result["passed"]:
            success(
                f"  ENRICHED_MEDIA_CATALOG: {total_rows} rows, "
                f"{distinct_types} media types, {distinct_extensions} extensions"
            )
        else:
            fail("  ENRICHED_MEDIA_CATALOG: table is empty")

        return result

    except Exception as e:
        fail(f"  Error querying ENRICHED_MEDIA_CATALOG: {e}")
        return {"test": "enriched_catalog_rows", "passed": False, "error": str(e)}


def test_classification_accuracy(cursor):
    """Check classification accuracy against known extension-to-type mappings."""
    step("Testing classification accuracy...")

    try:
        cursor.execute("""
            SELECT
                extension,
                media_type,
                COUNT(*) AS file_count
            FROM ENRICHED_MEDIA_CATALOG
            WHERE extension IS NOT NULL
            GROUP BY extension, media_type
            ORDER BY file_count DESC
        """)
        rows = cursor.fetchall()

        if not rows:
            warn("  No data in ENRICHED_MEDIA_CATALOG for accuracy check")
            return {
                "test": "classification_accuracy",
                "passed": True,
                "skipped": True,
                "reason": "No data available",
            }

        correct = 0
        incorrect = 0
        checked = 0
        mismatches = []

        for row in rows:
            ext = row[0]  # e.g., '.jpg'
            actual_type = row[1]  # e.g., 'image'
            count = row[2]

            # Only check extensions we have expected mappings for
            if ext in EXPECTED_CLASSIFICATIONS:
                expected_type = EXPECTED_CLASSIFICATIONS[ext]
                checked += count
                if actual_type == expected_type:
                    correct += count
                else:
                    incorrect += count
                    mismatches.append({
                        "extension": ext,
                        "expected": expected_type,
                        "actual": actual_type,
                        "count": count,
                    })

        accuracy = (correct / checked * 100) if checked > 0 else 0
        passed = accuracy >= 90  # 90% accuracy threshold

        result = {
            "test": "classification_accuracy",
            "files_checked": checked,
            "correct": correct,
            "incorrect": incorrect,
            "accuracy_percent": round(accuracy, 1),
            "mismatches": mismatches[:5],
            "passed": passed,
        }

        if passed:
            success(f"  Classification accuracy: {accuracy:.1f}% ({correct}/{checked} correct)")
        else:
            fail(f"  Classification accuracy: {accuracy:.1f}% (below 90% threshold)")
            for m in mismatches[:3]:
                info(f"    {m['extension']}: expected={m['expected']}, actual={m['actual']}")

        return result

    except Exception as e:
        fail(f"  Error checking classification accuracy: {e}")
        return {"test": "classification_accuracy", "passed": False, "error": str(e)}


def write_results(results):
    """Write test results to JSON file."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_file = os.path.join(RESULTS_DIR, "snowpark_udfs_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    info(f"Results written to: {output_file}")


def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║          Snowpark UDF Verification Test                                 ║")
    print("║          REQ-7: Snowpark UDF processing for media files                 ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()

    validate_config()

    info(f"Account:    {SF_ACCOUNT}")
    info(f"Database:   {SF_DATABASE}.{SF_SCHEMA}")
    info(f"Warehouse:  {SF_WAREHOUSE}")
    print()

    results = {
        "test_name": "snowpark_udfs",
        "test_time": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "account": SF_ACCOUNT,
            "database": SF_DATABASE,
            "schema": SF_SCHEMA,
            "warehouse": SF_WAREHOUSE,
        },
        "tests": {},
        "overall_status": "pass",
    }

    conn = get_connection()
    cursor = conn.cursor()
    all_passed = True

    # --- Test 1: PARSE_IMAGE_FILENAME ---
    print()
    parse_result = test_parse_image_filename(cursor)
    results["tests"]["parse_image_filename"] = parse_result
    if not parse_result["passed"]:
        all_passed = False
    print()

    # --- Test 2: CLASSIFY_MEDIA_FILE ---
    classify_result = test_classify_media_file(cursor)
    results["tests"]["classify_media_file"] = classify_result
    if not classify_result["passed"]:
        all_passed = False
    print()

    # --- Test 3: ENRICHED_MEDIA_CATALOG has rows ---
    catalog_result = test_enriched_catalog_rows(cursor)
    results["tests"]["enriched_catalog_rows"] = catalog_result
    if not catalog_result["passed"]:
        all_passed = False
    print()

    # --- Test 4: Classification accuracy ---
    accuracy_result = test_classification_accuracy(cursor)
    results["tests"]["classification_accuracy"] = accuracy_result
    if not accuracy_result["passed"]:
        all_passed = False
    print()

    # --- Summary ---
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if all_passed:
        results["overall_status"] = "pass"
        success("SNOWPARK UDF VERIFICATION PASSED")
    else:
        results["overall_status"] = "fail"
        fail("SNOWPARK UDF VERIFICATION FAILED")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    cursor.close()
    conn.close()

    write_results(results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

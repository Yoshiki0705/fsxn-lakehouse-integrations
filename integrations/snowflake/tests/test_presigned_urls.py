#!/usr/bin/env python3
"""
Pre-signed URL Accessibility Test Script
==========================================

Tests that GET_PRESIGNED_URL() generates valid, accessible URLs from
Snowflake Directory Tables backed by FSxN S3 Access Points.

NOTE: AWS documentation states that Presign is "Not supported" for FSxN S3
Access Points. However, testing confirms it works in practice with FSxN S3 AP.

Checks:
  - GET_PRESIGNED_URL generates valid URLs from Directory Table
  - HTTP GET request returns status 200
  - Content-Length > 0 (file has content)

Requirements: REQ-6 (Unstructured Data via Directory Table + Pre-signed URLs)

Environment Variables:
  SNOWFLAKE_ACCOUNT   - Snowflake account identifier
  SNOWFLAKE_USER      - Snowflake username
  SNOWFLAKE_PASSWORD  - Snowflake password
  SNOWFLAKE_WAREHOUSE - Warehouse name (default: COMPUTE_WH)

Usage:
  python test_presigned_urls.py
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

# Number of URLs to test (limit to avoid excessive HTTP requests)
MAX_URLS_TO_TEST = 5

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


def generate_presigned_urls(cursor):
    """Generate pre-signed URLs from Directory Table via Snowflake."""
    step("Generating Pre-signed URLs from Directory Table...")

    try:
        # Refresh stage first
        cursor.execute(f"ALTER STAGE {STAGE_NAME} REFRESH")
        info("  Stage refreshed")

        # Generate pre-signed URLs for a sample of files
        cursor.execute(f"""
            SELECT
                RELATIVE_PATH,
                SIZE AS file_size_bytes,
                GET_PRESIGNED_URL(@{STAGE_NAME}, RELATIVE_PATH, 3600) AS presigned_url
            FROM DIRECTORY(@{STAGE_NAME})
            WHERE SIZE > 0
            ORDER BY SIZE DESC
            LIMIT {MAX_URLS_TO_TEST}
        """)
        rows = cursor.fetchall()

        urls = []
        for row in rows:
            urls.append({
                "relative_path": row[0],
                "file_size_bytes": row[1],
                "presigned_url": row[2],
            })

        if urls:
            success(f"  Generated {len(urls)} pre-signed URLs")
        else:
            warn("  No files found in Directory Table")

        return urls

    except Exception as e:
        fail(f"  Error generating pre-signed URLs: {e}")
        return []


def test_url_accessibility(url_info):
    """Test HTTP accessibility of a pre-signed URL."""
    import requests

    relative_path = url_info["relative_path"]
    presigned_url = url_info["presigned_url"]
    expected_size = url_info["file_size_bytes"]

    try:
        start_time = time.time()
        # Use HEAD request first to avoid downloading large files
        response = requests.head(presigned_url, timeout=30, allow_redirects=True)
        elapsed_ms = (time.time() - start_time) * 1000

        # If HEAD doesn't return content-length, try GET with stream
        content_length = response.headers.get("Content-Length")
        if content_length is None and response.status_code == 200:
            # Some S3 implementations don't support HEAD well; try GET
            response = requests.get(
                presigned_url, timeout=30, stream=True, allow_redirects=True
            )
            content_length = response.headers.get("Content-Length")
            # Close the stream without downloading full body
            response.close()

        status_code = response.status_code
        content_length_int = int(content_length) if content_length else 0

        result = {
            "relative_path": relative_path,
            "status_code": status_code,
            "content_length": content_length_int,
            "expected_size": expected_size,
            "response_time_ms": round(elapsed_ms, 2),
            "http_200": status_code == 200,
            "has_content": content_length_int > 0,
            "passed": status_code == 200 and content_length_int > 0,
        }

        return result

    except requests.exceptions.Timeout:
        return {
            "relative_path": relative_path,
            "passed": False,
            "error": "Request timed out (30s)",
        }
    except requests.exceptions.ConnectionError as e:
        return {
            "relative_path": relative_path,
            "passed": False,
            "error": f"Connection error: {e}",
        }
    except Exception as e:
        return {
            "relative_path": relative_path,
            "passed": False,
            "error": str(e),
        }


def write_results(results):
    """Write test results to JSON file."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_file = os.path.join(RESULTS_DIR, "presigned_urls_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    info(f"Results written to: {output_file}")


def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║          Pre-signed URL Accessibility Test                              ║")
    print("║          REQ-6: Unstructured Data via Directory Table + Pre-signed URLs  ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()

    validate_config()

    info(f"Account:    {SF_ACCOUNT}")
    info(f"Database:   {SF_DATABASE}.{SF_SCHEMA}")
    info(f"Warehouse:  {SF_WAREHOUSE}")
    info(f"Stage:      {STAGE_NAME}")
    info(f"Max URLs:   {MAX_URLS_TO_TEST}")
    print()

    results = {
        "test_name": "presigned_urls",
        "test_time": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "account": SF_ACCOUNT,
            "database": SF_DATABASE,
            "schema": SF_SCHEMA,
            "warehouse": SF_WAREHOUSE,
            "stage": STAGE_NAME,
            "max_urls_tested": MAX_URLS_TO_TEST,
        },
        "url_generation": {},
        "accessibility_tests": [],
        "overall_status": "pass",
    }

    conn = get_connection()
    cursor = conn.cursor()

    # --- Step 1: Generate pre-signed URLs ---
    print()
    urls = generate_presigned_urls(cursor)
    results["url_generation"] = {
        "urls_generated": len(urls),
        "passed": len(urls) > 0,
    }

    if not urls:
        fail("No pre-signed URLs generated — cannot test accessibility")
        results["overall_status"] = "fail"
        cursor.close()
        conn.close()
        write_results(results)
        sys.exit(1)
    print()

    # --- Step 2: Test HTTP accessibility ---
    step(f"Testing HTTP accessibility for {len(urls)} URLs...")
    print()

    # Check if requests library is available
    try:
        import requests  # noqa: F401
    except ImportError:
        fail("  'requests' library not installed. Install with: pip install requests")
        results["overall_status"] = "fail"
        results["accessibility_tests"] = [{"error": "requests library not installed"}]
        cursor.close()
        conn.close()
        write_results(results)
        sys.exit(1)

    all_passed = True
    for i, url_info in enumerate(urls, 1):
        relative_path = url_info["relative_path"]
        info(f"  [{i}/{len(urls)}] Testing: {relative_path}")

        test_result = test_url_accessibility(url_info)
        results["accessibility_tests"].append(test_result)

        if test_result["passed"]:
            content_len = test_result.get("content_length", 0)
            resp_time = test_result.get("response_time_ms", 0)
            success(
                f"         HTTP 200 ✓ | Content-Length: {content_len:,} bytes "
                f"| {resp_time:.0f}ms"
            )
        else:
            error = test_result.get("error", "")
            status = test_result.get("status_code", "N/A")
            if error:
                fail(f"         FAILED: {error}")
            else:
                fail(f"         HTTP {status} | Content-Length: {test_result.get('content_length', 0)}")
            all_passed = False

    print()

    # --- Summary ---
    passed_count = sum(1 for t in results["accessibility_tests"] if t.get("passed"))
    total_count = len(results["accessibility_tests"])

    results["summary"] = {
        "total_tested": total_count,
        "passed": passed_count,
        "failed": total_count - passed_count,
        "pass_rate": round(passed_count / total_count * 100, 1) if total_count > 0 else 0,
    }

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if all_passed:
        results["overall_status"] = "pass"
        success(f"PRE-SIGNED URL TEST PASSED ({passed_count}/{total_count} URLs accessible)")
    else:
        results["overall_status"] = "fail"
        fail(
            f"PRE-SIGNED URL TEST FAILED ({passed_count}/{total_count} URLs accessible)"
        )
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    cursor.close()
    conn.close()

    write_results(results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

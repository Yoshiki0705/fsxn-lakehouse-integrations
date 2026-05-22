#!/usr/bin/env python3
"""
External Table Verification Test Script
========================================
Validates External Tables (TRANSACTIONS, IOT_SENSORS, CUSTOMERS_CSV, EVENTS_JSON)
on FSx for ONTAP via S3 Access Point.

Checks:
  - Row counts > 0 for each External Table
  - Query execution succeeds without errors
  - bytes_scanned metrics captured from QUERY_HISTORY

Requirements: REQ-2 (External Table queries on Parquet, CSV, JSON)

Environment Variables:
  SNOWFLAKE_ACCOUNT   - Snowflake account identifier
  SNOWFLAKE_USER      - Snowflake username
  SNOWFLAKE_PASSWORD  - Snowflake password
  SNOWFLAKE_WAREHOUSE - Warehouse name (default: COMPUTE_WH)

Usage:
  python test_external_tables.py
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
SF_SCHEMA = "BRONZE"

EXTERNAL_TABLES = [
    "TRANSACTIONS",
    "IOT_SENSORS",
    "CUSTOMERS_CSV",
    "EVENTS_JSON",
]

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


def test_row_count(cursor, table_name):
    """Test that a table has rows > 0 and capture metrics."""
    query = f"SELECT COUNT(*) AS row_count FROM {table_name}"
    start_time = time.time()
    cursor.execute(query)
    elapsed_ms = (time.time() - start_time) * 1000
    row = cursor.fetchone()
    row_count = row[0] if row else 0

    # Capture query ID for metrics lookup
    cursor.execute("SELECT LAST_QUERY_ID()")
    query_id = cursor.fetchone()[0]

    return {
        "table_name": table_name,
        "row_count": row_count,
        "query_time_ms": round(elapsed_ms, 2),
        "query_id": query_id,
        "passed": row_count > 0,
    }


def test_analytical_query(cursor, table_name):
    """Run an analytical query (GROUP BY) to verify query execution."""
    queries = {
        "TRANSACTIONS": """
            SELECT category, COUNT(*) AS cnt, SUM(amount) AS total
            FROM TRANSACTIONS
            GROUP BY category
            ORDER BY total DESC
            LIMIT 5
        """,
        "IOT_SENSORS": """
            SELECT sensor_location, COUNT(*) AS cnt, AVG(temperature) AS avg_temp
            FROM IOT_SENSORS
            GROUP BY sensor_location
            ORDER BY cnt DESC
            LIMIT 5
        """,
        "CUSTOMERS_CSV": """
            SELECT country, segment, COUNT(*) AS cnt
            FROM CUSTOMERS_CSV
            GROUP BY country, segment
            ORDER BY cnt DESC
            LIMIT 5
        """,
        "EVENTS_JSON": """
            SELECT event_type, COUNT(*) AS cnt
            FROM EVENTS_JSON
            GROUP BY event_type
            ORDER BY cnt DESC
            LIMIT 5
        """,
    }

    query = queries.get(table_name)
    if not query:
        return {"table_name": table_name, "passed": False, "error": "No query defined"}

    start_time = time.time()
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        elapsed_ms = (time.time() - start_time) * 1000

        cursor.execute("SELECT LAST_QUERY_ID()")
        query_id = cursor.fetchone()[0]

        return {
            "table_name": table_name,
            "rows_returned": len(rows),
            "query_time_ms": round(elapsed_ms, 2),
            "query_id": query_id,
            "passed": len(rows) > 0,
        }
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return {
            "table_name": table_name,
            "passed": False,
            "error": str(e),
            "query_time_ms": round(elapsed_ms, 2),
        }


def get_bytes_scanned(cursor, query_ids):
    """Retrieve bytes_scanned from QUERY_HISTORY for given query IDs."""
    if not query_ids:
        return {}

    id_list = ", ".join(f"'{qid}'" for qid in query_ids)
    query = f"""
        SELECT
            query_id,
            bytes_scanned,
            rows_produced,
            total_elapsed_time,
            compilation_time,
            execution_time
        FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
            RESULT_LIMIT => 50,
            END_TIME_RANGE_START => DATEADD('minute', -10, CURRENT_TIMESTAMP())
        ))
        WHERE query_id IN ({id_list})
    """
    try:
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        metrics = {}
        for row in rows:
            record = dict(zip(columns, row))
            metrics[record["QUERY_ID"]] = {
                "bytes_scanned": record.get("BYTES_SCANNED", 0),
                "rows_produced": record.get("ROWS_PRODUCED", 0),
                "total_elapsed_time": record.get("TOTAL_ELAPSED_TIME", 0),
                "compilation_time": record.get("COMPILATION_TIME", 0),
                "execution_time": record.get("EXECUTION_TIME", 0),
            }
        return metrics
    except Exception as e:
        warn(f"Could not retrieve QUERY_HISTORY metrics: {e}")
        return {}


def write_results(results):
    """Write test results to JSON file."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_file = os.path.join(RESULTS_DIR, "external_tables_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    info(f"Results written to: {output_file}")


def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║          External Table Verification Test                               ║")
    print("║          REQ-2: External Table queries on Parquet, CSV, JSON            ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()

    validate_config()

    info(f"Account:    {SF_ACCOUNT}")
    info(f"Database:   {SF_DATABASE}.{SF_SCHEMA}")
    info(f"Warehouse:  {SF_WAREHOUSE}")
    info(f"Tables:     {', '.join(EXTERNAL_TABLES)}")
    print()

    results = {
        "test_name": "external_tables",
        "test_time": datetime.now(timezone.utc).isoformat(),
        "configuration": {
            "account": SF_ACCOUNT,
            "database": SF_DATABASE,
            "schema": SF_SCHEMA,
            "warehouse": SF_WAREHOUSE,
        },
        "tables": {},
        "overall_status": "pass",
    }

    conn = get_connection()
    cursor = conn.cursor()
    all_query_ids = []
    all_passed = True

    # --- Test 1: Row counts ---
    step("1/3 Validating row counts for each External Table...")
    print()
    for table in EXTERNAL_TABLES:
        result = test_row_count(cursor, table)
        results["tables"][table] = {"row_count": result}
        all_query_ids.append(result["query_id"])

        if result["passed"]:
            success(f"  {table}: {result['row_count']:,} rows ({result['query_time_ms']:.0f}ms)")
        else:
            fail(f"  {table}: 0 rows — table is empty or inaccessible")
            all_passed = False
    print()

    # --- Test 2: Analytical queries ---
    step("2/3 Running analytical queries (GROUP BY, aggregation)...")
    print()
    for table in EXTERNAL_TABLES:
        result = test_analytical_query(cursor, table)
        results["tables"][table]["analytical_query"] = result
        if result.get("query_id"):
            all_query_ids.append(result["query_id"])

        if result["passed"]:
            success(
                f"  {table}: {result['rows_returned']} groups returned "
                f"({result['query_time_ms']:.0f}ms)"
            )
        else:
            fail(f"  {table}: query failed — {result.get('error', 'unknown')}")
            all_passed = False
    print()

    # --- Test 3: Bytes scanned metrics ---
    step("3/3 Capturing bytes_scanned metrics from QUERY_HISTORY...")
    print()
    metrics = get_bytes_scanned(cursor, all_query_ids)
    for table in EXTERNAL_TABLES:
        table_results = results["tables"][table]
        # Attach metrics to row_count query
        qid = table_results["row_count"].get("query_id")
        if qid and qid in metrics:
            table_results["row_count"]["metrics"] = metrics[qid]
            bytes_val = metrics[qid]["bytes_scanned"]
            info(f"  {table} (count): {bytes_val:,} bytes scanned")
        # Attach metrics to analytical query
        qid = table_results.get("analytical_query", {}).get("query_id")
        if qid and qid in metrics:
            table_results["analytical_query"]["metrics"] = metrics[qid]
            bytes_val = metrics[qid]["bytes_scanned"]
            info(f"  {table} (analytics): {bytes_val:,} bytes scanned")

    results["metrics_captured"] = len(metrics) > 0
    print()

    # --- Summary ---
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if all_passed:
        results["overall_status"] = "pass"
        success("EXTERNAL TABLE VERIFICATION PASSED")
    else:
        results["overall_status"] = "fail"
        fail("EXTERNAL TABLE VERIFICATION FAILED")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    cursor.close()
    conn.close()

    write_results(results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()

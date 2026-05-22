#!/usr/bin/env python3
"""
Snowpipe Latency Comparison Test Script
=========================================
Measures and compares FPolicy event-driven (<30s) vs Lambda polling (5-7min) latency.

Reads snowpipe_e2e_results.json for FPolicy timing, estimates Lambda polling timing
based on 5-minute interval, and outputs comparison metrics.

Requirements: REQ-4 (Snowpipe auto-ingest, FPolicy event-driven)

Environment Variables:
  SNOWFLAKE_ACCOUNT   - Snowflake account identifier
  SNOWFLAKE_USER      - Snowflake username
  SNOWFLAKE_PASSWORD  - Snowflake password
  SNOWFLAKE_WAREHOUSE - Warehouse name (default: COMPUTE_WH)

Usage:
  python test_latency_comparison.py
"""

import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Color output helpers
# ---------------------------------------------------------------------------
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
MAGENTA = "\033[0;35m"
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


def highlight(msg):
    print(f"{MAGENTA}[METRIC]{NC} {msg}")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SF_ACCOUNT = os.environ.get("SNOWFLAKE_ACCOUNT", "")
SF_USER = os.environ.get("SNOWFLAKE_USER", "")
SF_PASSWORD = os.environ.get("SNOWFLAKE_PASSWORD", "")
SF_WAREHOUSE = os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
E2E_RESULTS_FILE = os.path.join(RESULTS_DIR, "snowpipe_e2e_results.json")

# Lambda polling configuration (design document values)
LAMBDA_POLLING_INTERVAL_SEC = 300  # 5 minutes
LAMBDA_COPY_TIME_SEC = 20  # Average COPY INTO time
LAMBDA_MIN_LATENCY_SEC = LAMBDA_COPY_TIME_SEC  # Best case: file arrives just before poll
LAMBDA_MAX_LATENCY_SEC = LAMBDA_POLLING_INTERVAL_SEC + LAMBDA_COPY_TIME_SEC  # Worst case
LAMBDA_AVG_LATENCY_SEC = (LAMBDA_POLLING_INTERVAL_SEC / 2) + LAMBDA_COPY_TIME_SEC  # Average

# FPolicy target
FPOLICY_TARGET_SEC = 30


def load_fpolicy_results():
    """Load FPolicy E2E test results from JSON file."""
    if not os.path.exists(E2E_RESULTS_FILE):
        return None

    try:
        with open(E2E_RESULTS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        warn(f"Could not parse {E2E_RESULTS_FILE}: {e}")
        return None


def query_copy_history(cursor):
    """Query Snowflake COPY_HISTORY for recent Snowpipe loads."""
    try:
        cursor.execute("""
            SELECT
                pipe_name,
                file_name,
                stage_location,
                row_count,
                file_size,
                first_commit_time,
                last_load_time,
                DATEDIFF('second', first_commit_time, last_load_time) AS load_latency_sec
            FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
                TABLE_NAME => 'RAW_EVENTS',
                START_TIME => DATEADD('hour', -24, CURRENT_TIMESTAMP())
            ))
            ORDER BY last_load_time DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        warn(f"Could not query COPY_HISTORY: {e}")
        return []


def calculate_comparison(fpolicy_latency_ms):
    """Calculate latency comparison metrics."""
    fpolicy_sec = fpolicy_latency_ms / 1000.0

    return {
        "fpolicy": {
            "measured_latency_ms": fpolicy_latency_ms,
            "measured_latency_sec": round(fpolicy_sec, 2),
            "within_target": fpolicy_sec < FPOLICY_TARGET_SEC,
            "target_sec": FPOLICY_TARGET_SEC,
            "pipeline": "NFS → FPolicy → Fargate → SQS → Lambda → SNS → Snowpipe",
        },
        "lambda_polling": {
            "polling_interval_sec": LAMBDA_POLLING_INTERVAL_SEC,
            "copy_time_sec": LAMBDA_COPY_TIME_SEC,
            "min_latency_sec": LAMBDA_MIN_LATENCY_SEC,
            "max_latency_sec": LAMBDA_MAX_LATENCY_SEC,
            "avg_latency_sec": round(LAMBDA_AVG_LATENCY_SEC, 2),
            "pipeline": "EventBridge (5min) → Lambda → ListObjects → SNS → Snowpipe",
        },
        "improvement": {
            "vs_avg_factor": round(LAMBDA_AVG_LATENCY_SEC / max(fpolicy_sec, 0.1), 1),
            "vs_max_factor": round(LAMBDA_MAX_LATENCY_SEC / max(fpolicy_sec, 0.1), 1),
            "time_saved_avg_sec": round(LAMBDA_AVG_LATENCY_SEC - fpolicy_sec, 2),
            "time_saved_max_sec": round(LAMBDA_MAX_LATENCY_SEC - fpolicy_sec, 2),
            "improvement_percent": round(
                (1 - fpolicy_sec / LAMBDA_AVG_LATENCY_SEC) * 100, 1
            )
            if LAMBDA_AVG_LATENCY_SEC > 0
            else 0,
        },
    }


def write_results(results):
    """Write comparison results to JSON file."""
    os.makedirs(RESULTS_DIR, exist_ok=True)
    output_file = os.path.join(RESULTS_DIR, "latency_comparison_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    info(f"Results written to: {output_file}")


def main():
    print()
    print("╔══════════════════════════════════════════════════════════════════════════╗")
    print("║          Snowpipe Latency Comparison                                    ║")
    print("║          REQ-4: FPolicy (<30s) vs Lambda Polling (5-7min)               ║")
    print("╚══════════════════════════════════════════════════════════════════════════╝")
    print()

    results = {
        "test_name": "latency_comparison",
        "test_time": datetime.now(timezone.utc).isoformat(),
        "overall_status": "pass",
        "fpolicy_data_source": None,
        "comparison": None,
        "copy_history": [],
    }

    # --- Step 1: Load FPolicy E2E results ---
    step("1/3 Loading FPolicy E2E test results...")
    fpolicy_results = load_fpolicy_results()

    fpolicy_latency_ms = None
    if fpolicy_results:
        fpolicy_latency_ms = fpolicy_results.get("metrics", {}).get("e2e_latency_ms")
        if fpolicy_latency_ms and fpolicy_latency_ms > 0:
            results["fpolicy_data_source"] = E2E_RESULTS_FILE
            success(
                f"  FPolicy E2E result loaded: {fpolicy_latency_ms}ms "
                f"({fpolicy_latency_ms/1000:.2f}s)"
            )
        else:
            warn("  FPolicy E2E result found but latency is 0 or missing (test may have failed)")
            fpolicy_latency_ms = None
    else:
        warn(f"  No FPolicy E2E results found at: {E2E_RESULTS_FILE}")
        info("  Using design target value (30s) for comparison")
    print()

    # --- Step 2: Query COPY_HISTORY (if Snowflake credentials available) ---
    step("2/3 Querying Snowflake COPY_HISTORY for recent loads...")
    copy_history = []
    if SF_ACCOUNT and SF_USER and SF_PASSWORD:
        try:
            import snowflake.connector

            conn = snowflake.connector.connect(
                account=SF_ACCOUNT,
                user=SF_USER,
                password=SF_PASSWORD,
                warehouse=SF_WAREHOUSE,
                database="FSXN_LAKEHOUSE",
                schema="BRONZE",
            )
            cursor = conn.cursor()
            copy_history = query_copy_history(cursor)
            cursor.close()
            conn.close()

            if copy_history:
                info(f"  Found {len(copy_history)} recent COPY_HISTORY entries")
                for entry in copy_history[:3]:
                    latency = entry.get("LOAD_LATENCY_SEC", "N/A")
                    fname = entry.get("FILE_NAME", "unknown")
                    info(f"    {fname}: {latency}s")
            else:
                info("  No recent COPY_HISTORY entries found")
        except ImportError:
            warn("  snowflake-connector-python not installed — skipping COPY_HISTORY")
        except Exception as e:
            warn(f"  Could not query COPY_HISTORY: {e}")
    else:
        info("  Snowflake credentials not set — skipping COPY_HISTORY query")

    results["copy_history"] = copy_history
    print()

    # --- Step 3: Calculate comparison ---
    step("3/3 Calculating latency comparison...")
    print()

    # Use measured FPolicy latency or design target
    if fpolicy_latency_ms is None:
        # Use design target for comparison
        fpolicy_latency_ms = FPOLICY_TARGET_SEC * 1000  # 30s in ms
        results["fpolicy_data_source"] = "design_target (no measured data)"

    comparison = calculate_comparison(fpolicy_latency_ms)
    results["comparison"] = comparison

    # --- Display comparison table ---
    print("┌─────────────────────────────────────────────────────────────────────┐")
    print("│                    LATENCY COMPARISON                                │")
    print("├─────────────────────┬──────────────────┬─────────────────────────────┤")
    print("│ Metric              │ FPolicy          │ Lambda Polling              │")
    print("├─────────────────────┼──────────────────┼─────────────────────────────┤")

    fp_sec = comparison["fpolicy"]["measured_latency_sec"]
    lp_avg = comparison["lambda_polling"]["avg_latency_sec"]
    lp_max = comparison["lambda_polling"]["max_latency_sec"]

    print(f"│ Measured/Avg Latency│ {fp_sec:>8.1f}s        │ {lp_avg:>8.1f}s (avg)              │")
    print(f"│ Max Latency         │ {FPOLICY_TARGET_SEC:>8}s (target)│ {lp_max:>8}s (worst case)       │")
    print(f"│ Min Latency         │       <1s        │ {LAMBDA_MIN_LATENCY_SEC:>8}s (best case)        │")
    print("├─────────────────────┼──────────────────┼─────────────────────────────┤")

    pipeline_fp = "FPolicy→SQS→SNS"
    pipeline_lp = "EB→Lambda→SNS"
    print(f"│ Pipeline            │ {pipeline_fp:<16} │ {pipeline_lp:<27} │")
    print("├─────────────────────┴──────────────────┴─────────────────────────────┤")

    improvement_pct = comparison["improvement"]["improvement_percent"]
    improvement_factor = comparison["improvement"]["vs_avg_factor"]
    print(f"│ Improvement: {improvement_pct:.0f}% faster ({improvement_factor:.0f}x vs avg Lambda polling)       │")
    print("└─────────────────────────────────────────────────────────────────────┘")
    print()

    # --- Metrics highlights ---
    highlight(f"FPolicy E2E Latency:     {fp_sec:.2f}s")
    highlight(f"Lambda Polling Avg:      {lp_avg:.1f}s")
    highlight(f"Improvement Factor:      {improvement_factor:.1f}x faster")
    highlight(f"Time Saved (avg):        {comparison['improvement']['time_saved_avg_sec']:.1f}s per file")
    highlight(f"Within 30s Target:       {'YES ✓' if comparison['fpolicy']['within_target'] else 'NO ✗'}")
    print()

    # --- Pass/Fail ---
    fpolicy_within_target = comparison["fpolicy"]["within_target"]

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if fpolicy_within_target:
        results["overall_status"] = "pass"
        success("LATENCY COMPARISON PASSED — FPolicy within 30s target")
    else:
        results["overall_status"] = "fail"
        fail(f"LATENCY COMPARISON FAILED — FPolicy latency {fp_sec:.1f}s exceeds 30s target")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print()

    write_results(results)
    sys.exit(0 if fpolicy_within_target else 1)


if __name__ == "__main__":
    main()

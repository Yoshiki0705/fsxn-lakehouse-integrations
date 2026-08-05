#!/usr/bin/env python3
"""
FSx for ONTAP DuckDB Integration — Write-Back Verification

Writes DuckDB query results back to FSx for ONTAP via S3 AP using COPY command.
Verifies data integrity by reading back written files.

Usage:
    python 03_write_back.py [--ap-alias <alias>]
"""

import argparse
import json
import time
from pathlib import Path

import boto3
import duckdb


def setup_conn(region: str) -> duckdb.DuckDBPyConnection:
    session = boto3.Session(region_name=region)
    creds = session.get_credentials().get_frozen_credentials()
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute(f"SET s3_region='{creds.region or region}';")
    conn.execute(f"SET s3_access_key_id='{creds.access_key}';")
    conn.execute(f"SET s3_secret_access_key='{creds.secret_key}';")
    if creds.token:
        conn.execute(f"SET s3_session_token='{creds.token}';")
    conn.execute("SET s3_url_style='path';")
    return conn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ap-alias", default=None)
    parser.add_argument("--region", default="ap-northeast-1")
    args = parser.parse_args()

    ap_alias = args.ap_alias
    if not ap_alias:
        params_file = Path(__file__).parent.parent / "params.json"
        if params_file.exists():
            ap_alias = json.load(open(params_file)).get("S3AccessPointAlias")
    if not ap_alias:
        print("❌ --ap-alias required"); return

    print("=" * 60)
    print("DuckDB Write-Back Verification")
    print("=" * 60)

    conn = setup_conn(args.region)
    base = f"s3://{ap_alias}"
    results = []

    # --- Test 1: Write Parquet ---
    print("\n▶ Test 1: Write aggregation results as Parquet")
    output_parquet = f"{base}/gold/duckdb_category_summary.parquet"
    start = time.time()
    try:
        conn.execute(f"""
            COPY (
                SELECT category, COUNT(*) AS cnt, SUM(amount) AS total, AVG(amount) AS avg_amount
                FROM read_parquet('{base}/transactions/**/*.parquet')
                GROUP BY category
            ) TO '{output_parquet}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """)
        write_time = (time.time() - start) * 1000
        print(f"  ✅ Written in {write_time:.0f}ms: {output_parquet}")

        # Read back and verify
        readback = conn.execute(f"SELECT COUNT(*) FROM read_parquet('{output_parquet}')").fetchone()
        print(f"  ✅ Read-back: {readback[0]} rows")
        results.append({"test": "write_parquet", "success": True, "write_ms": write_time, "rows": readback[0]})
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({"test": "write_parquet", "success": False, "error": str(e)})

    # --- Test 2: Write CSV ---
    print("\n▶ Test 2: Write customer summary as CSV")
    output_csv = f"{base}/gold/duckdb_customer_top10.csv"
    start = time.time()
    try:
        conn.execute(f"""
            COPY (
                SELECT customer_id, COUNT(*) AS txn_count, SUM(amount) AS total_spent
                FROM read_parquet('{base}/transactions/**/*.parquet')
                GROUP BY customer_id
                ORDER BY total_spent DESC
                LIMIT 10
            ) TO '{output_csv}' (FORMAT CSV, HEADER)
        """)
        write_time = (time.time() - start) * 1000
        print(f"  ✅ Written in {write_time:.0f}ms: {output_csv}")

        readback = conn.execute(f"SELECT COUNT(*) FROM read_csv_auto('{output_csv}')").fetchone()
        print(f"  ✅ Read-back: {readback[0]} rows")
        results.append({"test": "write_csv", "success": True, "write_ms": write_time, "rows": readback[0]})
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({"test": "write_csv", "success": False, "error": str(e)})

    # --- Test 3: Data integrity check ---
    print("\n▶ Test 3: Data integrity verification")
    try:
        # Write known data
        conn.execute(f"""
            COPY (SELECT 42 AS answer, 'hello' AS greeting, 3.14 AS pi)
            TO '{base}/gold/duckdb_integrity_test.parquet' (FORMAT PARQUET)
        """)
        # Read back and compare
        row = conn.execute(f"SELECT * FROM read_parquet('{base}/gold/duckdb_integrity_test.parquet')").fetchone()
        assert row[0] == 42 and row[1] == "hello" and abs(row[2] - 3.14) < 0.001
        print("  ✅ Data integrity verified (exact match)")
        results.append({"test": "integrity", "success": True})
    except Exception as e:
        print(f"  ❌ Integrity check failed: {e}")
        results.append({"test": "integrity", "success": False, "error": str(e)})

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r.get("success"))
    print(f"Results: {passed}/{len(results)} tests passed")

    output_path = Path(__file__).parent.parent / "tests/results/write_back_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(results, open(output_path, "w"), indent=2)
    print(f"📊 Results: {output_path}")


if __name__ == "__main__":
    main()

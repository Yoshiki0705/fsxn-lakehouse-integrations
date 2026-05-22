#!/usr/bin/env python3
"""
FSxN DuckDB Integration — Local Query Verification

Configures DuckDB httpfs for S3 Access Point and executes analytical queries
on FSxN data. Records execution time and memory usage.

Prerequisites:
    pip install duckdb boto3

Usage:
    python 01_local_queries.py [--ap-alias <alias>] [--region ap-northeast-1]
"""

import argparse
import json
import os
import time
from pathlib import Path

import boto3
import duckdb


def get_aws_credentials(region: str) -> dict:
    """Get temporary credentials from the current AWS session."""
    session = boto3.Session(region_name=region)
    credentials = session.get_credentials().get_frozen_credentials()
    return {
        "access_key": credentials.access_key,
        "secret_key": credentials.secret_key,
        "session_token": credentials.token,
        "region": region,
    }


def configure_duckdb(conn: duckdb.DuckDBPyConnection, creds: dict) -> None:
    """Configure DuckDB httpfs for S3 Access Point access."""
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute(f"SET s3_region = '{creds['region']}';")
    conn.execute(f"SET s3_access_key_id = '{creds['access_key']}';")
    conn.execute(f"SET s3_secret_access_key = '{creds['secret_key']}';")
    if creds.get("session_token"):
        conn.execute(f"SET s3_session_token = '{creds['session_token']}';")
    # Path-style access for S3 AP aliases
    conn.execute("SET s3_url_style = 'path';")
    print("✅ DuckDB httpfs configured for S3 AP")


def run_query(conn: duckdb.DuckDBPyConnection, label: str, query: str) -> dict:
    """Execute a query and return results with metrics."""
    print(f"\n▶ {label}")
    print(f"  Query: {query[:100]}...")

    start = time.time()
    try:
        result = conn.execute(query)
        rows = result.fetchall()
        elapsed = time.time() - start
        cols = [d[0] for d in result.description] if result.description else []

        print(f"  ✅ {len(rows)} rows in {elapsed*1000:.0f}ms")
        if rows:
            # Print first 3 rows
            for row in rows[:3]:
                print(f"     {dict(zip(cols, row))}")
            if len(rows) > 3:
                print(f"     ... ({len(rows) - 3} more rows)")

        return {"label": label, "rows": len(rows), "time_ms": elapsed * 1000, "success": True}

    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ Error after {elapsed*1000:.0f}ms: {e}")
        return {"label": label, "rows": 0, "time_ms": elapsed * 1000, "success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="DuckDB local queries on FSxN S3 AP")
    parser.add_argument("--ap-alias", default=None, help="S3 AP alias")
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--output", default="tests/results/local_query_results.json")
    args = parser.parse_args()

    # Load AP alias from params.json if not provided
    ap_alias = args.ap_alias
    if not ap_alias:
        params_file = Path(__file__).parent.parent / "params.json"
        if params_file.exists():
            with open(params_file) as f:
                params = json.load(f)
            ap_alias = params.get("S3AccessPointAlias")

    if not ap_alias:
        print("❌ S3 AP alias required. Use --ap-alias or set in params.json")
        return

    print("=" * 60)
    print("FSxN DuckDB Integration — Local Query Verification")
    print("=" * 60)
    print(f"S3 AP Alias: {ap_alias}")
    print(f"Region:      {args.region}")

    # Get credentials and configure DuckDB
    creds = get_aws_credentials(args.region)
    conn = duckdb.connect(database=":memory:")
    configure_duckdb(conn, creds)

    base_path = f"s3://{ap_alias}"
    results = []

    # --- Query 1: List files (Parquet) ---
    results.append(run_query(conn, "Q1: List Parquet files",
        f"SELECT * FROM glob('{base_path}/transactions/**/*.parquet') LIMIT 5"
    ))

    # --- Query 2: Simple SELECT on Parquet ---
    results.append(run_query(conn, "Q2: Simple SELECT on Parquet",
        f"SELECT * FROM read_parquet('{base_path}/transactions/**/*.parquet') LIMIT 10"
    ))

    # --- Query 3: Aggregation ---
    results.append(run_query(conn, "Q3: Aggregation (GROUP BY category)",
        f"""
        SELECT category, COUNT(*) AS cnt, SUM(amount) AS total, AVG(amount) AS avg
        FROM read_parquet('{base_path}/transactions/**/*.parquet')
        GROUP BY category
        ORDER BY total DESC
        """
    ))

    # --- Query 4: CSV query ---
    results.append(run_query(conn, "Q4: CSV query (customers)",
        f"SELECT * FROM read_csv_auto('{base_path}/customers/customers.csv') LIMIT 5"
    ))

    # --- Query 5: JSON query ---
    results.append(run_query(conn, "Q5: JSON query (events)",
        f"""
        SELECT event_type, COUNT(*) AS cnt
        FROM read_json_auto('{base_path}/events/*.json')
        GROUP BY event_type
        ORDER BY cnt DESC
        """
    ))

    # --- Query 6: Window function ---
    results.append(run_query(conn, "Q6: Window function (running total)",
        f"""
        SELECT customer_id, transaction_date, amount,
               SUM(amount) OVER (PARTITION BY customer_id ORDER BY transaction_date) AS running_total
        FROM read_parquet('{base_path}/transactions/**/*.parquet')
        WHERE customer_id = (
            SELECT customer_id FROM read_parquet('{base_path}/transactions/**/*.parquet')
            LIMIT 1
        )
        LIMIT 10
        """
    ))

    # --- Query 7: JOIN across formats ---
    results.append(run_query(conn, "Q7: JOIN Parquet + CSV",
        f"""
        SELECT t.customer_id, c.country, COUNT(*) AS txn_count, SUM(t.amount) AS total
        FROM read_parquet('{base_path}/transactions/**/*.parquet') t
        JOIN read_csv_auto('{base_path}/customers/customers.csv') c
          ON t.customer_id = c.customer_id
        GROUP BY t.customer_id, c.country
        ORDER BY total DESC
        LIMIT 10
        """
    ))

    # Summary
    print("\n" + "=" * 60)
    successful = sum(1 for r in results if r["success"])
    total_time = sum(r["time_ms"] for r in results)
    print(f"Results: {successful}/{len(results)} queries succeeded")
    print(f"Total time: {total_time:.0f}ms")

    # Save results
    output_path = Path(__file__).parent.parent / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({"queries": results, "summary": {
            "successful": successful,
            "total": len(results),
            "total_time_ms": total_time,
        }}, f, indent=2)
    print(f"📊 Results saved to: {output_path}")


if __name__ == "__main__":
    main()

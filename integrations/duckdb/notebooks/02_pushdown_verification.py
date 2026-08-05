#!/usr/bin/env python3
"""
FSx for ONTAP DuckDB Integration — Predicate Pushdown Verification

Verifies that DuckDB pushes predicates down to Parquet row groups,
reducing data scanned from FSx for ONTAP S3 AP.

Usage:
    python 02_pushdown_verification.py [--ap-alias <alias>]
"""

import argparse
import json
import time
from pathlib import Path

import boto3
import duckdb


def get_credentials(region: str) -> dict:
    session = boto3.Session(region_name=region)
    creds = session.get_credentials().get_frozen_credentials()
    return {"access_key": creds.access_key, "secret_key": creds.secret_key,
            "session_token": creds.token, "region": region}


def setup_conn(region: str) -> duckdb.DuckDBPyConnection:
    creds = get_credentials(region)
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute(f"SET s3_region='{creds['region']}';")
    conn.execute(f"SET s3_access_key_id='{creds['access_key']}';")
    conn.execute(f"SET s3_secret_access_key='{creds['secret_key']}';")
    if creds["session_token"]:
        conn.execute(f"SET s3_session_token='{creds['session_token']}';")
    conn.execute("SET s3_url_style='path';")
    return conn


def timed_query(conn, label, query):
    print(f"\n▶ {label}")
    start = time.time()
    result = conn.execute(query).fetchall()
    elapsed = (time.time() - start) * 1000
    print(f"  Rows: {len(result)}, Time: {elapsed:.0f}ms")
    return {"label": label, "rows": len(result), "time_ms": elapsed}


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
    print("DuckDB Predicate Pushdown Verification")
    print("=" * 60)

    conn = setup_conn(args.region)
    base = f"s3://{ap_alias}/transactions/**/*.parquet"
    results = []

    # Full scan (no predicate)
    results.append(timed_query(conn, "Full scan (no filter)",
        f"SELECT COUNT(*) FROM read_parquet('{base}')"))

    # Predicate pushdown: filter on amount
    results.append(timed_query(conn, "Predicate pushdown: amount > 4000",
        f"SELECT COUNT(*) FROM read_parquet('{base}') WHERE amount > 4000"))

    # Predicate pushdown: filter on status
    results.append(timed_query(conn, "Predicate pushdown: status = 'cancelled'",
        f"SELECT COUNT(*) FROM read_parquet('{base}') WHERE status = 'cancelled'"))

    # Projection pushdown: select only 2 columns
    results.append(timed_query(conn, "Projection pushdown: 2 columns only",
        f"SELECT customer_id, amount FROM read_parquet('{base}') LIMIT 1000"))

    # Full projection (all columns)
    results.append(timed_query(conn, "Full projection: all columns",
        f"SELECT * FROM read_parquet('{base}') LIMIT 1000"))

    # EXPLAIN to verify pushdown
    print("\n▶ EXPLAIN (predicate pushdown verification)")
    explain = conn.execute(
        f"EXPLAIN SELECT COUNT(*) FROM read_parquet('{base}') WHERE amount > 4000"
    ).fetchall()
    for row in explain:
        print(f"  {row[1]}")

    # Compare times
    print("\n" + "=" * 60)
    print("Pushdown Effectiveness:")
    if len(results) >= 2:
        full_time = results[0]["time_ms"]
        filtered_time = results[1]["time_ms"]
        if full_time > 0:
            reduction = ((full_time - filtered_time) / full_time) * 100
            print(f"  Full scan:     {full_time:.0f}ms")
            print(f"  Filtered scan: {filtered_time:.0f}ms")
            print(f"  Reduction:     {reduction:.1f}%")

    output_path = Path(__file__).parent.parent / "tests/results/pushdown_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(results, open(output_path, "w"), indent=2)
    print(f"\n📊 Results: {output_path}")


if __name__ == "__main__":
    main()

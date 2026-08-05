#!/usr/bin/env python3
"""
Generate test data in multiple formats and upload to FSx for ONTAP S3 AP.

Generates Parquet, CSV, and JSON files with configurable row counts,
then uploads to the specified S3 Access Point path.

Usage:
    python3 generate-test-data.py --ap-alias <alias> --region <region> --prefix <path> [--rows 10000] [--formats parquet,csv,json]

Example:
    python3 generate-test-data.py \
        --ap-alias verification-tes-fpg5t76dgh3xchkrudk6yc4jhgzz1apn1b-ext-s3alias \
        --region ap-northeast-1 \
        --prefix bronze/sensor-data/ \
        --rows 50000 \
        --formats parquet,csv
"""

import argparse
import boto3
import io
import os
import sys
import time
import numpy as np
import pandas as pd

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False


def generate_sensor_data(rows: int, seed: int = 42) -> pd.DataFrame:
    """Generate IoT sensor data."""
    np.random.seed(seed)
    return pd.DataFrame({
        "id": range(1, rows + 1),
        "timestamp": pd.date_range("2024-01-01", periods=rows, freq="s").astype(str),
        "sensor_id": np.random.choice([f"S{i:04d}" for i in range(100)], rows),
        "temperature": np.round(np.random.normal(25, 5, rows), 2),
        "humidity": np.round(np.random.uniform(30, 90, rows), 2),
        "pressure": np.round(np.random.normal(1013, 10, rows), 2),
        "vibration": np.round(np.random.exponential(0.5, rows), 4),
        "status": np.random.choice(["normal", "warning", "critical", "maintenance"], rows, p=[0.80, 0.12, 0.03, 0.05]),
        "location": np.random.choice(["plant_a", "plant_b", "plant_c", "warehouse"], rows),
        "batch_id": np.random.randint(1000, 9999, rows),
    })


def generate_customer_data(rows: int, seed: int = 42) -> pd.DataFrame:
    """Generate customer master data."""
    np.random.seed(seed)
    return pd.DataFrame({
        "customer_id": range(1, rows + 1),
        "name": [f"Customer_{i}" for i in range(1, rows + 1)],
        "email": [f"customer{i}@example.com" for i in range(1, rows + 1)],
        "country": np.random.choice(["JP", "US", "UK", "DE", "FR"], rows),
        "segment": np.random.choice(["enterprise", "mid-market", "smb"], rows, p=[0.2, 0.3, 0.5]),
        "annual_revenue": np.round(np.random.exponential(500000, rows), 0).astype(int),
    })


def upload_parquet(s3, bucket: str, key: str, df: pd.DataFrame) -> dict:
    """Upload DataFrame as Parquet."""
    if not HAS_PYARROW:
        return {"format": "parquet", "result": "SKIP", "error": "pyarrow not installed"}
    
    start = time.time()
    buf = io.BytesIO()
    table = pa.Table.from_pandas(df)
    pq.write_table(table, buf, compression="snappy")
    buf.seek(0)
    size = buf.getbuffer().nbytes
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue())
    elapsed = time.time() - start
    return {"format": "parquet", "key": key, "size_bytes": size, "rows": len(df), "upload_seconds": round(elapsed, 2), "result": "SUCCESS"}


def upload_csv(s3, bucket: str, key: str, df: pd.DataFrame) -> dict:
    """Upload DataFrame as CSV."""
    start = time.time()
    csv_data = df.to_csv(index=False).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=csv_data)
    elapsed = time.time() - start
    return {"format": "csv", "key": key, "size_bytes": len(csv_data), "rows": len(df), "upload_seconds": round(elapsed, 2), "result": "SUCCESS"}


def upload_json(s3, bucket: str, key: str, df: pd.DataFrame) -> dict:
    """Upload DataFrame as JSON Lines."""
    start = time.time()
    json_data = df.to_json(orient="records", lines=True).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=json_data)
    elapsed = time.time() - start
    return {"format": "json", "key": key, "size_bytes": len(json_data), "rows": len(df), "upload_seconds": round(elapsed, 2), "result": "SUCCESS"}


def main():
    parser = argparse.ArgumentParser(description="Generate and upload test data to FSx for ONTAP S3 AP")
    parser.add_argument("--ap-alias", required=True, help="S3 Access Point alias")
    parser.add_argument("--region", required=True, help="AWS region")
    parser.add_argument("--prefix", default="test-data/", help="S3 key prefix")
    parser.add_argument("--rows", type=int, default=10000, help="Number of rows to generate")
    parser.add_argument("--formats", default="parquet,csv", help="Comma-separated formats: parquet,csv,json")
    parser.add_argument("--dataset", default="sensor", choices=["sensor", "customer"], help="Dataset type")
    parser.add_argument("--profile", help="AWS CLI profile name")
    args = parser.parse_args()

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    s3 = session.client("s3")
    formats = [f.strip() for f in args.formats.split(",")]

    print(f"=== Test Data Generation ===")
    print(f"AP Alias: {args.ap_alias}")
    print(f"Prefix: {args.prefix}")
    print(f"Rows: {args.rows:,}")
    print(f"Formats: {formats}")
    print(f"Dataset: {args.dataset}")
    print()

    # Generate data
    if args.dataset == "sensor":
        df = generate_sensor_data(args.rows)
    else:
        df = generate_customer_data(args.rows)

    print(f"Generated {len(df):,} rows, {len(df.columns)} columns")
    print()

    # Upload in each format
    results = []
    for fmt in formats:
        key = f"{args.prefix}{args.dataset}_data.{fmt}"
        if fmt == "parquet":
            r = upload_parquet(s3, args.ap_alias, key, df)
        elif fmt == "csv":
            r = upload_csv(s3, args.ap_alias, key, df)
        elif fmt == "json":
            r = upload_json(s3, args.ap_alias, key, df)
        else:
            r = {"format": fmt, "result": "SKIP", "error": f"Unknown format: {fmt}"}
        
        results.append(r)
        status = r["result"]
        size = r.get("size_bytes", 0)
        elapsed = r.get("upload_seconds", 0)
        print(f"[{status}] {fmt}: {key} ({size:,} bytes, {elapsed}s)")

    print(f"\n=== Done: {sum(1 for r in results if r['result'] == 'SUCCESS')}/{len(results)} uploaded ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

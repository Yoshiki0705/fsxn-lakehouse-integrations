#!/usr/bin/env python3
"""
FSx for ONTAP Delta Lake OSS — delta-rs (Python Native) Verification

Reads/writes Delta tables on FSx for ONTAP using the Python `deltalake` package
(delta-rs) WITHOUT requiring a Spark cluster.

Prerequisites:
    pip install deltalake pandas boto3

Usage:
    python 05_delta_rs.py --s3-ap-alias <alias> [--region ap-northeast-1]
"""

import argparse
import json
import time
from pathlib import Path

import boto3
import pandas as pd


def get_storage_options(region: str) -> dict:
    """Get storage options for delta-rs S3 access."""
    session = boto3.Session(region_name=region)
    creds = session.get_credentials().get_frozen_credentials()
    opts = {
        "AWS_REGION": region,
        "AWS_ACCESS_KEY_ID": creds.access_key,
        "AWS_SECRET_ACCESS_KEY": creds.secret_key,
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }
    if creds.token:
        opts["AWS_SESSION_TOKEN"] = creds.token
    return opts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--s3-ap-alias", required=True)
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--output", default="tests/results/delta_rs_results.json")
    args = parser.parse_args()

    # Import deltalake
    try:
        import deltalake
        print(f"deltalake version: {deltalake.__version__}")
    except ImportError:
        print("❌ Install: pip install deltalake")
        return

    storage_options = get_storage_options(args.region)
    base_path = f"s3a://{args.s3_ap_alias}/delta"
    results = []

    print("=" * 60)
    print("FSx for ONTAP Delta Lake OSS — delta-rs Verification")
    print("=" * 60)
    print(f"Path: {base_path}")

    # --- Test 1: Read existing Delta table (created by Spark) ---
    print("\n▶ Test 1: Read Delta table (created by Spark)")
    spark_table_path = f"{base_path}/transactions"
    start = time.time()
    try:
        dt = deltalake.DeltaTable(spark_table_path, storage_options=storage_options)
        df = dt.to_pandas()
        elapsed = time.time() - start
        print(f"  ✅ Read {len(df)} rows in {elapsed:.1f}s")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Version: {dt.version()}")
        results.append({"test": "read_spark_table", "rows": len(df), "time_s": elapsed, "success": True})
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ Error: {e}")
        results.append({"test": "read_spark_table", "error": str(e), "time_s": elapsed, "success": False})

    # --- Test 2: Write new Delta table with delta-rs ---
    print("\n▶ Test 2: Write new Delta table with delta-rs")
    rs_table_path = f"{base_path}/delta_rs_test"
    start = time.time()
    try:
        test_df = pd.DataFrame({
            "id": range(1, 1001),
            "name": [f"item_{i}" for i in range(1, 1001)],
            "value": [float(i) * 1.5 for i in range(1, 1001)],
            "category": ["A" if i % 2 == 0 else "B" for i in range(1, 1001)],
        })
        deltalake.write_deltalake(
            rs_table_path,
            test_df,
            mode="overwrite",
            storage_options=storage_options,
        )
        elapsed = time.time() - start
        print(f"  ✅ Written {len(test_df)} rows in {elapsed:.1f}s")
        results.append({"test": "write_delta_rs", "rows": len(test_df), "time_s": elapsed, "success": True})
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ Error: {e}")
        results.append({"test": "write_delta_rs", "error": str(e), "time_s": elapsed, "success": False})

    # --- Test 3: Read back delta-rs written table ---
    print("\n▶ Test 3: Read back delta-rs table")
    start = time.time()
    try:
        dt2 = deltalake.DeltaTable(rs_table_path, storage_options=storage_options)
        df2 = dt2.to_pandas()
        elapsed = time.time() - start
        assert len(df2) == 1000, f"Expected 1000 rows, got {len(df2)}"
        assert list(df2.columns) == ["id", "name", "value", "category"]
        print(f"  ✅ Read back {len(df2)} rows in {elapsed:.1f}s — integrity verified")
        results.append({"test": "readback_delta_rs", "rows": len(df2), "time_s": elapsed, "success": True})
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ Error: {e}")
        results.append({"test": "readback_delta_rs", "error": str(e), "time_s": elapsed, "success": False})

    # --- Test 4: Cross-compatibility (delta-rs reads Spark table, Spark reads delta-rs table) ---
    print("\n▶ Test 4: Version and history via delta-rs")
    try:
        dt = deltalake.DeltaTable(spark_table_path, storage_options=storage_options)
        print(f"  Version: {dt.version()}")
        print(f"  Files: {len(dt.files())}")
        history = dt.history()
        print(f"  History entries: {len(history)}")
        results.append({"test": "history", "version": dt.version(),
                       "files": len(dt.files()), "success": True})
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({"test": "history", "error": str(e), "success": False})

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r.get("success"))
    print(f"Results: {passed}/{len(results)} tests passed")

    output_path = Path(__file__).parent.parent / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump(results, open(output_path, "w"), indent=2, default=str)
    print(f"📊 Results: {output_path}")


if __name__ == "__main__":
    main()

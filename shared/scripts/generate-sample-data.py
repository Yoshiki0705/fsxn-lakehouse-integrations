#!/usr/bin/env python3
"""
generate-sample-data.py - Generate sample structured and unstructured data.

Creates sample datasets for testing FSxN Lakehouse integrations:
- Structured: Parquet, CSV, JSON (transactions, IoT sensors, customers)
- Unstructured: Sample images (generated), text documents

Usage:
    python generate-sample-data.py --output-dir ./sample-output
    python generate-sample-data.py --s3-ap-alias <alias> --region ap-northeast-1
"""

import argparse
import json
import os
import random
import string
import sys
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    print("ERROR: Required packages not installed.")
    print("  pip install pandas pyarrow")
    sys.exit(1)


def generate_transactions(n_rows: int = 10000) -> pd.DataFrame:
    """Generate sample financial transaction data."""
    random.seed(42)
    return pd.DataFrame(
        {
            "transaction_id": [f"TXN-{i:08d}" for i in range(n_rows)],
            "timestamp": [
                datetime(2024, 1, 1) + timedelta(seconds=random.randint(0, 31536000))
                for _ in range(n_rows)
            ],
            "account_id": [f"ACC-{random.randint(1000, 9999)}" for _ in range(n_rows)],
            "amount": [round(random.uniform(1.0, 10000.0), 2) for _ in range(n_rows)],
            "currency": [
                random.choice(["USD", "EUR", "JPY", "GBP"]) for _ in range(n_rows)
            ],
            "category": [
                random.choice(["payment", "transfer", "withdrawal", "deposit"])
                for _ in range(n_rows)
            ],
            "status": [
                random.choice(["completed", "pending", "failed"]) for _ in range(n_rows)
            ],
        }
    )


def generate_iot_sensors(n_rows: int = 10000) -> pd.DataFrame:
    """Generate sample IoT sensor data."""
    random.seed(43)
    return pd.DataFrame(
        {
            "sensor_id": [
                f"SENSOR-{random.randint(1, 100):03d}" for _ in range(n_rows)
            ],
            "timestamp": [
                datetime(2024, 1, 1) + timedelta(seconds=random.randint(0, 31536000))
                for _ in range(n_rows)
            ],
            "temperature": [
                round(random.uniform(-10.0, 50.0), 2) for _ in range(n_rows)
            ],
            "humidity": [
                round(random.uniform(0.0, 100.0), 2) for _ in range(n_rows)
            ],
            "pressure": [
                round(random.uniform(900.0, 1100.0), 2) for _ in range(n_rows)
            ],
            "vibration": [
                round(random.uniform(0.0, 10.0), 4) for _ in range(n_rows)
            ],
            "location": [
                random.choice(["plant-A", "plant-B", "plant-C"]) for _ in range(n_rows)
            ],
        }
    )


def generate_customers(n_rows: int = 1000) -> pd.DataFrame:
    """Generate sample customer data."""
    random.seed(44)
    countries = ["US", "JP", "DE", "GB", "FR", "CA", "AU", "SG"]
    return pd.DataFrame(
        {
            "customer_id": [f"CUST-{i:04d}" for i in range(n_rows)],
            "name": [f"Customer {i}" for i in range(n_rows)],
            "email": [f"customer{i}@example.com" for i in range(n_rows)],
            "country": [random.choice(countries) for _ in range(n_rows)],
            "created_at": [
                datetime(2020, 1, 1) + timedelta(days=random.randint(0, 1500))
                for _ in range(n_rows)
            ],
        }
    )


def generate_events(n_rows: int = 5000) -> list[dict]:
    """Generate sample event data (JSON lines)."""
    random.seed(45)
    event_types = ["page_view", "click", "purchase", "signup", "logout"]
    events = []
    for i in range(n_rows):
        events.append(
            {
                "event_id": f"EVT-{i:08d}",
                "event_type": random.choice(event_types),
                "timestamp": (
                    datetime(2024, 1, 1) + timedelta(seconds=random.randint(0, 31536000))
                ).isoformat(),
                "user_id": f"USER-{random.randint(1, 500):04d}",
                "payload": {
                    "page": f"/page/{random.randint(1, 100)}",
                    "duration_ms": random.randint(100, 30000),
                    "device": random.choice(["mobile", "desktop", "tablet"]),
                },
            }
        )
    return events


def generate_sample_documents(output_dir: Path) -> None:
    """Generate sample text documents (simulating PDF/DOCX content)."""
    docs_dir = output_dir / "media" / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Generate sample text files (representing document content)
    topics = [
        ("quarterly_report_2024_Q1", "Quarterly Financial Report Q1 2024"),
        ("product_specification_v2", "Product Specification Document v2.0"),
        ("compliance_audit_2024", "Annual Compliance Audit Report 2024"),
        ("architecture_design_doc", "System Architecture Design Document"),
        ("user_manual_v3", "User Manual Version 3.0"),
    ]

    for filename, title in topics:
        content = f"""# {title}

## Executive Summary

This document provides a comprehensive overview of {title.lower()}.
Generated as sample data for FSxN Lakehouse Integration testing.

## Section 1: Overview

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo.

## Section 2: Details

Key metrics and findings are summarized below:
- Metric A: {random.randint(100, 999)}
- Metric B: {random.uniform(0.5, 0.99):.2%}
- Metric C: ${random.randint(10000, 999999):,}

## Section 3: Recommendations

Based on the analysis, we recommend the following actions:
1. Action item one with detailed description
2. Action item two with implementation timeline
3. Action item three with resource requirements

## Appendix

Generated: {datetime.now().isoformat()}
Document ID: DOC-{random.randint(10000, 99999)}
"""
        filepath = docs_dir / f"{filename}.txt"
        filepath.write_text(content)

    print(f"  Generated {len(topics)} sample documents in {docs_dir}")


def write_local(output_dir: Path, datasets: dict) -> None:
    """Write datasets to local filesystem."""
    # Structured data
    bronze_dir = output_dir / "bronze"

    # Transactions (Parquet)
    txn_dir = bronze_dir / "transactions"
    txn_dir.mkdir(parents=True, exist_ok=True)
    datasets["transactions"].to_parquet(txn_dir / "transactions.parquet", index=False)
    print(f"  Written: {txn_dir}/transactions.parquet ({len(datasets['transactions'])} rows)")

    # IoT Sensors (Parquet, partitioned by location)
    iot_dir = bronze_dir / "iot-sensors"
    iot_dir.mkdir(parents=True, exist_ok=True)
    for location, group in datasets["iot_sensors"].groupby("location"):
        part_dir = iot_dir / f"location={location}"
        part_dir.mkdir(parents=True, exist_ok=True)
        group.to_parquet(part_dir / "data.parquet", index=False)
    print(f"  Written: {iot_dir}/ (partitioned, {len(datasets['iot_sensors'])} rows)")

    # Customers (CSV)
    cust_dir = bronze_dir / "customers"
    cust_dir.mkdir(parents=True, exist_ok=True)
    datasets["customers"].to_csv(cust_dir / "customers.csv", index=False)
    print(f"  Written: {cust_dir}/customers.csv ({len(datasets['customers'])} rows)")

    # Events (JSON lines)
    events_dir = bronze_dir / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    with open(events_dir / "events.jsonl", "w") as f:
        for event in datasets["events"]:
            f.write(json.dumps(event) + "\n")
    print(f"  Written: {events_dir}/events.jsonl ({len(datasets['events'])} events)")

    # Unstructured data
    generate_sample_documents(output_dir)

    # Generate placeholder images (1x1 pixel PNGs as placeholders)
    images_dir = output_dir / "media" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    for i in range(10):
        # Create minimal valid PNG (1x1 pixel)
        # In real usage, copy actual images to FSxN via NFS
        placeholder = images_dir / f"sample_image_{i:03d}.txt"
        placeholder.write_text(
            f"Placeholder for sample_image_{i:03d}.jpg\n"
            f"In production, upload real images via NFS/SMB.\n"
            f"Size: {random.randint(100, 5000)}KB\n"
            f"Dimensions: {random.choice(['1920x1080', '3840x2160', '1280x720'])}\n"
        )
    print(f"  Generated: {images_dir}/ (10 image placeholders)")


def main():
    parser = argparse.ArgumentParser(description="Generate sample data for FSxN Lakehouse")
    parser.add_argument(
        "--output-dir",
        default="./sample-output",
        help="Local output directory (default: ./sample-output)",
    )
    parser.add_argument("--rows", type=int, default=10000, help="Number of rows per dataset")
    parser.add_argument(
        "--s3-ap-alias", help="S3 AP alias (if writing directly to FSxN)"
    )
    parser.add_argument("--region", default="ap-northeast-1", help="AWS region")
    args = parser.parse_args()

    print("=" * 60)
    print("FSxN Lakehouse - Sample Data Generator")
    print("=" * 60)
    print(f"  Rows per dataset: {args.rows}")
    print(f"  Output: {args.output_dir}")
    print()

    # Generate datasets
    print("Generating datasets...")
    datasets = {
        "transactions": generate_transactions(args.rows),
        "iot_sensors": generate_iot_sensors(args.rows),
        "customers": generate_customers(min(args.rows, 1000)),
        "events": generate_events(args.rows // 2),
    }

    # Write to local filesystem
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nWriting to: {output_dir}")
    write_local(output_dir, datasets)

    # If S3 AP alias provided, also upload
    if args.s3_ap_alias:
        print(f"\nUploading to S3 AP: {args.s3_ap_alias}")
        print("  (Use 'aws s3 sync' or rsync via NFS for production uploads)")
        print(f"  aws s3 sync {output_dir} s3://{args.s3_ap_alias}/ --region {args.region}")

    print("\n" + "=" * 60)
    print("✅ Sample data generation complete!")
    print("=" * 60)
    print(f"\nTo upload to FSxN via NFS:")
    print(f"  cp -r {output_dir}/* /mnt/fsxn/<volume>/")
    print(f"\nTo upload via S3 AP:")
    print(f"  aws s3 sync {output_dir} s3://<s3ap-alias>/ --region {args.region}")


if __name__ == "__main__":
    main()

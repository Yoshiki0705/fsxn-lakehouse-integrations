#!/usr/bin/env python3
"""
FSx for ONTAP Glue Integration — Sample Data Generator

Generates sample datasets for Glue ETL verification in medallion architecture:
  - bronze/transactions: 500k rows, Parquet, partitioned by year/month
  - bronze/customers: 50k rows, CSV
  - bronze/events: 100k rows, JSON Lines

Output: Local directory structure ready for upload to FSx for ONTAP via NFS.

Usage:
    python generate_sample_data.py [--output-dir ./sample_data] [--scale 1.0]
"""

import argparse
import json
import os
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def generate_transactions(output_dir: Path, num_rows: int = 500_000) -> None:
    """Generate partitioned Parquet transactions dataset."""
    print(f"  Generating bronze/transactions ({num_rows:,} rows)...")

    categories = ["electronics", "clothing", "food", "travel", "entertainment",
                  "healthcare", "education", "utilities", "automotive", "home"]
    statuses = ["completed", "pending", "cancelled", "refunded"]
    currencies = ["USD", "JPY", "EUR", "GBP"]
    merchants = [f"MERCHANT-{i:04d}" for i in range(200)]

    # Generate data in chunks to manage memory
    chunk_size = 50_000
    for chunk_start in range(0, num_rows, chunk_size):
        chunk_end = min(chunk_start + chunk_size, num_rows)
        chunk_rows = chunk_end - chunk_start

        # Random dates across 2024
        base_date = datetime(2024, 1, 1)
        dates = [base_date + timedelta(days=random.randint(0, 364),
                                        hours=random.randint(0, 23),
                                        minutes=random.randint(0, 59))
                 for _ in range(chunk_rows)]

        data = {
            "id": list(range(chunk_start + 1, chunk_end + 1)),
            "transaction_date": dates,
            "customer_id": [f"CUST-{random.randint(1, 50000):05d}" for _ in range(chunk_rows)],
            "amount": [round(random.uniform(1.0, 5000.0), 2) for _ in range(chunk_rows)],
            "currency": [random.choice(currencies) for _ in range(chunk_rows)],
            "status": [random.choices(statuses, weights=[70, 15, 10, 5])[0] for _ in range(chunk_rows)],
            "category": [random.choice(categories) for _ in range(chunk_rows)],
            "merchant": [random.choice(merchants) for _ in range(chunk_rows)],
        }

        df = pd.DataFrame(data)
        df["year"] = df["transaction_date"].dt.year
        df["month"] = df["transaction_date"].dt.month

        # Write partitioned Parquet
        for (year, month), group in df.groupby(["year", "month"]):
            partition_dir = output_dir / "bronze" / "transactions" / f"year={year}" / f"month={month}"
            partition_dir.mkdir(parents=True, exist_ok=True)
            file_path = partition_dir / f"part-{chunk_start:08d}.snappy.parquet"
            group.drop(columns=["year", "month"]).to_parquet(
                file_path, engine="pyarrow", compression="snappy", index=False
            )

    print(f"  ✅ bronze/transactions: {num_rows:,} rows written (partitioned by year/month)")


def generate_customers(output_dir: Path, num_rows: int = 50_000) -> None:
    """Generate CSV customers dataset."""
    print(f"  Generating bronze/customers ({num_rows:,} rows)...")

    countries = ["US", "JP", "UK", "DE", "FR", "CA", "AU", "BR", "IN", "KR"]
    segments = ["enterprise", "mid-market", "small-business", "consumer"]

    data = {
        "customer_id": [f"CUST-{i:05d}" for i in range(1, num_rows + 1)],
        "name": [f"Customer {i}" for i in range(1, num_rows + 1)],
        "email": [f"customer{i}@example.com" for i in range(1, num_rows + 1)],
        "country": [random.choice(countries) for _ in range(num_rows)],
        "segment": [random.choice(segments) for _ in range(num_rows)],
        "created_at": [
            (datetime(2020, 1, 1) + timedelta(days=random.randint(0, 1460))).isoformat()
            for _ in range(num_rows)
        ],
    }

    df = pd.DataFrame(data)
    customers_dir = output_dir / "bronze" / "customers"
    customers_dir.mkdir(parents=True, exist_ok=True)
    df.to_csv(customers_dir / "customers.csv", index=False)

    print(f"  ✅ bronze/customers: {num_rows:,} rows written (CSV)")


def generate_events(output_dir: Path, num_rows: int = 100_000) -> None:
    """Generate JSON events dataset."""
    print(f"  Generating bronze/events ({num_rows:,} rows)...")

    event_types = ["page_view", "click", "purchase", "signup", "logout",
                   "search", "add_to_cart", "remove_from_cart", "checkout"]

    events_dir = output_dir / "bronze" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)

    # Write in chunks (JSON Lines format)
    chunk_size = 10_000
    for chunk_idx, chunk_start in enumerate(range(0, num_rows, chunk_size)):
        chunk_end = min(chunk_start + chunk_size, num_rows)
        records = []

        for i in range(chunk_start, chunk_end):
            event_date = datetime(2024, 1, 1) + timedelta(
                days=random.randint(0, 364),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59)
            )
            record = {
                "event_id": f"EVT-{i+1:08d}",
                "event_type": random.choice(event_types),
                "timestamp": event_date.isoformat(),
                "user_id": f"USER-{random.randint(1, 10000):05d}",
                "payload": json.dumps({
                    "page": f"/page/{random.randint(1, 100)}",
                    "duration_ms": random.randint(100, 30000),
                    "referrer": random.choice(["google", "direct", "social", "email"]),
                }),
                "source": random.choice(["web", "mobile_ios", "mobile_android", "api"]),
            }
            records.append(json.dumps(record))

        file_path = events_dir / f"events_{chunk_idx:04d}.json"
        with open(file_path, "w") as f:
            f.write("\n".join(records))

    print(f"  ✅ bronze/events: {num_rows:,} rows written (JSON Lines)")


def main():
    parser = argparse.ArgumentParser(description="Generate sample data for Glue ETL verification")
    parser.add_argument("--output-dir", type=str, default="./sample_data",
                        help="Output directory for generated data")
    parser.add_argument("--scale", type=float, default=1.0,
                        help="Scale factor (1.0 = default sizes)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    scale = args.scale

    print("=" * 60)
    print("FSx for ONTAP Glue Integration — Sample Data Generator")
    print("=" * 60)
    print(f"Output directory: {output_dir.absolute()}")
    print(f"Scale factor: {scale}")
    print(f"Structure: bronze/{{transactions,customers,events}}")
    print()

    generate_transactions(output_dir, int(500_000 * scale))
    generate_customers(output_dir, int(50_000 * scale))
    generate_events(output_dir, int(100_000 * scale))

    # Summary
    total_size = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
    print()
    print(f"📊 Total data generated: {total_size / (1024*1024):.1f} MB")
    print(f"📁 Output directory: {output_dir.absolute()}")
    print()
    print("Next step: Upload to FSx for ONTAP via NFS mount")
    print("  rsync -avz ./sample_data/bronze/ /mnt/fsxn/bronze/")


if __name__ == "__main__":
    main()

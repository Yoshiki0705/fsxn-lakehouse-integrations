#!/usr/bin/env python3
"""
generate-sample-data.py - Generate sample structured data for FSx for ONTAP Lakehouse integrations.

Creates datasets for testing Snowflake External Tables and Iceberg Tables:
- bronze/transactions/  — Parquet (50k rows): transaction_id, timestamp, amount, category, merchant, customer_id
- bronze/iot-sensors/   — Parquet partitioned by date (50k rows): sensor_id, timestamp, temperature, humidity, pressure, location
- silver/customers/     — CSV (50k rows): customer_id, name, email, country, segment, created_at
- bronze/events/        — NDJSON (50k rows): event_id, event_type, timestamp, user_id, payload
- silver/products/      — Parquet (50k rows): product_id, name, category, price, stock_qty, supplier, updated_at

Usage:
    python generate-sample-data.py --output-dir ./sample-output
    python generate-sample-data.py --output-dir ./sample-output --rows 50000 --format all
    python generate-sample-data.py --output-dir /mnt/fsxn/vol1 --rows 100000
"""

import argparse
import json
import os
import random
import string
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    print("ERROR: Required packages not installed.")
    print("  pip install pandas pyarrow")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Data generation functions
# ---------------------------------------------------------------------------

CATEGORIES = [
    "electronics", "groceries", "dining", "travel", "entertainment",
    "healthcare", "clothing", "utilities", "education", "automotive",
]

MERCHANTS = [
    "Amazon", "Walmart", "Starbucks", "Shell", "Netflix",
    "Uber", "Apple Store", "Target", "Costco", "Whole Foods",
    "7-Eleven", "McDonald's", "Delta Airlines", "Hilton Hotels", "Nike",
    "Best Buy", "Home Depot", "Spotify", "Airbnb", "DoorDash",
]

COUNTRIES = ["US", "JP", "DE", "GB", "FR", "CA", "AU", "SG", "KR", "BR"]

SEGMENTS = ["enterprise", "mid-market", "small-business", "individual", "government"]

PRODUCT_CATEGORIES = [
    "compute", "storage", "networking", "security", "database",
    "analytics", "ai-ml", "iot", "devtools", "monitoring",
]

SUPPLIERS = [
    "Supplier-Alpha", "Supplier-Beta", "Supplier-Gamma",
    "Supplier-Delta", "Supplier-Epsilon", "Supplier-Zeta",
    "Supplier-Eta", "Supplier-Theta", "Supplier-Iota", "Supplier-Kappa",
]

EVENT_TYPES = ["page_view", "click", "purchase", "signup", "logout", "search", "add_to_cart"]

DEVICES = ["mobile", "desktop", "tablet"]

LOCATIONS = ["plant-A", "plant-B", "plant-C", "warehouse-1", "warehouse-2", "office-HQ"]


def generate_transactions(n_rows: int) -> pd.DataFrame:
    """Generate financial transaction data for bronze/transactions/ (Parquet)."""
    random.seed(42)
    base_date = datetime(2024, 1, 1)
    max_offset = 365 * 24 * 3600  # 1 year in seconds

    data = {
        "transaction_id": [f"TXN-{i:08d}" for i in range(n_rows)],
        "timestamp": [
            base_date + timedelta(seconds=random.randint(0, max_offset))
            for _ in range(n_rows)
        ],
        "amount": [round(random.uniform(0.50, 15000.00), 2) for _ in range(n_rows)],
        "category": [random.choice(CATEGORIES) for _ in range(n_rows)],
        "merchant": [random.choice(MERCHANTS) for _ in range(n_rows)],
        "customer_id": [f"CUST-{random.randint(1, 10000):05d}" for _ in range(n_rows)],
    }
    return pd.DataFrame(data)


def generate_iot_sensors(n_rows: int) -> pd.DataFrame:
    """Generate IoT sensor data for bronze/iot-sensors/ (Parquet, partitioned by date)."""
    random.seed(43)
    base_date = datetime(2024, 1, 1)
    # Spread across 90 days for meaningful date partitions
    max_offset = 90 * 24 * 3600

    timestamps = [
        base_date + timedelta(seconds=random.randint(0, max_offset))
        for _ in range(n_rows)
    ]

    data = {
        "sensor_id": [f"SENSOR-{random.randint(1, 200):04d}" for _ in range(n_rows)],
        "timestamp": timestamps,
        "temperature": [round(random.uniform(-20.0, 55.0), 2) for _ in range(n_rows)],
        "humidity": [round(random.uniform(10.0, 95.0), 2) for _ in range(n_rows)],
        "pressure": [round(random.uniform(950.0, 1050.0), 2) for _ in range(n_rows)],
        "location": [random.choice(LOCATIONS) for _ in range(n_rows)],
        # Partition column derived from timestamp
        "date": [ts.strftime("%Y-%m-%d") for ts in timestamps],
    }
    return pd.DataFrame(data)


def generate_customers(n_rows: int) -> pd.DataFrame:
    """Generate customer data for silver/customers/ (CSV)."""
    random.seed(44)
    base_date = datetime(2020, 1, 1)
    max_days = 1600

    first_names = [
        "James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael",
        "Linda", "David", "Elizabeth", "Taro", "Hanako", "Yuki", "Kenji",
        "Akiko", "Hiroshi", "Sakura", "Takeshi", "Mika", "Satoshi",
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
        "Davis", "Rodriguez", "Martinez", "Tanaka", "Suzuki", "Sato", "Yamamoto",
        "Watanabe", "Nakamura", "Kobayashi", "Ito", "Kimura", "Hayashi",
    ]

    data = {
        "customer_id": [f"CUST-{i:05d}" for i in range(1, n_rows + 1)],
        "name": [
            f"{random.choice(first_names)} {random.choice(last_names)}"
            for _ in range(n_rows)
        ],
        "email": [
            f"user{i}@{'example' if i % 3 == 0 else random.choice(['gmail', 'yahoo', 'outlook'])}.com"
            for i in range(n_rows)
        ],
        "country": [random.choice(COUNTRIES) for _ in range(n_rows)],
        "segment": [random.choice(SEGMENTS) for _ in range(n_rows)],
        "created_at": [
            (base_date + timedelta(days=random.randint(0, max_days))).strftime("%Y-%m-%d")
            for _ in range(n_rows)
        ],
    }
    return pd.DataFrame(data)


def generate_events(n_rows: int) -> list[dict]:
    """Generate event data for bronze/events/ (NDJSON)."""
    random.seed(45)
    base_date = datetime(2024, 1, 1)
    max_offset = 365 * 24 * 3600

    events = []
    for i in range(n_rows):
        ts = base_date + timedelta(seconds=random.randint(0, max_offset))
        events.append({
            "event_id": f"EVT-{i:08d}",
            "event_type": random.choice(EVENT_TYPES),
            "timestamp": ts.isoformat(),
            "user_id": f"USER-{random.randint(1, 5000):05d}",
            "payload": {
                "page": f"/page/{random.randint(1, 200)}",
                "duration_ms": random.randint(50, 60000),
                "device": random.choice(DEVICES),
                "referrer": random.choice(["google", "direct", "social", "email", "ads"]),
            },
        })
    return events


def generate_products(n_rows: int) -> pd.DataFrame:
    """Generate product data for silver/products/ (Parquet, used by Iceberg table)."""
    random.seed(46)
    base_date = datetime(2023, 6, 1)
    max_days = 500

    adjectives = [
        "Advanced", "Pro", "Enterprise", "Standard", "Premium",
        "Basic", "Ultra", "Lite", "Max", "Core",
    ]
    nouns = [
        "Gateway", "Controller", "Module", "Engine", "Platform",
        "Service", "Agent", "Connector", "Hub", "Processor",
    ]

    data = {
        "product_id": [f"PROD-{i:06d}" for i in range(1, n_rows + 1)],
        "name": [
            f"{random.choice(adjectives)} {random.choice(nouns)} {random.choice(PRODUCT_CATEGORIES).title()}"
            for _ in range(n_rows)
        ],
        "category": [random.choice(PRODUCT_CATEGORIES) for _ in range(n_rows)],
        "price": [round(random.uniform(9.99, 9999.99), 2) for _ in range(n_rows)],
        "stock_qty": [random.randint(0, 10000) for _ in range(n_rows)],
        "supplier": [random.choice(SUPPLIERS) for _ in range(n_rows)],
        "updated_at": [
            (base_date + timedelta(days=random.randint(0, max_days))).strftime("%Y-%m-%dT%H:%M:%S")
            for _ in range(n_rows)
        ],
    }
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_transactions(df: pd.DataFrame, output_dir: Path) -> None:
    """Write transactions as Parquet to bronze/transactions/."""
    dest = output_dir / "bronze" / "transactions"
    dest.mkdir(parents=True, exist_ok=True)
    filepath = dest / "transactions.parquet"
    df.to_parquet(filepath, index=False, engine="pyarrow")
    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"  ✓ bronze/transactions/transactions.parquet ({len(df):,} rows, {size_mb:.1f} MB)")


def write_iot_sensors(df: pd.DataFrame, output_dir: Path) -> None:
    """Write IoT sensors as Parquet partitioned by date to bronze/iot-sensors/."""
    dest = output_dir / "bronze" / "iot-sensors"
    dest.mkdir(parents=True, exist_ok=True)

    partition_count = 0
    for date_val, group in df.groupby("date"):
        part_dir = dest / f"date={date_val}"
        part_dir.mkdir(parents=True, exist_ok=True)
        # Drop the partition column from the data file
        group_data = group.drop(columns=["date"])
        group_data.to_parquet(part_dir / "data.parquet", index=False, engine="pyarrow")
        partition_count += 1

    print(f"  ✓ bronze/iot-sensors/ ({len(df):,} rows, {partition_count} date partitions)")


def write_customers(df: pd.DataFrame, output_dir: Path) -> None:
    """Write customers as CSV to silver/customers/."""
    dest = output_dir / "silver" / "customers"
    dest.mkdir(parents=True, exist_ok=True)
    filepath = dest / "customers.csv"
    df.to_csv(filepath, index=False)
    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"  ✓ silver/customers/customers.csv ({len(df):,} rows, {size_mb:.1f} MB)")


def write_events(events: list[dict], output_dir: Path) -> None:
    """Write events as NDJSON to bronze/events/."""
    dest = output_dir / "bronze" / "events"
    dest.mkdir(parents=True, exist_ok=True)
    filepath = dest / "events.ndjson"
    with open(filepath, "w") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"  ✓ bronze/events/events.ndjson ({len(events):,} rows, {size_mb:.1f} MB)")


def write_products(df: pd.DataFrame, output_dir: Path) -> None:
    """Write products as Parquet to silver/products/."""
    dest = output_dir / "silver" / "products"
    dest.mkdir(parents=True, exist_ok=True)
    filepath = dest / "products.parquet"
    df.to_parquet(filepath, index=False, engine="pyarrow")
    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"  ✓ silver/products/products.parquet ({len(df):,} rows, {size_mb:.1f} MB)")


# ---------------------------------------------------------------------------
# S3 upload helper
# ---------------------------------------------------------------------------

def upload_to_s3(output_dir: Path, s3_ap_alias: str, region: str) -> None:
    """Print aws s3 sync commands for uploading to FSx for ONTAP via S3 Access Point."""
    print(f"\n{'─' * 60}")
    print("S3 Access Point Upload Commands")
    print(f"{'─' * 60}")
    print(f"\n# Sync all data to FSx for ONTAP via S3 Access Point:")
    print(f"aws s3 sync {output_dir}/bronze s3://{s3_ap_alias}/bronze/ --region {region}")
    print(f"aws s3 sync {output_dir}/silver s3://{s3_ap_alias}/silver/ --region {region}")
    print(f"\n# Or upload individual datasets:")
    print(f"aws s3 cp {output_dir}/bronze/transactions/transactions.parquet \\")
    print(f"    s3://{s3_ap_alias}/bronze/transactions/transactions.parquet --region {region}")
    print(f"aws s3 sync {output_dir}/bronze/iot-sensors/ \\")
    print(f"    s3://{s3_ap_alias}/bronze/iot-sensors/ --region {region}")
    print(f"aws s3 cp {output_dir}/silver/customers/customers.csv \\")
    print(f"    s3://{s3_ap_alias}/silver/customers/customers.csv --region {region}")
    print(f"aws s3 cp {output_dir}/bronze/events/events.ndjson \\")
    print(f"    s3://{s3_ap_alias}/bronze/events/events.ndjson --region {region}")
    print(f"aws s3 cp {output_dir}/silver/products/products.parquet \\")
    print(f"    s3://{s3_ap_alias}/silver/products/products.parquet --region {region}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate sample structured data for FSx for ONTAP Lakehouse integrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --output-dir ./sample-output
  %(prog)s --output-dir ./sample-output --rows 50000 --format all
  %(prog)s --output-dir /mnt/fsxn/vol1 --format parquet
  %(prog)s --output-dir ./out --s3-ap-alias my-ap-alias --region ap-northeast-1
        """,
    )
    parser.add_argument(
        "--output-dir",
        default="./sample-output",
        help="Local output directory (default: ./sample-output)",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=50000,
        help="Number of rows per dataset (default: 50000)",
    )
    parser.add_argument(
        "--format",
        choices=["all", "parquet", "csv", "json"],
        default="all",
        help="Output format filter: all, parquet, csv, or json (default: all)",
    )
    parser.add_argument(
        "--s3-ap-alias",
        help="S3 Access Point alias — prints upload commands if provided",
    )
    parser.add_argument(
        "--region",
        default="ap-northeast-1",
        help="AWS region (default: ap-northeast-1)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("FSx for ONTAP Lakehouse — Sample Data Generator")
    print("=" * 60)
    print(f"  Rows per dataset : {args.rows:,}")
    print(f"  Output directory : {output_dir.resolve()}")
    print(f"  Format filter    : {args.format}")
    print()

    # Generate and write datasets based on format filter
    fmt = args.format

    if fmt in ("all", "parquet"):
        print("Generating transactions (Parquet → bronze/transactions/) ...")
        df_txn = generate_transactions(args.rows)
        write_transactions(df_txn, output_dir)

        print("Generating IoT sensors (Parquet, date-partitioned → bronze/iot-sensors/) ...")
        df_iot = generate_iot_sensors(args.rows)
        write_iot_sensors(df_iot, output_dir)

        print("Generating products (Parquet → silver/products/) ...")
        df_prod = generate_products(args.rows)
        write_products(df_prod, output_dir)

    if fmt in ("all", "csv"):
        print("Generating customers (CSV → silver/customers/) ...")
        df_cust = generate_customers(args.rows)
        write_customers(df_cust, output_dir)

    if fmt in ("all", "json"):
        print("Generating events (NDJSON → bronze/events/) ...")
        events = generate_events(args.rows)
        write_events(events, output_dir)

    # Print S3 upload commands if alias provided
    if args.s3_ap_alias:
        upload_to_s3(output_dir, args.s3_ap_alias, args.region)

    print(f"\n{'=' * 60}")
    print("✅ Sample data generation complete!")
    print(f"{'=' * 60}")
    print(f"\nOutput structure:")
    print(f"  {output_dir}/")
    if fmt in ("all", "parquet"):
        print(f"  ├── bronze/transactions/transactions.parquet")
        print(f"  ├── bronze/iot-sensors/date=YYYY-MM-DD/data.parquet")
        print(f"  ├── silver/products/products.parquet")
    if fmt in ("all", "csv"):
        print(f"  ├── silver/customers/customers.csv")
    if fmt in ("all", "json"):
        print(f"  └── bronze/events/events.ndjson")
    print(f"\nTo upload to FSx for ONTAP via NFS mount:")
    print(f"  cp -r {output_dir}/* /mnt/fsxn/<volume>/")
    print(f"\nTo upload via S3 Access Point:")
    print(f"  aws s3 sync {output_dir} s3://<s3ap-alias>/ --region {args.region}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate sample sensor data for FSx for ONTAP S3 AP PoC.
Output: Parquet file with microsecond timestamps (Spark-compatible).

Usage:
  python generate-sensor-data.py --rows 10000 --output sensor_data.parquet
  python generate-sensor-data.py --rows 5000000 --output sensor_data_large.parquet
"""

import argparse
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime


def generate_sensor_data(n_rows: int, seed: int = 42) -> pd.DataFrame:
    """Generate realistic IoT sensor data."""
    np.random.seed(seed)

    df = pd.DataFrame({
        'timestamp': pd.date_range(
            start='2026-01-01',
            periods=n_rows,
            freq='1min'
        ),
        'device_id': np.random.choice(
            [f'device_{i:03d}' for i in range(1, 21)],
            n_rows
        ),
        'sensor_id': np.random.choice(
            [f'S{i:03d}' for i in range(1, 6)],
            n_rows
        ),
        'temperature': np.round(np.random.normal(25, 5, n_rows), 2),
        'humidity': np.round(np.random.uniform(30, 90, n_rows), 2),
        'pressure': np.round(np.random.normal(1013, 10, n_rows), 2),
        'status': np.random.choice(
            ['normal', 'warning', 'critical'],
            n_rows,
            p=[0.85, 0.12, 0.03]
        ),
        'location': np.random.choice(
            ['factory_A', 'factory_B', 'warehouse_C', 'office_D'],
            n_rows
        ),
    })

    return df


def write_parquet_microsecond(df: pd.DataFrame, output_path: str):
    """Write Parquet with microsecond timestamps (Spark-compatible)."""
    table = pa.Table.from_pandas(df)

    # Convert nanosecond timestamps to microsecond (Spark compatibility)
    new_fields = []
    for field in table.schema:
        if pa.types.is_timestamp(field.type):
            new_fields.append(field.with_type(pa.timestamp('us')))
        else:
            new_fields.append(field)

    new_schema = pa.schema(new_fields)
    table = table.cast(new_schema)

    pq.write_table(table, output_path, compression='snappy')
    print(f"✅ Written {len(df):,} rows to {output_path}")
    print(f"   File size: {pq.read_metadata(output_path).serialized_size:,} bytes")
    print(f"   Columns: {', '.join(df.columns)}")
    print(f"   Timestamp resolution: microsecond (Spark-compatible)")


def main():
    parser = argparse.ArgumentParser(description='Generate sample sensor data')
    parser.add_argument('--rows', type=int, default=10000, help='Number of rows')
    parser.add_argument('--output', type=str, default='sensor_data.parquet', help='Output file')
    parser.add_argument('--seed', type=int, default=42, help='Random seed')
    args = parser.parse_args()

    print(f"Generating {args.rows:,} rows of sensor data...")
    df = generate_sensor_data(args.rows, args.seed)
    write_parquet_microsecond(df, args.output)


if __name__ == '__main__':
    main()

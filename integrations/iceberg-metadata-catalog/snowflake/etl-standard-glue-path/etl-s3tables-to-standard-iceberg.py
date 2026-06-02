#!/usr/bin/env python3
"""
ETL: S3 Tables → Standard Glue Iceberg Table
=============================================
Reads metadata from S3 Tables (via Glue Iceberg REST) and writes to a
standard Glue-managed Iceberg table on S3 for Snowflake access.

Prerequisites:
  pip install pyiceberg[glue,s3] pyarrow boto3

Usage:
  python etl-s3tables-to-standard-iceberg.py

Environment Variables:
  AWS_REGION: ap-northeast-1 (default)
  SOURCE_WAREHOUSE: <ACCOUNT_ID>:s3tablescatalog/fsxn-metadata-catalog
  TARGET_BUCKET: fsxn-metadata-mirror-<ACCOUNT_ID>
  TARGET_DATABASE: metadata_mirror
  TARGET_TABLE: unstructured_files
"""

import os
import sys
import time
from datetime import datetime

try:
    from pyiceberg.catalog import load_catalog
    from pyiceberg.schema import Schema
    from pyiceberg.types import (
        StringType, LongType, BooleanType, TimestampType,
        FloatType, NestedField, ListType
    )
    import pyarrow as pa
except ImportError:
    print("ERROR: Required packages not installed.")
    print("  pip install pyiceberg[glue,s3] pyarrow boto3")
    sys.exit(1)


# Configuration
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
SOURCE_WAREHOUSE = os.environ.get(
    "SOURCE_WAREHOUSE",
    # Replace <ACCOUNT_ID> with actual account ID at runtime
    os.environ.get("AWS_ACCOUNT_ID", "<ACCOUNT_ID>") + ":s3tablescatalog/fsxn-metadata-catalog"
)
TARGET_BUCKET = os.environ.get("TARGET_BUCKET", "fsxn-metadata-mirror-" + os.environ.get("AWS_ACCOUNT_ID", "<ACCOUNT_ID>"))
TARGET_DATABASE = os.environ.get("TARGET_DATABASE", "metadata_mirror")
TARGET_TABLE = os.environ.get("TARGET_TABLE", "unstructured_files")


def load_source_catalog():
    """Load the S3 Tables catalog via Glue Iceberg REST."""
    print(f"[1/5] Loading source catalog (S3 Tables via Glue REST)...")
    catalog = load_catalog(
        "s3tables_source",
        **{
            "type": "glue",
            "s3.region": AWS_REGION,
            "glue.region": AWS_REGION,
            "warehouse": SOURCE_WAREHOUSE,
        }
    )
    return catalog


def load_target_catalog():
    """Load the standard Glue catalog for the mirror table."""
    print(f"[2/5] Loading target catalog (standard Glue)...")
    catalog = load_catalog(
        "glue_target",
        **{
            "type": "glue",
            "s3.region": AWS_REGION,
            "glue.region": AWS_REGION,
            "warehouse": f"s3://{TARGET_BUCKET}/iceberg-mirror/",
        }
    )
    return catalog


def read_source_data(source_catalog):
    """Read all current records from S3 Tables."""
    print(f"[3/5] Reading source data from S3 Tables...")
    start = time.time()

    table = source_catalog.load_table(f"metadata.{TARGET_TABLE}")
    scan = table.scan()
    df = scan.to_arrow()

    elapsed = time.time() - start
    print(f"       Read {len(df)} records in {elapsed:.1f}s")
    print(f"       Schema: {df.schema}")
    return df, table.schema()


def ensure_target_table(target_catalog, iceberg_schema):
    """Create target table if it doesn't exist."""
    print(f"[4/5] Ensuring target table exists...")

    table_identifier = f"{TARGET_DATABASE}.{TARGET_TABLE}"

    try:
        table = target_catalog.load_table(table_identifier)
        print(f"       Target table exists: {table_identifier}")
        return table
    except Exception:
        print(f"       Creating target table: {table_identifier}")
        # Create namespace if needed
        try:
            target_catalog.create_namespace(TARGET_DATABASE)
        except Exception:
            pass  # Already exists

        table = target_catalog.create_table(
            table_identifier,
            schema=iceberg_schema,
            location=f"s3://{TARGET_BUCKET}/iceberg-mirror/{TARGET_TABLE}/",
        )
        print(f"       Created: {table.metadata_location}")
        return table


def write_to_target(target_table, arrow_df):
    """Write (overwrite) data to the target table."""
    print(f"[5/5] Writing {len(arrow_df)} records to target...")
    start = time.time()

    # Overwrite with current state (full refresh)
    target_table.overwrite(arrow_df)

    elapsed = time.time() - start
    print(f"       Written in {elapsed:.1f}s")
    print(f"       New metadata location: {target_table.metadata_location}")


def main():
    print("=" * 60)
    print("ETL: S3 Tables → Standard Glue Iceberg")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print(f"Source: {SOURCE_WAREHOUSE}")
    print(f"Target: s3://{TARGET_BUCKET}/iceberg-mirror/{TARGET_TABLE}/")
    print("=" * 60)

    # Load catalogs
    source_catalog = load_source_catalog()
    target_catalog = load_target_catalog()

    # Read source
    arrow_df, iceberg_schema = read_source_data(source_catalog)

    if len(arrow_df) == 0:
        print("\nWARNING: No data in source table. Nothing to ETL.")
        sys.exit(0)

    # Ensure target exists
    target_table = ensure_target_table(target_catalog, iceberg_schema)

    # Write to target
    write_to_target(target_table, arrow_df)

    # Summary
    print("\n" + "=" * 60)
    print("ETL COMPLETE")
    print(f"  Records: {len(arrow_df)}")
    print(f"  Target: {TARGET_DATABASE}.{TARGET_TABLE}")
    print(f"  Location: s3://{TARGET_BUCKET}/iceberg-mirror/{TARGET_TABLE}/")
    print(f"  Next: Validate via Athena, then configure Snowflake CATALOG INTEGRATION")
    print("=" * 60)


if __name__ == "__main__":
    main()

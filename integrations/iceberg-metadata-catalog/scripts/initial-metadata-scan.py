#!/usr/bin/env python3
"""
initial-metadata-scan.py — Initial Metadata Scan for FSx for ONTAP S3 Access Point

Scans files on an FSx for ONTAP volume via S3 Access Point and writes metadata
records to an S3 Tables Iceberg table using PyIceberg.

This script is used for:
  1. Initial catalog population (existing files before FPolicy was enabled)
  2. Periodic reconciliation (detect gaps from FPolicy event drops)
  3. Quick Start PoC (demonstrate metadata search in < 1 hour)

Usage:
    python initial-metadata-scan.py \
        --access-point-arn arn:aws:s3:ap-northeast-1:178625946981:accesspoint/fsxn-ap \
        --table-bucket-arn arn:aws:s3tables:ap-northeast-1:178625946981:bucket/fsxn-metadata-catalog \
        --namespace metadata \
        --table-name unstructured_files \
        --max-files 1000

    # Dry-run mode (list files without writing):
    python initial-metadata-scan.py \
        --access-point-arn <ARN> \
        --dry-run

Environment Variables:
    AWS_DEFAULT_REGION  - AWS region (default: ap-northeast-1)
    AWS_PROFILE         - AWS CLI profile to use

Requirements:
    pip install boto3 pyiceberg[s3tables]
"""

import argparse
import hashlib
import mimetypes
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    print("ERROR: boto3 is required. Install with: pip install boto3")
    sys.exit(1)

try:
    import pyarrow as pa
except ImportError:
    print("ERROR: pyarrow is required. Install with: pip install pyarrow")
    sys.exit(1)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_REGION = "ap-northeast-1"
BATCH_SIZE = 100  # Records per Iceberg append operation
LIST_PAGE_SIZE = 1000  # S3 ListObjectsV2 page size


# =============================================================================
# Schema Definition (matches design.md Component 1)
# =============================================================================

METADATA_SCHEMA = pa.schema([
    pa.field("file_id", pa.string(), nullable=False),
    pa.field("file_path", pa.string(), nullable=False),
    pa.field("file_name", pa.string(), nullable=False),
    pa.field("file_type", pa.string(), nullable=True),
    pa.field("file_size", pa.int64(), nullable=True),
    pa.field("created_at", pa.timestamp("us", tz="UTC"), nullable=True),
    pa.field("modified_at", pa.timestamp("us", tz="UTC"), nullable=True),
    pa.field("source_volume", pa.string(), nullable=True),
    pa.field("source_svm", pa.string(), nullable=True),
    pa.field("access_point_arn", pa.string(), nullable=False),
    pa.field("tags", pa.map_(pa.field('key', pa.string(), nullable=False), pa.field('value', pa.string(), nullable=False)), nullable=True),
    pa.field("classification", pa.string(), nullable=True),
    pa.field("confidence_score", pa.float64(), nullable=True),
    pa.field("sensitivity_level", pa.string(), nullable=True),
    pa.field("summary", pa.string(), nullable=True),
    pa.field("embedding_vector", pa.binary(), nullable=True),
    pa.field("enrichment_status", pa.string(), nullable=True),
    pa.field("enriched_at", pa.timestamp("us", tz="UTC"), nullable=True),
    pa.field("is_deleted", pa.bool_(), nullable=False),
    pa.field("deleted_at", pa.timestamp("us", tz="UTC"), nullable=True),
    pa.field("has_pii", pa.bool_(), nullable=True),
    pa.field("anonymized_path", pa.string(), nullable=True),
    pa.field("anonymization_status", pa.string(), nullable=True),
])


# =============================================================================
# Helper Functions
# =============================================================================


def generate_file_id(access_point_arn: str, key: str) -> str:
    """Generate deterministic UUID from access point ARN + object key."""
    seed = f"{access_point_arn}/{key}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def detect_file_type(key: str) -> str:
    """Detect MIME type from file extension."""
    mime_type, _ = mimetypes.guess_type(key)
    if mime_type:
        return mime_type
    # Fallback based on extension
    ext = os.path.splitext(key)[1].lower()
    extension_map = {
        ".dwg": "application/acad",
        ".step": "application/step",
        ".stp": "application/step",
        ".stl": "model/stl",
        ".dicom": "application/dicom",
        ".dcm": "application/dicom",
        ".parquet": "application/x-parquet",
        ".avro": "application/avro",
    }
    return extension_map.get(ext, "application/octet-stream")


def extract_volume_from_key(key: str) -> Optional[str]:
    """Extract volume name from S3 key prefix (convention: vol_name/...)."""
    parts = key.split("/")
    if len(parts) > 1:
        return parts[0]
    return None


# =============================================================================
# Main Scan Logic
# =============================================================================


def list_objects(s3_client, access_point_arn: str, prefix: str = "",
                max_files: int = 1000) -> list:
    """List objects from FSx S3 Access Point with pagination."""
    objects = []
    continuation_token = None

    while len(objects) < max_files:
        params = {
            "Bucket": access_point_arn,
            "MaxKeys": min(LIST_PAGE_SIZE, max_files - len(objects)),
        }
        if prefix:
            params["Prefix"] = prefix
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        try:
            response = s3_client.list_objects_v2(**params)
        except ClientError as e:
            print(f"  ERROR: ListObjectsV2 failed: {e}")
            break

        contents = response.get("Contents", [])
        objects.extend(contents)

        if not response.get("IsTruncated", False):
            break
        continuation_token = response.get("NextContinuationToken")

    return objects[:max_files]


def build_metadata_records(objects: list, access_point_arn: str) -> list:
    """Convert S3 object list to metadata records."""
    records = []
    for obj in objects:
        key = obj["Key"]
        # Skip directory markers
        if key.endswith("/"):
            continue

        file_name = os.path.basename(key)
        file_type = detect_file_type(key)
        file_id = generate_file_id(access_point_arn, key)
        volume = extract_volume_from_key(key)

        record = {
            "file_id": file_id,
            "file_path": f"s3://{access_point_arn}/{key}",
            "file_name": file_name,
            "file_type": file_type,
            "file_size": obj.get("Size", 0),
            "created_at": obj.get("LastModified"),
            "modified_at": obj.get("LastModified"),
            "source_volume": volume,
            "source_svm": None,
            "access_point_arn": access_point_arn,
            "tags": None,
            "classification": None,
            "confidence_score": None,
            "sensitivity_level": None,
            "summary": None,
            "embedding_vector": None,
            "enrichment_status": "pending",
            "enriched_at": None,
            "is_deleted": False,
            "deleted_at": None,
            "has_pii": None,
            "anonymized_path": None,
            "anonymization_status": None,
        }
        records.append(record)

    return records


def write_to_iceberg(records: list, table_bucket_arn: str, namespace: str,
                     table_name: str, region: str, dry_run: bool = False):
    """Write metadata records to S3 Tables Iceberg table."""
    if dry_run:
        print(f"  [DRY-RUN] Would write {len(records)} records to "
              f"{table_bucket_arn}/{namespace}.{table_name}")
        return

    # Convert records to PyArrow table
    table_data = {field.name: [] for field in METADATA_SCHEMA}
    for record in records:
        for field in METADATA_SCHEMA:
            table_data[field.name].append(record.get(field.name))

    arrow_table = pa.table(table_data, schema=METADATA_SCHEMA)

    # Write using PyIceberg (S3 Tables catalog)
    # Note: PyIceberg S3 Tables integration requires pyiceberg[s3tables]
    try:
        from pyiceberg.catalog import load_catalog

        catalog = load_catalog(
            "s3tables",
            **{
                "type": "rest",
                "uri": f"https://s3tables.{region}.amazonaws.com/iceberg",
                "warehouse": table_bucket_arn,
                "rest.sigv4-enabled": "true",
                "rest.signing-region": region,
                "rest.signing-name": "s3tables",
            }
        )

        table = catalog.load_table(f"{namespace}.{table_name}")
        table.append(arrow_table)
        print(f"  ✅ Wrote {len(records)} records to {namespace}.{table_name}")

    except ImportError:
        print("  ERROR: pyiceberg[s3tables] is required for S3 Tables write.")
        print("  Install with: pip install 'pyiceberg[s3tables]'")
        print(f"  Would have written {len(records)} records.")
        # Fallback: write as Parquet for manual import
        fallback_path = f"/tmp/metadata-scan-{datetime.now().strftime('%Y%m%d-%H%M%S')}.parquet"
        import pyarrow.parquet as pq
        pq.write_table(arrow_table, fallback_path)
        print(f"  Fallback: Parquet written to {fallback_path}")

    except Exception as e:
        print(f"  ERROR: Failed to write to Iceberg table: {e}")
        raise


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Scan FSx for ONTAP S3 AP and populate Iceberg metadata table",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--access-point-arn",
        required=True,
        help="FSx for ONTAP S3 Access Point ARN",
    )
    parser.add_argument(
        "--table-bucket-arn",
        default=None,
        help="S3 Tables table bucket ARN (required unless --dry-run)",
    )
    parser.add_argument(
        "--namespace",
        default="metadata",
        help="Iceberg namespace (default: metadata)",
    )
    parser.add_argument(
        "--table-name",
        default="unstructured_files",
        help="Iceberg table name (default: unstructured_files)",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="S3 key prefix to scan (default: scan all)",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=1000,
        help="Maximum number of files to scan (default: 1000)",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_DEFAULT_REGION", DEFAULT_REGION),
        help=f"AWS region (default: {DEFAULT_REGION})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List files without writing to Iceberg table",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.table_bucket_arn:
        parser.error("--table-bucket-arn is required unless --dry-run is specified")

    print("=" * 60)
    print("FSx for ONTAP → Iceberg Metadata Catalog: Initial Scan")
    print("=" * 60)
    print(f"  Access Point: {args.access_point_arn}")
    print(f"  Prefix:       {args.prefix or '(all)'}")
    print(f"  Max files:    {args.max_files}")
    print(f"  Region:       {args.region}")
    if args.dry_run:
        print(f"  Mode:         DRY-RUN")
    else:
        print(f"  Table Bucket: {args.table_bucket_arn}")
        print(f"  Table:        {args.namespace}.{args.table_name}")
    print("=" * 60)
    print()

    # Initialize S3 client
    s3_client = boto3.client("s3", region_name=args.region)

    # Step 1: List objects
    print("[1/3] Listing objects from FSx S3 Access Point...")
    objects = list_objects(s3_client, args.access_point_arn, args.prefix, args.max_files)
    print(f"  Found {len(objects)} objects")

    if not objects:
        print("  No objects found. Exiting.")
        sys.exit(0)

    # Step 2: Build metadata records
    print("[2/3] Building metadata records...")
    records = build_metadata_records(objects, args.access_point_arn)
    print(f"  Built {len(records)} metadata records (skipped {len(objects) - len(records)} directory markers)")

    # Show sample
    if records:
        sample = records[0]
        print(f"\n  Sample record:")
        print(f"    file_id:   {sample['file_id']}")
        print(f"    file_name: {sample['file_name']}")
        print(f"    file_type: {sample['file_type']}")
        print(f"    file_size: {sample['file_size']} bytes")
        print(f"    enrichment_status: {sample['enrichment_status']}")
        print()

    # Step 3: Write to Iceberg
    print("[3/3] Writing to Iceberg metadata table...")
    # Write in batches
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        write_to_iceberg(
            batch,
            args.table_bucket_arn or "",
            args.namespace,
            args.table_name,
            args.region,
            dry_run=args.dry_run,
        )

    # Summary
    print()
    print("=" * 60)
    print(f"  Total files scanned:    {len(objects)}")
    print(f"  Metadata records:       {len(records)}")
    print(f"  Enrichment pending:     {len(records)} (run AI enrichment pipeline next)")
    print("=" * 60)

    if not args.dry_run:
        print()
        print("Next steps:")
        print("  1. Query metadata with Athena:")
        print(f"     SELECT * FROM \"{args.namespace}\".\"{args.table_name}\" LIMIT 10;")
        print("  2. Run AI enrichment pipeline for pending records")
        print("  3. Enable FPolicy for real-time sync of new files")


if __name__ == "__main__":
    main()

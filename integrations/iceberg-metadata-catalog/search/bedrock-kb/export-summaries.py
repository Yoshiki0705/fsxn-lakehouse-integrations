"""
export-summaries.py — Export Metadata Summaries for Bedrock Knowledge Base

Exports AI-generated summaries from the Iceberg metadata table as individual
text documents to S3, formatted for Bedrock Knowledge Base ingestion.

Each document contains:
  - File name and path
  - Classification and confidence
  - AI-generated summary
  - Tags and attributes

This enables natural language search like:
  "Find all invoices from Q1 2025 with amount > $10,000"

Usage:
    python export-summaries.py \
        --table-bucket-arn arn:aws:s3tables:ap-northeast-1:178625946981:bucket/fsxn-metadata-catalog \
        --output-bucket fsxn-metadata-kb-documents \
        --output-prefix summaries/

Environment Variables:
    AWS_REGION  - AWS region (default: ap-northeast-1)
"""

import argparse
import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")


def fetch_enriched_records(table_bucket_arn: str) -> list:
    """Fetch all enriched records from S3 Tables."""
    from pyiceberg.catalog import load_catalog
    from pyiceberg.expressions import And, EqualTo

    catalog = load_catalog(
        "s3tables",
        **{
            "type": "rest",
            "uri": f"https://s3tables.{REGION}.amazonaws.com/iceberg",
            "warehouse": table_bucket_arn,
            "rest.sigv4-enabled": "true",
            "rest.signing-region": REGION,
            "rest.signing-name": "s3tables",
        }
    )

    table = catalog.load_table("metadata.unstructured_files")
    scan = table.scan(
        row_filter=And(
            EqualTo("enrichment_status", "completed"),
            EqualTo("is_deleted", False),
        ),
        selected_fields=(
            "file_id", "file_name", "file_path", "file_type",
            "classification", "confidence_score", "summary",
            "sensitivity_level", "source_volume", "created_at", "tags",
        ),
    )

    records = []
    for batch in scan.to_arrow().to_batches():
        for i in range(batch.num_rows):
            records.append({
                "file_id": batch.column("file_id")[i].as_py(),
                "file_name": batch.column("file_name")[i].as_py(),
                "file_path": batch.column("file_path")[i].as_py(),
                "file_type": batch.column("file_type")[i].as_py(),
                "classification": batch.column("classification")[i].as_py(),
                "confidence_score": batch.column("confidence_score")[i].as_py(),
                "summary": batch.column("summary")[i].as_py(),
                "sensitivity_level": batch.column("sensitivity_level")[i].as_py(),
                "source_volume": batch.column("source_volume")[i].as_py(),
                "created_at": str(batch.column("created_at")[i].as_py()),
                "tags": batch.column("tags")[i].as_py(),
            })

    return records


def format_document(record: dict) -> str:
    """Format a metadata record as a text document for KB ingestion."""
    tags_str = ""
    if record.get("tags"):
        tags_str = ", ".join(f"{k}={v}" for k, v in record["tags"].items())

    doc = f"""File: {record['file_name']}
Path: {record['file_path']}
Type: {record['file_type']}
Classification: {record['classification']} (confidence: {record.get('confidence_score', 0):.2f})
Sensitivity: {record.get('sensitivity_level', 'unknown')}
Volume: {record.get('source_volume', 'unknown')}
Created: {record.get('created_at', 'unknown')}
Tags: {tags_str or 'none'}

Summary:
{record.get('summary', 'No summary available.')}
"""
    return doc.strip()


def export_to_s3(records: list, output_bucket: str, output_prefix: str):
    """Export formatted documents to S3 for KB ingestion."""
    s3_client = boto3.client("s3", region_name=REGION)
    exported = 0

    for record in records:
        doc_text = format_document(record)
        key = f"{output_prefix}{record['file_id']}.txt"

        # Add metadata for KB filtering
        metadata = {
            "classification": record.get("classification", ""),
            "file_type": record.get("file_type", ""),
            "sensitivity_level": record.get("sensitivity_level", ""),
        }

        s3_client.put_object(
            Bucket=output_bucket,
            Key=key,
            Body=doc_text.encode("utf-8"),
            ContentType="text/plain",
            Metadata=metadata,
        )
        exported += 1

    return exported


def main():
    parser = argparse.ArgumentParser(description="Export metadata summaries for Bedrock KB")
    parser.add_argument("--table-bucket-arn", required=True)
    parser.add_argument("--output-bucket", required=True)
    parser.add_argument("--output-prefix", default="summaries/")
    args = parser.parse_args()

    logger.info("Fetching enriched records from S3 Tables...")
    records = fetch_enriched_records(args.table_bucket_arn)
    logger.info(f"Found {len(records)} enriched records")

    logger.info(f"Exporting to s3://{args.output_bucket}/{args.output_prefix}...")
    exported = export_to_s3(records, args.output_bucket, args.output_prefix)
    logger.info(f"Exported {exported} documents")

    logger.info("Next: Sync Bedrock Knowledge Base data source to index new documents")


if __name__ == "__main__":
    main()

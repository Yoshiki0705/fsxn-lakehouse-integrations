"""
metadata-sync-handler — FPolicy Event → Iceberg Metadata Sync Lambda

Processes FPolicy file events from SQS and writes/updates metadata records
in the S3 Tables Iceberg table.

Architecture:
    ONTAP FPolicy (async) → ECS Fargate (FPolicy Server) → SQS Queue
        → This Lambda → S3 Tables (Iceberg via PyIceberg)

Event Types:
    - create: New file detected → INSERT metadata record (enrichment_status=pending)
    - write:  File modified → UPDATE modified_at, file_size, reset enrichment_status
    - rename: File renamed → UPDATE file_path, file_name
    - delete: File deleted → Soft delete (is_deleted=true, deleted_at=now)

Idempotency:
    file_id = UUID5(access_point_arn + file_path) — deterministic, safe to reprocess

Environment Variables:
    TABLE_BUCKET_ARN    - S3 Tables table bucket ARN
    NAMESPACE           - Iceberg namespace (default: metadata)
    TABLE_NAME          - Iceberg table name (default: unstructured_files)
    AWS_REGION          - AWS region
    LOG_LEVEL           - Logging level (default: INFO)
"""

import hashlib
import json
import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
import pyarrow as pa

# =============================================================================
# Configuration
# =============================================================================

TABLE_BUCKET_ARN = os.environ["TABLE_BUCKET_ARN"]
NAMESPACE = os.environ.get("NAMESPACE", "metadata")
TABLE_NAME = os.environ.get("TABLE_NAME", "unstructured_files")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

logger = logging.getLogger(__name__)
logger.setLevel(LOG_LEVEL)

# Metrics
METRICS = {
    "events_processed": 0,
    "events_created": 0,
    "events_updated": 0,
    "events_deleted": 0,
    "events_failed": 0,
}


# =============================================================================
# Schema (subset for append operations)
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


def generate_file_id(access_point_arn: str, file_path: str) -> str:
    """Generate deterministic UUID from access point ARN + file path."""
    seed = f"{access_point_arn}/{file_path}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def detect_file_type(file_path: str) -> str:
    """Detect MIME type from file extension."""
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type:
        return mime_type
    ext = os.path.splitext(file_path)[1].lower()
    extension_map = {
        ".dwg": "application/acad",
        ".step": "application/step",
        ".stp": "application/step",
        ".stl": "model/stl",
        ".dicom": "application/dicom",
        ".dcm": "application/dicom",
        ".parquet": "application/x-parquet",
    }
    return extension_map.get(ext, "application/octet-stream")


def parse_fpolicy_event(sqs_body: str) -> dict:
    """
    Parse FPolicy event from SQS message body.

    Expected format (from FPolicy Server → SQS):
    {
        "event_type": "create" | "write" | "rename" | "delete",
        "file_path": "/vol1/data/images/photo001.jpg",
        "new_file_path": "/vol1/data/images/photo001_renamed.jpg",  (rename only)
        "file_size": 2048576,
        "timestamp": "2026-06-01T10:00:00Z",
        "svm_name": "svm1",
        "volume_name": "vol1",
        "access_point_arn": "arn:aws:s3:ap-northeast-1:<ACCOUNT_ID>:accesspoint/fsxn-ap"
    }
    """
    try:
        event = json.loads(sqs_body)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse SQS message body: {e}")
        raise ValueError(f"Invalid JSON in SQS message: {e}")

    required_fields = ["event_type", "file_path", "timestamp"]
    for field in required_fields:
        if field not in event:
            raise ValueError(f"Missing required field: {field}")

    if event["event_type"] not in ("create", "write", "rename", "delete"):
        raise ValueError(f"Unknown event_type: {event['event_type']}")

    return event


# =============================================================================
# Event Processing
# =============================================================================


def process_create_event(event: dict) -> dict:
    """Process file creation event → new metadata record."""
    file_path = event["file_path"]
    access_point_arn = event.get("access_point_arn", "")
    timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))

    return {
        "file_id": generate_file_id(access_point_arn, file_path),
        "file_path": f"s3://{access_point_arn}/{file_path.lstrip('/')}",
        "file_name": os.path.basename(file_path),
        "file_type": detect_file_type(file_path),
        "file_size": event.get("file_size", 0),
        "created_at": timestamp,
        "modified_at": timestamp,
        "source_volume": event.get("volume_name"),
        "source_svm": event.get("svm_name"),
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


def process_write_event(event: dict) -> dict:
    """Process file write/modify event → update record with new size/timestamp."""
    file_path = event["file_path"]
    access_point_arn = event.get("access_point_arn", "")
    timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))

    # For writes, we create a new record that will supersede the old one
    # Iceberg's merge-on-read or compaction will handle deduplication
    return {
        "file_id": generate_file_id(access_point_arn, file_path),
        "file_path": f"s3://{access_point_arn}/{file_path.lstrip('/')}",
        "file_name": os.path.basename(file_path),
        "file_type": detect_file_type(file_path),
        "file_size": event.get("file_size", 0),
        "created_at": None,  # Preserve original created_at (handled by MERGE)
        "modified_at": timestamp,
        "source_volume": event.get("volume_name"),
        "source_svm": event.get("svm_name"),
        "access_point_arn": access_point_arn,
        "tags": None,
        "classification": None,
        "confidence_score": None,
        "sensitivity_level": None,
        "summary": None,
        "embedding_vector": None,
        "enrichment_status": "pending",  # Re-enrich after modification
        "enriched_at": None,
        "is_deleted": False,
        "deleted_at": None,
        "has_pii": None,
        "anonymized_path": None,
        "anonymization_status": None,
    }


def process_delete_event(event: dict) -> dict:
    """Process file deletion event → soft delete (is_deleted=true)."""
    file_path = event["file_path"]
    access_point_arn = event.get("access_point_arn", "")
    timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))

    return {
        "file_id": generate_file_id(access_point_arn, file_path),
        "file_path": f"s3://{access_point_arn}/{file_path.lstrip('/')}",
        "file_name": os.path.basename(file_path),
        "file_type": detect_file_type(file_path),
        "file_size": 0,
        "created_at": None,
        "modified_at": timestamp,
        "source_volume": event.get("volume_name"),
        "source_svm": event.get("svm_name"),
        "access_point_arn": access_point_arn,
        "tags": None,
        "classification": None,
        "confidence_score": None,
        "sensitivity_level": None,
        "summary": None,
        "embedding_vector": None,
        "enrichment_status": "not_applicable",
        "enriched_at": None,
        "is_deleted": True,
        "deleted_at": timestamp,
        "has_pii": None,
        "anonymized_path": None,
        "anonymization_status": None,
    }


def process_rename_event(event: dict) -> list:
    """
    Process file rename event → soft delete old + create new.

    Returns two records: one delete for old path, one create for new path.
    """
    records = []

    # Soft delete old path
    delete_event = {**event, "event_type": "delete"}
    records.append(process_delete_event(delete_event))

    # Create new path
    new_path = event.get("new_file_path", event["file_path"])
    create_event = {**event, "file_path": new_path, "event_type": "create"}
    records.append(process_create_event(create_event))

    return records


# =============================================================================
# Iceberg Write
# =============================================================================


def write_records_to_iceberg(records: list[dict]) -> None:
    """Write metadata records to S3 Tables Iceberg table via PyIceberg."""
    if not records:
        return

    # Convert to PyArrow table
    table_data = {field.name: [] for field in METADATA_SCHEMA}
    for record in records:
        for field in METADATA_SCHEMA:
            table_data[field.name].append(record.get(field.name))

    arrow_table = pa.table(table_data, schema=METADATA_SCHEMA)

    # Write to S3 Tables via PyIceberg
    from pyiceberg.catalog import load_catalog

    catalog = load_catalog(
        "s3tables",
        **{
            "type": "rest",
            "uri": f"https://s3tables.{REGION}.amazonaws.com/iceberg",
            "warehouse": TABLE_BUCKET_ARN,
            "rest.sigv4-enabled": "true",
            "rest.signing-region": REGION,
            "rest.signing-name": "s3tables",
        }
    )

    table = catalog.load_table(f"{NAMESPACE}.{TABLE_NAME}")
    table.append(arrow_table)

    logger.info(f"Appended {len(records)} records to {NAMESPACE}.{TABLE_NAME}")


# =============================================================================
# Lambda Handler
# =============================================================================


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler for SQS → Iceberg metadata sync.

    Processes a batch of SQS messages containing FPolicy events.
    Each message is processed independently; failures are reported
    via batchItemFailures for SQS partial batch response.
    """
    records_to_write = []
    batch_item_failures = []

    sqs_records = event.get("Records", [])
    logger.info(f"Processing {len(sqs_records)} SQS messages")

    for sqs_record in sqs_records:
        message_id = sqs_record.get("messageId", "unknown")

        try:
            # Parse FPolicy event from SQS message
            fpolicy_event = parse_fpolicy_event(sqs_record["body"])
            event_type = fpolicy_event["event_type"]

            # Process based on event type
            if event_type == "create":
                records_to_write.append(process_create_event(fpolicy_event))
                METRICS["events_created"] += 1

            elif event_type == "write":
                records_to_write.append(process_write_event(fpolicy_event))
                METRICS["events_updated"] += 1

            elif event_type == "delete":
                records_to_write.append(process_delete_event(fpolicy_event))
                METRICS["events_deleted"] += 1

            elif event_type == "rename":
                rename_records = process_rename_event(fpolicy_event)
                records_to_write.extend(rename_records)
                METRICS["events_updated"] += 1

            METRICS["events_processed"] += 1

        except (ValueError, KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to process message {message_id}: {e}")
            METRICS["events_failed"] += 1
            batch_item_failures.append({"itemIdentifier": message_id})

        except Exception as e:
            logger.error(f"Unexpected error processing message {message_id}: {e}")
            METRICS["events_failed"] += 1
            batch_item_failures.append({"itemIdentifier": message_id})

    # Batch write all records to Iceberg
    if records_to_write:
        try:
            write_records_to_iceberg(records_to_write)
        except Exception as e:
            logger.error(f"Failed to write {len(records_to_write)} records to Iceberg: {e}")
            # All messages in this batch failed
            batch_item_failures = [
                {"itemIdentifier": r.get("messageId", "unknown")}
                for r in sqs_records
            ]

    # Log metrics
    logger.info(
        f"Batch complete: processed={METRICS['events_processed']}, "
        f"created={METRICS['events_created']}, "
        f"updated={METRICS['events_updated']}, "
        f"deleted={METRICS['events_deleted']}, "
        f"failed={METRICS['events_failed']}"
    )

    # Return partial batch failure response
    # SQS will retry only the failed messages
    return {"batchItemFailures": batch_item_failures}

"""
update-metadata — Write Enrichment Results to S3 Tables

Updates the Iceberg metadata table with AI enrichment results
(classification, summary, embedding, PII detection).

This Lambda is called at the end of each file's enrichment pipeline
in the Step Functions workflow.

Environment Variables:
    TABLE_BUCKET_ARN  - S3 Tables table bucket ARN
    NAMESPACE         - Iceberg namespace (default: metadata)
    TABLE_NAME        - Iceberg table name (default: unstructured_files)
    AWS_REGION        - AWS region
"""

import base64
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import pyarrow as pa

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

TABLE_BUCKET_ARN = os.environ.get("TABLE_BUCKET_ARN", "")
NAMESPACE = os.environ.get("NAMESPACE", "metadata")
TABLE_NAME = os.environ.get("TABLE_NAME", "unstructured_files")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Update metadata record with enrichment results.

    Input:
        file_id: str
        classification: str (optional)
        confidence_score: float (optional)
        summary: str (optional)
        embedding_vector: str (base64-encoded, optional)
        has_pii: bool (optional)
        enrichment_status: str ("completed" or "failed")
        error_reason: str (optional, for failed status)

    Output:
        success: bool
        file_id: str
    """
    file_id = event["file_id"]
    enrichment_status = event.get("enrichment_status", "completed")

    logger.info(f"Updating metadata for {file_id}: status={enrichment_status}")

    now = datetime.now(timezone.utc)

    # Build the update record
    # Note: Iceberg append-only pattern — we append a new version of the record.
    # The latest record (by enriched_at) is the current state.
    # Compaction will merge these into the latest version.
    update_data = {
        "file_id": file_id,
        "enrichment_status": enrichment_status,
        "enriched_at": now,
    }

    if enrichment_status == "completed":
        update_data["classification"] = event.get("classification")
        update_data["confidence_score"] = event.get("confidence_score")
        update_data["summary"] = event.get("summary", "")[:500]
        update_data["has_pii"] = event.get("has_pii")

        # Decode embedding if provided
        embedding_b64 = event.get("embedding_vector")
        if embedding_b64:
            update_data["embedding_vector"] = base64.b64decode(embedding_b64)
        else:
            update_data["embedding_vector"] = None

        # Set sensitivity level based on PII detection
        if event.get("has_pii"):
            update_data["sensitivity_level"] = "confidential"
            update_data["anonymization_status"] = "pending"
        else:
            update_data["sensitivity_level"] = "internal"
            update_data["anonymization_status"] = "not_required"

    elif enrichment_status == "failed":
        error_reason = event.get("error_reason", "Unknown error")
        update_data["summary"] = f"Enrichment failed: {error_reason[:200]}"
        update_data["classification"] = None
        update_data["confidence_score"] = None
        update_data["embedding_vector"] = None
        update_data["has_pii"] = None
        update_data["sensitivity_level"] = None
        update_data["anonymization_status"] = None

    # Write to S3 Tables via PyIceberg
    try:
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

        # Build a minimal PyArrow table for the overwrite
        # Using Iceberg overwrite with filter on file_id
        schema = pa.schema([
            pa.field("file_id", pa.string()),
            pa.field("classification", pa.string()),
            pa.field("confidence_score", pa.float64()),
            pa.field("summary", pa.string()),
            pa.field("embedding_vector", pa.binary()),
            pa.field("sensitivity_level", pa.string()),
            pa.field("has_pii", pa.bool_()),
            pa.field("enrichment_status", pa.string()),
            pa.field("enriched_at", pa.timestamp("us", tz="UTC")),
            pa.field("anonymization_status", pa.string()),
        ])

        arrow_table = pa.table(
            {
                "file_id": [update_data["file_id"]],
                "classification": [update_data.get("classification")],
                "confidence_score": [update_data.get("confidence_score")],
                "summary": [update_data.get("summary")],
                "embedding_vector": [update_data.get("embedding_vector")],
                "sensitivity_level": [update_data.get("sensitivity_level")],
                "has_pii": [update_data.get("has_pii")],
                "enrichment_status": [update_data["enrichment_status"]],
                "enriched_at": [update_data["enriched_at"]],
                "anonymization_status": [update_data.get("anonymization_status")],
            },
            schema=schema,
        )

        # Append enrichment result (merge handled by downstream query logic)
        table.append(arrow_table)

        logger.info(f"Successfully updated metadata for {file_id}")
        return {"success": True, "file_id": file_id}

    except Exception as e:
        logger.error(f"Failed to update metadata for {file_id}: {e}")
        raise

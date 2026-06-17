"""
write_results_to_iceberg — Record Multi-Model Classification Results to Iceberg

Writes classification + confidence + model agreement metadata to the
S3 Tables Iceberg table via PyIceberg, extending the existing metadata schema.

New columns added to the enrichment results:
  - multimodel_classification: str (consensus classification)
  - multimodel_confidence: float (consensus confidence)
  - model_agreement: str ("unanimous"|"majority"|"disagreement")
  - model_votes: str (JSON: {"blueprint": 2, "diagram": 1})
  - individual_results: str (JSON array of per-model results)
  - escalated: bool (whether sent to human review)

Environment Variables:
    GLUE_CATALOG_ID     - AWS account ID for Glue catalog
    TABLE_NAMESPACE     - Iceberg namespace (default: metadata)
    TABLE_NAME          - Iceberg table name (default: unstructured_files)
    AWS_REGION          - AWS region
"""

import json
import logging
import os
import time
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
GLUE_CATALOG_ID = os.environ.get("GLUE_CATALOG_ID", "")
TABLE_NAMESPACE = os.environ.get("TABLE_NAMESPACE", "metadata")
TABLE_NAME = os.environ.get("TABLE_NAME", "unstructured_files")


def get_iceberg_catalog():
    """Initialize PyIceberg catalog pointing to Glue Iceberg REST."""
    from pyiceberg.catalog import load_catalog

    catalog = load_catalog(
        "glue",
        **{
            "type": "glue",
            "glue.region": REGION,
            "glue.id": GLUE_CATALOG_ID,
        },
    )
    return catalog


def write_multimodel_result(
    file_id: str,
    multimodel_result: dict,
    existing_record: dict | None = None,
) -> dict:
    """
    Write multi-model classification result to Iceberg table.

    This appends enrichment metadata to the existing file record.
    Uses PyIceberg append (not overwrite) — the result is an additional
    record linked by file_id.

    Args:
        file_id: Unique file identifier
        multimodel_result: Output from multimodel_classify.classify_image_multimodel()
        existing_record: Optional existing metadata record to merge with

    Returns:
        The record written to Iceberg
    """
    import pyarrow as pa

    record = {
        "file_id": file_id,
        "multimodel_classification": multimodel_result["classification"],
        "multimodel_confidence": multimodel_result["confidence_score"],
        "model_agreement": multimodel_result["agreement"],
        "model_votes": json.dumps(multimodel_result.get("vote_count", {})),
        "individual_results": json.dumps(multimodel_result.get("individual_results", [])),
        "escalated": multimodel_result.get("escalate", False),
        "enrichment_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "enrichment_version": "multimodel-v1",
    }

    # Merge with existing record if provided
    if existing_record:
        record = {**existing_record, **record}

    logger.info(f"Writing multi-model result for {file_id}: {record['multimodel_classification']} ({record['model_agreement']})")

    return record


def batch_write_to_iceberg(records: list[dict]) -> int:
    """
    Batch write multi-model enrichment results to Iceberg table.

    Uses PyIceberg to append records as a new data file.
    Schema must include the multimodel_* columns (added via schema evolution).

    Returns:
        Number of records written
    """
    import pyarrow as pa

    if not records:
        return 0

    # Define schema for the enrichment result columns
    schema = pa.schema([
        pa.field("file_id", pa.string(), nullable=False),
        pa.field("multimodel_classification", pa.string()),
        pa.field("multimodel_confidence", pa.float64()),
        pa.field("model_agreement", pa.string()),
        pa.field("model_votes", pa.string()),  # JSON
        pa.field("individual_results", pa.string()),  # JSON
        pa.field("escalated", pa.bool_()),
        pa.field("enrichment_timestamp", pa.string()),
        pa.field("enrichment_version", pa.string()),
    ])

    # Convert to PyArrow Table
    table_data = pa.table(
        {field.name: [r.get(field.name) for r in records] for field in schema},
        schema=schema,
    )

    try:
        catalog = get_iceberg_catalog()
        iceberg_table = catalog.load_table(f"{TABLE_NAMESPACE}.{TABLE_NAME}")

        # Append to existing table
        iceberg_table.append(table_data)
        logger.info(f"Successfully wrote {len(records)} records to {TABLE_NAMESPACE}.{TABLE_NAME}")
        return len(records)

    except Exception as e:
        logger.error(f"Failed to write to Iceberg: {e}")
        # Fallback: write to local JSON for later retry
        fallback_path = f"/tmp/multimodel_results_{int(time.time())}.json"
        with open(fallback_path, "w") as f:
            json.dump(records, f, indent=2)
        logger.info(f"Fallback: saved {len(records)} records to {fallback_path}")
        raise


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda handler: write a batch of multi-model results to Iceberg.

    Input:
        records: list of {file_id, multimodel_result}

    Output:
        written_count: int
    """
    input_records = event.get("records", [])

    iceberg_records = []
    for item in input_records:
        file_id = item["file_id"]
        multimodel_result = item["multimodel_result"]
        record = write_multimodel_result(file_id, multimodel_result)
        iceberg_records.append(record)

    written = batch_write_to_iceberg(iceberg_records)

    return {
        "written_count": written,
        "total_input": len(input_records),
    }


if __name__ == "__main__":
    # Demo: generate sample records and show what would be written
    sample_results = [
        {
            "file_id": "file-001",
            "multimodel_result": {
                "classification": "blueprint",
                "confidence_score": 0.92,
                "agreement": "unanimous",
                "vote_count": {"blueprint": 2},
                "individual_results": [
                    {"model": "claude-haiku", "classification": "blueprint", "confidence_score": 0.95},
                    {"model": "nova-lite", "classification": "blueprint", "confidence_score": 0.89},
                ],
                "escalate": False,
            },
        },
        {
            "file_id": "file-002",
            "multimodel_result": {
                "classification": "diagram",
                "confidence_score": 0.72,
                "agreement": "majority",
                "vote_count": {"diagram": 2, "blueprint": 1},
                "individual_results": [
                    {"model": "claude-haiku", "classification": "diagram", "confidence_score": 0.8},
                    {"model": "nova-lite", "classification": "diagram", "confidence_score": 0.7},
                ],
                "escalate": False,
            },
        },
    ]

    print("Sample records to write:")
    for item in sample_results:
        record = write_multimodel_result(item["file_id"], item["multimodel_result"])
        print(json.dumps(record, indent=2))
    print(f"\nTotal: {len(sample_results)} records")
    print("\nTo write to Iceberg, set GLUE_CATALOG_ID and run as Lambda or call batch_write_to_iceberg()")

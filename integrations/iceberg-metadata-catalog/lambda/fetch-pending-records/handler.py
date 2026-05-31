"""
fetch-pending-records — Query Pending Records from S3 Tables

Queries the Iceberg metadata table for records with enrichment_status='pending'
and returns them for processing by the Step Functions workflow.

Environment Variables:
    TABLE_BUCKET_ARN  - S3 Tables table bucket ARN
    NAMESPACE         - Iceberg namespace (default: metadata)
    TABLE_NAME        - Iceberg table name (default: unstructured_files)
    AWS_REGION        - AWS region
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

TABLE_BUCKET_ARN = os.environ.get("TABLE_BUCKET_ARN", "")
NAMESPACE = os.environ.get("NAMESPACE", "metadata")
TABLE_NAME = os.environ.get("TABLE_NAME", "unstructured_files")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Fetch pending records from the Iceberg metadata table.

    Input:
        max_records: int (default: 50)
        table_bucket_arn: str (optional, overrides env var)
        namespace: str (optional)
        table_name: str (optional)

    Output:
        count: int
        records: list[dict] (file_id, file_path, file_name, file_type, access_point_arn)
    """
    max_records = event.get("max_records", 50)
    table_bucket = event.get("table_bucket_arn", TABLE_BUCKET_ARN)
    namespace = event.get("namespace", NAMESPACE)
    table_name = event.get("table_name", TABLE_NAME)

    logger.info(f"Fetching up to {max_records} pending records from {namespace}.{table_name}")

    try:
        from pyiceberg.catalog import load_catalog
        from pyiceberg.expressions import EqualTo

        catalog = load_catalog(
            "s3tables",
            **{
                "type": "rest",
                "uri": f"https://s3tables.{REGION}.amazonaws.com/iceberg",
                "warehouse": table_bucket,
                "rest.sigv4-enabled": "true",
                "rest.signing-region": REGION,
                "rest.signing-name": "s3tables",
            }
        )

        table = catalog.load_table(f"{namespace}.{table_name}")

        # Scan for pending records
        scan = table.scan(
            row_filter=EqualTo("enrichment_status", "pending"),
            selected_fields=(
                "file_id", "file_path", "file_name", "file_type", "access_point_arn"
            ),
            limit=max_records,
        )

        records = []
        for batch in scan.to_arrow().to_batches():
            for i in range(batch.num_rows):
                records.append({
                    "file_id": batch.column("file_id")[i].as_py(),
                    "file_path": batch.column("file_path")[i].as_py(),
                    "file_name": batch.column("file_name")[i].as_py(),
                    "file_type": batch.column("file_type")[i].as_py(),
                    "access_point_arn": batch.column("access_point_arn")[i].as_py(),
                })
                if len(records) >= max_records:
                    break
            if len(records) >= max_records:
                break

        logger.info(f"Found {len(records)} pending records")

        return {
            "count": len(records),
            "records": records,
        }

    except Exception as e:
        logger.error(f"Failed to fetch pending records: {e}")
        raise

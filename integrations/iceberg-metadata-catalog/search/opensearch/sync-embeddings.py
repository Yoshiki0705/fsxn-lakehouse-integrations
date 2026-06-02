"""
sync-embeddings.py — Sync Embeddings from S3 Tables to OpenSearch Serverless

Reads embedding vectors from the Iceberg metadata table and indexes them
into an OpenSearch Serverless collection for kNN similarity search.

Architecture:
    S3 Tables (embedding_vector column)
      → This script (scheduled via EventBridge / Step Functions)
        → OpenSearch Serverless (vector search collection)

Usage:
    python sync-embeddings.py \
        --collection-endpoint https://xxxxxxxx.ap-northeast-1.aoss.amazonaws.com \
        --table-bucket-arn arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog \
        --full-sync          # First run: index all records
        --incremental-sync   # Subsequent: only new/updated records

Environment Variables:
    OPENSEARCH_ENDPOINT   - OpenSearch Serverless collection endpoint
    TABLE_BUCKET_ARN      - S3 Tables table bucket ARN
    AWS_REGION            - AWS region (default: ap-northeast-1)

Requirements:
    pip install boto3 opensearch-py requests-aws4auth pyiceberg[s3tables] pyarrow
"""

import argparse
import json
import logging
import os
import struct
import sys
from datetime import datetime, timezone
from typing import Optional

import boto3

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
INDEX_NAME = "fsxn-metadata-embeddings"
EMBEDDING_DIMENSIONS = 1024
BATCH_SIZE = 100


# =============================================================================
# OpenSearch Index Mapping
# =============================================================================

INDEX_MAPPING = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 512,
        }
    },
    "mappings": {
        "properties": {
            "file_id": {"type": "keyword"},
            "file_name": {"type": "text", "analyzer": "standard"},
            "file_path": {"type": "keyword"},
            "file_type": {"type": "keyword"},
            "classification": {"type": "keyword"},
            "summary": {"type": "text", "analyzer": "standard"},
            "sensitivity_level": {"type": "keyword"},
            "department": {"type": "keyword"},
            "created_at": {"type": "date"},
            "embedding_vector": {
                "type": "knn_vector",
                "dimension": EMBEDDING_DIMENSIONS,
                "method": {
                    "name": "hnsw",
                    "space_type": "cosinesimil",
                    "engine": "nmslib",
                    "parameters": {
                        "ef_construction": 512,
                        "m": 16,
                    },
                },
            },
        }
    },
}


# =============================================================================
# OpenSearch Client
# =============================================================================


def get_opensearch_client(endpoint: str):
    """Create OpenSearch client with SigV4 authentication."""
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from requests_aws4auth import AWS4Auth

    credentials = boto3.Session().get_credentials()
    auth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        REGION,
        "aoss",
        session_token=credentials.token,
    )

    client = OpenSearch(
        hosts=[{"host": endpoint.replace("https://", ""), "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )
    return client


def create_index_if_not_exists(client, index_name: str):
    """Create the kNN index if it doesn't exist."""
    if not client.indices.exists(index=index_name):
        client.indices.create(index=index_name, body=INDEX_MAPPING)
        logger.info(f"Created index: {index_name}")
    else:
        logger.info(f"Index already exists: {index_name}")


# =============================================================================
# Embedding Decode
# =============================================================================


def decode_embedding(binary_data: bytes) -> list:
    """Decode binary embedding to float list."""
    num_floats = len(binary_data) // 4
    return list(struct.unpack(f"{num_floats}f", binary_data))


# =============================================================================
# Sync Logic
# =============================================================================


def fetch_records(table_bucket_arn: str, incremental: bool = False,
                  since: Optional[datetime] = None) -> list:
    """Fetch records with embeddings from S3 Tables."""
    from pyiceberg.catalog import load_catalog
    from pyiceberg.expressions import And, EqualTo, GreaterThanOrEqual, IsNotNull

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

    # Build filter
    filters = [
        EqualTo("is_deleted", False),
        EqualTo("enrichment_status", "completed"),
    ]

    if incremental and since:
        filters.append(GreaterThanOrEqual("enriched_at", since))

    row_filter = And(*filters) if len(filters) > 1 else filters[0]

    scan = table.scan(
        row_filter=row_filter,
        selected_fields=(
            "file_id", "file_name", "file_path", "file_type",
            "classification", "summary", "sensitivity_level",
            "created_at", "embedding_vector", "tags",
        ),
    )

    records = []
    for batch in scan.to_arrow().to_batches():
        for i in range(batch.num_rows):
            embedding_raw = batch.column("embedding_vector")[i].as_py()
            if embedding_raw is None:
                continue

            tags = batch.column("tags")[i].as_py()
            department = tags.get("department", "unknown") if tags else "unknown"

            records.append({
                "file_id": batch.column("file_id")[i].as_py(),
                "file_name": batch.column("file_name")[i].as_py(),
                "file_path": batch.column("file_path")[i].as_py(),
                "file_type": batch.column("file_type")[i].as_py(),
                "classification": batch.column("classification")[i].as_py(),
                "summary": batch.column("summary")[i].as_py(),
                "sensitivity_level": batch.column("sensitivity_level")[i].as_py(),
                "department": department,
                "created_at": str(batch.column("created_at")[i].as_py()),
                "embedding_vector": decode_embedding(embedding_raw),
            })

    return records


def bulk_index(client, records: list, index_name: str):
    """Bulk index records into OpenSearch."""
    if not records:
        return 0

    actions = []
    for record in records:
        actions.append(json.dumps({"index": {"_index": index_name, "_id": record["file_id"]}}))
        actions.append(json.dumps(record))

    body = "\n".join(actions) + "\n"
    response = client.bulk(body=body)

    errors = response.get("errors", False)
    if errors:
        failed = [item for item in response["items"] if "error" in item.get("index", {})]
        logger.warning(f"Bulk index had {len(failed)} errors")

    return len(records)


# =============================================================================
# Search Examples
# =============================================================================


def similarity_search(client, query_embedding: list, index_name: str,
                      k: int = 5, filters: Optional[dict] = None) -> list:
    """
    Perform kNN similarity search.

    Example usage:
        results = similarity_search(client, my_embedding, INDEX_NAME, k=5,
                                    filters={"classification": "contract"})
    """
    query = {
        "size": k,
        "query": {
            "knn": {
                "embedding_vector": {
                    "vector": query_embedding,
                    "k": k,
                }
            }
        },
    }

    if filters:
        query["query"] = {
            "bool": {
                "must": [{"knn": {"embedding_vector": {"vector": query_embedding, "k": k * 2}}}],
                "filter": [{"term": {key: value}} for key, value in filters.items()],
            }
        }

    response = client.search(index=index_name, body=query)
    return [
        {
            "file_id": hit["_source"]["file_id"],
            "file_name": hit["_source"]["file_name"],
            "file_path": hit["_source"]["file_path"],
            "classification": hit["_source"].get("classification"),
            "summary": hit["_source"].get("summary", "")[:100],
            "score": hit["_score"],
        }
        for hit in response["hits"]["hits"]
    ]


# =============================================================================
# CLI
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Sync embeddings to OpenSearch Serverless")
    parser.add_argument("--collection-endpoint", required=True, help="OpenSearch Serverless endpoint")
    parser.add_argument("--table-bucket-arn", required=True, help="S3 Tables table bucket ARN")
    parser.add_argument("--full-sync", action="store_true", help="Full sync (all records)")
    parser.add_argument("--incremental-sync", action="store_true", help="Incremental (new records only)")
    parser.add_argument("--since-hours", type=int, default=24, help="Hours lookback for incremental (default: 24)")
    args = parser.parse_args()

    if not args.full_sync and not args.incremental_sync:
        parser.error("Specify --full-sync or --incremental-sync")

    # Initialize OpenSearch client
    client = get_opensearch_client(args.collection_endpoint)
    create_index_if_not_exists(client, INDEX_NAME)

    # Fetch records
    since = None
    if args.incremental_sync:
        from datetime import timedelta
        since = datetime.now(timezone.utc) - timedelta(hours=args.since_hours)
        logger.info(f"Incremental sync: records since {since}")

    logger.info("Fetching records from S3 Tables...")
    records = fetch_records(args.table_bucket_arn, incremental=args.incremental_sync, since=since)
    logger.info(f"Fetched {len(records)} records with embeddings")

    # Bulk index
    total_indexed = 0
    for i in range(0, len(records), BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        indexed = bulk_index(client, batch, INDEX_NAME)
        total_indexed += indexed
        logger.info(f"Indexed {total_indexed}/{len(records)} records")

    logger.info(f"Sync complete: {total_indexed} records indexed to {INDEX_NAME}")


if __name__ == "__main__":
    main()

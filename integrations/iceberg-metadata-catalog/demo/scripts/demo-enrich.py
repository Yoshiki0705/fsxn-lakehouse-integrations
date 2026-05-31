#!/usr/bin/env python3
"""
demo-enrich.py — AI Enrichment Demo

Processes pending files from S3 Tables metadata with Bedrock AI:
  - Image files: Claude Vision classification
  - All files: Titan Embeddings V2 (1024-dim)

Usage:
    python demo-enrich.py --table-bucket-arn <ARN> --ap-alias <ALIAS> --region ap-northeast-1
"""

import argparse
import base64
import json
import os
import struct
import sys
from datetime import datetime, timezone

import boto3
import pyarrow as pa
from pyiceberg.catalog import load_catalog
from pyiceberg.expressions import EqualTo


def main():
    parser = argparse.ArgumentParser(description="AI Enrichment Demo")
    parser.add_argument("--table-bucket-arn", required=True)
    parser.add_argument("--ap-alias", required=True)
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--max-files", type=int, default=5)
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=args.region)
    bedrock = boto3.client("bedrock-runtime", region_name=args.region)

    catalog = load_catalog("s3tables", **{
        "type": "rest",
        "uri": f"https://s3tables.{args.region}.amazonaws.com/iceberg",
        "warehouse": args.table_bucket_arn,
        "rest.sigv4-enabled": "true",
        "rest.signing-region": args.region,
        "rest.signing-name": "s3tables",
    })

    table = catalog.load_table("metadata.unstructured_files")

    # Fetch pending image files
    scan = table.scan(
        row_filter=EqualTo("enrichment_status", "pending"),
        selected_fields=("file_id", "file_path", "file_name", "file_type", "file_size", "access_point_arn"),
        limit=args.max_files,
    )

    records = []
    for batch in scan.to_arrow().to_batches():
        for i in range(batch.num_rows):
            records.append({
                "file_id": batch.column("file_id")[i].as_py(),
                "file_path": batch.column("file_path")[i].as_py(),
                "file_name": batch.column("file_name")[i].as_py(),
                "file_type": batch.column("file_type")[i].as_py(),
                "file_size": batch.column("file_size")[i].as_py(),
                "access_point_arn": batch.column("access_point_arn")[i].as_py(),
            })

    print(f"  Found {len(records)} pending files for enrichment")

    enriched = 0
    for record in records:
        file_name = record["file_name"]
        file_type = record["file_type"] or ""

        # Determine S3 key from file_path (s3://bucket-or-alias/key)
        # file_path format: s3://<ap-alias>/<key>
        if record["file_path"].startswith("s3://"):
            s3_key = "/".join(record["file_path"].split("/")[3:])
        else:
            s3_key = file_name

        # Classify
        classification = "other"
        summary = f"File: {file_name}"
        confidence = 0.5

        if "image" in file_type:
            try:
                response = s3.get_object(Bucket=args.ap_alias, Key=s3_key)
                image_bytes = response["Body"].read(5_000_000)
                image_b64 = base64.b64encode(image_bytes).decode("utf-8")

                media_type = "image/png" if "png" in file_type else "image/jpeg"
                resp = bedrock.invoke_model(
                    modelId="anthropic.claude-3-haiku-20240307-v1:0",
                    contentType="application/json", accept="application/json",
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 512,
                        "messages": [{"role": "user", "content": [
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
                            {"type": "text", "text": 'Classify this image. Respond JSON only: {"classification":"...","confidence_score":0.X,"summary":"..."}'},
                        ]}],
                    }),
                )
                ai_result = json.loads(json.loads(resp["body"].read())["content"][0]["text"])
                classification = ai_result.get("classification", "other")
                confidence = ai_result.get("confidence_score", 0.5)
                summary = ai_result.get("summary", "")[:500]
                print(f"    🖼️  {file_name}: {classification} (confidence {confidence})")
            except Exception as e:
                print(f"    ⚠️  {file_name}: Vision failed ({e})")
        else:
            print(f"    📄 {file_name}: metadata-only enrichment")

        # Generate embedding
        embed_text = summary if summary else file_name
        try:
            resp = bedrock.invoke_model(
                modelId="amazon.titan-embed-text-v2:0",
                contentType="application/json", accept="application/json",
                body=json.dumps({"inputText": embed_text, "dimensions": 1024, "normalize": True}),
            )
            embedding = json.loads(resp["body"].read())["embedding"]
            embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)
        except Exception as e:
            print(f"    ⚠️  Embedding failed: {e}")
            embedding_bytes = None

        # Write enrichment to S3 Tables
        now = datetime.now(timezone.utc)
        schema = pa.schema([
            pa.field("file_id", pa.string(), nullable=False),
            pa.field("file_path", pa.string(), nullable=False),
            pa.field("file_name", pa.string(), nullable=False),
            pa.field("file_type", pa.string()),
            pa.field("file_size", pa.int64()),
            pa.field("created_at", pa.timestamp("us", tz="UTC")),
            pa.field("modified_at", pa.timestamp("us", tz="UTC")),
            pa.field("source_volume", pa.string()),
            pa.field("source_svm", pa.string()),
            pa.field("access_point_arn", pa.string(), nullable=False),
            pa.field("tags", pa.map_(pa.field("key", pa.string(), nullable=False), pa.field("value", pa.string(), nullable=False))),
            pa.field("classification", pa.string()),
            pa.field("confidence_score", pa.float64()),
            pa.field("sensitivity_level", pa.string()),
            pa.field("summary", pa.string()),
            pa.field("embedding_vector", pa.binary()),
            pa.field("enrichment_status", pa.string()),
            pa.field("enriched_at", pa.timestamp("us", tz="UTC")),
            pa.field("is_deleted", pa.bool_(), nullable=False),
            pa.field("deleted_at", pa.timestamp("us", tz="UTC")),
            pa.field("has_pii", pa.bool_()),
            pa.field("anonymized_path", pa.string()),
            pa.field("anonymization_status", pa.string()),
        ])

        arrow_table = pa.table({
            "file_id": [record["file_id"]],
            "file_path": [record["file_path"]],
            "file_name": [file_name],
            "file_type": [record["file_type"]],
            "file_size": [record["file_size"]],
            "created_at": [None],
            "modified_at": [now],
            "source_volume": [None],
            "source_svm": [None],
            "access_point_arn": [record["access_point_arn"]],
            "tags": [None],
            "classification": [classification],
            "confidence_score": [confidence],
            "sensitivity_level": ["internal"],
            "summary": [summary],
            "embedding_vector": [embedding_bytes],
            "enrichment_status": ["completed"],
            "enriched_at": [now],
            "is_deleted": [False],
            "deleted_at": [None],
            "has_pii": [None],
            "anonymized_path": [None],
            "anonymization_status": [None],
        }, schema=schema)

        try:
            table.append(arrow_table)
            enriched += 1
        except Exception as e:
            print(f"    ⚠️  Write failed: {e}")

    print(f"\n  ✅ Enriched {enriched}/{len(records)} files")


if __name__ == "__main__":
    main()

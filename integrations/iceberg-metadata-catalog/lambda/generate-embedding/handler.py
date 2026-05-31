"""
generate-embedding — Vector Embedding Generation Lambda

Generates a 1024-dimension vector embedding from text using Amazon Titan Embeddings V2.
Used for similarity search across the metadata catalog.

Input text sources:
  - Documents: AI-generated summary
  - Images: AI-generated description
  - Audio/Video: Transcription or scene description
  - Other: File name (fallback)

Environment Variables:
    EMBEDDING_MODEL_ID  - Bedrock embedding model (default: amazon.titan-embed-text-v2:0)
    AWS_REGION          - AWS region
"""

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

EMBEDDING_MODEL_ID = os.environ.get(
    "EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
)
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
EMBEDDING_DIMENSIONS = 1024  # Titan V2 supports 256, 512, 1024


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Generate vector embedding for a text input.

    Input:
        file_id: str
        file_name: str
        text: str (summary, description, or file name as fallback)

    Output:
        embedding: str (base64-encoded binary)
        dimensions: int
        model_id: str
    """
    file_id = event["file_id"]
    file_name = event.get("file_name", "")
    text = event.get("text", "")

    # Fallback to file name if no text provided
    if not text or text.strip() == "":
        text = file_name
        logger.info(f"No text provided for {file_id}, using file_name: {file_name}")

    # Truncate to Titan Embeddings input limit (~8K tokens ≈ 32K chars)
    if len(text) > 30000:
        text = text[:30000]

    logger.info(f"Generating embedding for {file_id} ({len(text)} chars)")

    # Call Bedrock Titan Embeddings
    bedrock_client = boto3.client("bedrock-runtime", region_name=REGION)

    try:
        response = bedrock_client.invoke_model(
            modelId=EMBEDDING_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "inputText": text,
                "dimensions": EMBEDDING_DIMENSIONS,
                "normalize": True,
            }),
        )

        response_body = json.loads(response["body"].read())
        embedding_vector = response_body["embedding"]

        # Convert float list to bytes for Iceberg BINARY column storage
        import struct
        embedding_bytes = struct.pack(f"{len(embedding_vector)}f", *embedding_vector)
        import base64
        embedding_b64 = base64.b64encode(embedding_bytes).decode("utf-8")

        return {
            "embedding": embedding_b64,
            "dimensions": EMBEDDING_DIMENSIONS,
            "model_id": EMBEDDING_MODEL_ID,
        }

    except Exception as e:
        logger.error(f"Embedding generation failed for {file_id}: {e}")
        raise

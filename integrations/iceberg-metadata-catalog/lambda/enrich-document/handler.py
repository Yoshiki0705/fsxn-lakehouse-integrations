"""
enrich-document — Document AI Enrichment Lambda

Reads a document (PDF, Word, text) from FSx for ONTAP S3 AP and generates:
  - Summary (2-3 sentences)
  - Classification (contract, invoice, report, manual, specification, other)
  - Key entities (people, organizations, dates, amounts)

Uses Amazon Bedrock Claude for summarization and classification.

Environment Variables:
    BEDROCK_MODEL_ID  - Bedrock model (default: anthropic.claude-3-haiku-20240307-v1:0)
    AWS_REGION        - AWS region
"""

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
)
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
MAX_DOCUMENT_BYTES = 50_000  # ~50KB text limit for Bedrock input

# Classification taxonomy
CLASSIFICATION_CATEGORIES = [
    "contract",
    "invoice",
    "report",
    "manual",
    "specification",
    "correspondence",
    "presentation",
    "spreadsheet",
    "other",
]


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Enrich a document file with AI-generated metadata.

    Input:
        file_id: str
        file_path: str (s3://ap-arn/key)
        file_type: str
        access_point_arn: str

    Output:
        classification: str
        confidence_score: float
        summary: str
        entities: dict
    """
    file_id = event["file_id"]
    file_path = event["file_path"]
    access_point_arn = event["access_point_arn"]

    logger.info(f"Processing document: {file_path}")

    # Extract S3 key from file_path
    # Format: s3://arn:aws:s3:region:account:accesspoint/name/key
    s3_key = "/".join(file_path.split("/")[4:])  # After ap-name

    # Read document from FSx for ONTAP S3 AP
    s3_client = boto3.client("s3", region_name=REGION)
    try:
        response = s3_client.get_object(Bucket=access_point_arn, Key=s3_key)
        content_bytes = response["Body"].read(MAX_DOCUMENT_BYTES)
        # Attempt UTF-8 decode; fall back to latin-1
        try:
            document_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            document_text = content_bytes.decode("latin-1")
    except Exception as e:
        logger.error(f"Failed to read document {file_path}: {e}")
        raise

    if not document_text.strip():
        return {
            "classification": "other",
            "confidence_score": 0.0,
            "summary": "Empty or binary document — no text content extracted.",
            "entities": {},
        }

    # Truncate for Bedrock input
    if len(document_text) > 10000:
        document_text = document_text[:10000] + "\n[... truncated ...]"

    # Call Bedrock for classification and summarization
    bedrock_client = boto3.client("bedrock-runtime", region_name=REGION)

    prompt = f"""Analyze the following document and provide:
1. Classification: Choose exactly one from [{', '.join(CLASSIFICATION_CATEGORIES)}]
2. Confidence: A score from 0.0 to 1.0 indicating classification confidence
3. Summary: A 2-3 sentence summary of the document content
4. Entities: Key entities found (people, organizations, dates, monetary amounts)

Respond in JSON format only:
{{"classification": "...", "confidence_score": 0.X, "summary": "...", "entities": {{"people": [], "organizations": [], "dates": [], "amounts": []}}}}

Document:
{document_text}"""

    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
            }),
        )

        response_body = json.loads(response["body"].read())
        ai_text = response_body["content"][0]["text"]

        # Parse JSON response from AI
        # Handle potential markdown code blocks
        if "```json" in ai_text:
            ai_text = ai_text.split("```json")[1].split("```")[0]
        elif "```" in ai_text:
            ai_text = ai_text.split("```")[1].split("```")[0]

        result = json.loads(ai_text.strip())

        # Validate classification
        classification = result.get("classification", "other")
        if classification not in CLASSIFICATION_CATEGORIES:
            classification = "other"

        confidence = min(max(float(result.get("confidence_score", 0.5)), 0.0), 1.0)

        return {
            "classification": classification,
            "confidence_score": confidence,
            "summary": result.get("summary", "")[:500],
            "entities": result.get("entities", {}),
        }

    except json.JSONDecodeError:
        logger.warning(f"Failed to parse AI response as JSON for {file_id}")
        return {
            "classification": "other",
            "confidence_score": 0.3,
            "summary": document_text[:200],
            "entities": {},
        }
    except Exception as e:
        logger.error(f"Bedrock invocation failed for {file_id}: {e}")
        raise

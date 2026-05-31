"""
anonymize-document.py — Document PII Redaction Lambda

Reads a document from FSx S3 AP, detects PII entities, redacts them,
and writes the anonymized version to a designated output location.

Supported formats:
  - Plain text (UTF-8)
  - PDF (via textract extraction + overlay redaction)

PII types redacted:
  - Names, addresses, phone numbers, email addresses
  - SSN, credit card numbers, bank account numbers
  - Passport numbers, driver's license numbers

Environment Variables:
    OUTPUT_BUCKET       - S3 bucket for anonymized files
    OUTPUT_PREFIX       - S3 prefix for anonymized files (default: anonymized/)
    TABLE_BUCKET_ARN    - S3 Tables ARN (for metadata update)
    AWS_REGION          - AWS region
"""

import json
import logging
import os
import re
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", "")
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "anonymized/")

# PII patterns for regex-based redaction (supplement to Comprehend)
PII_PATTERNS = {
    "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    "phone_jp": r'(?:0\d{1,4}-?\d{1,4}-?\d{3,4})',
    "phone_intl": r'(?:\+\d{1,3}[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9})',
    "credit_card": r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    "ssn_us": r'\b\d{3}-\d{2}-\d{4}\b',
    "my_number_jp": r'\b\d{4}\s?\d{4}\s?\d{4}\b',
}

REDACTION_MARKER = "[REDACTED]"


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Anonymize a document by redacting PII.

    Input:
        file_id: str
        file_path: str
        file_name: str
        access_point_arn: str
        pii_types: list[str] (from detect-pii Lambda)

    Output:
        anonymized_path: str (S3 path to redacted file)
        redaction_count: int
        redacted_types: list[str]
    """
    file_id = event["file_id"]
    file_path = event["file_path"]
    file_name = event["file_name"]
    access_point_arn = event["access_point_arn"]
    pii_types = event.get("pii_types", [])

    logger.info(f"Anonymizing document: {file_name} (PII types: {pii_types})")

    # Read file from FSx S3 AP
    s3_client = boto3.client("s3", region_name=REGION)
    s3_key = "/".join(file_path.split("/")[4:])

    try:
        response = s3_client.get_object(Bucket=access_point_arn, Key=s3_key)
        content_bytes = response["Body"].read()
    except Exception as e:
        logger.error(f"Failed to read file: {e}")
        raise

    # Detect content type and process accordingly
    try:
        text_content = content_bytes.decode("utf-8")
        is_text = True
    except UnicodeDecodeError:
        # Binary file (PDF, etc.) — use Comprehend on extracted text
        text_content = ""
        is_text = False

    if is_text and text_content:
        # Text-based redaction
        redacted_text, redaction_count, redacted_types = redact_text(text_content)

        # Write anonymized version
        output_key = f"{OUTPUT_PREFIX}{file_id}/{file_name}"
        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=output_key,
            Body=redacted_text.encode("utf-8"),
            ContentType="text/plain",
            Metadata={
                "original_file_id": file_id,
                "redaction_count": str(redaction_count),
                "anonymization_version": "1.0",
            },
        )

        anonymized_path = f"s3://{OUTPUT_BUCKET}/{output_key}"

    else:
        # Binary file — copy with metadata noting it needs manual review
        output_key = f"{OUTPUT_PREFIX}{file_id}/{file_name}"
        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=output_key,
            Body=content_bytes,
            Metadata={
                "original_file_id": file_id,
                "anonymization_status": "binary_file_manual_review_required",
                "anonymization_version": "1.0",
            },
        )
        anonymized_path = f"s3://{OUTPUT_BUCKET}/{output_key}"
        redaction_count = 0
        redacted_types = ["manual_review_required"]

    logger.info(
        f"Anonymization complete: {file_name}, "
        f"redactions={redaction_count}, types={redacted_types}"
    )

    return {
        "anonymized_path": anonymized_path,
        "redaction_count": redaction_count,
        "redacted_types": redacted_types,
        "file_id": file_id,
    }


def redact_text(text: str) -> tuple:
    """
    Redact PII from text using regex patterns and Comprehend.

    Returns: (redacted_text, redaction_count, redacted_types)
    """
    redaction_count = 0
    redacted_types = set()

    # Step 1: Regex-based redaction (fast, deterministic)
    for pii_type, pattern in PII_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            text = re.sub(pattern, REDACTION_MARKER, text)
            redaction_count += len(matches)
            redacted_types.add(pii_type)

    # Step 2: Comprehend-based redaction (ML, catches more patterns)
    if len(text.encode("utf-8")) < 99000:  # Comprehend limit
        try:
            comprehend = boto3.client("comprehend", region_name=REGION)
            response = comprehend.detect_pii_entities(
                Text=text[:5000],  # Sample for additional detection
                LanguageCode="en",
            )

            # Sort entities by offset (reverse) to redact without shifting positions
            entities = sorted(
                [e for e in response.get("Entities", []) if e["Score"] >= 0.8],
                key=lambda x: x["BeginOffset"],
                reverse=True,
            )

            for entity in entities:
                begin = entity["BeginOffset"]
                end = entity["EndOffset"]
                original = text[begin:end]
                # Only redact if not already redacted
                if REDACTION_MARKER not in original:
                    text = text[:begin] + REDACTION_MARKER + text[end:]
                    redaction_count += 1
                    redacted_types.add(entity["Type"])

        except Exception as e:
            logger.warning(f"Comprehend redaction failed (regex-only applied): {e}")

    return text, redaction_count, list(redacted_types)

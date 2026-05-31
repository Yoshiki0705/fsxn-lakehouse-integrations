"""
detect-pii — PII Detection Lambda

Detects Personally Identifiable Information (PII) in text content
using Amazon Comprehend.

Sets has_pii flag and identifies PII types found.

Environment Variables:
    AWS_REGION        - AWS region
    LANGUAGE_CODE     - Comprehend language (default: en)
"""

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
LANGUAGE_CODE = os.environ.get("LANGUAGE_CODE", "en")

# PII entity types that indicate sensitive data
SENSITIVE_PII_TYPES = {
    "SSN", "CREDIT_DEBIT_NUMBER", "BANK_ACCOUNT_NUMBER",
    "PASSPORT_NUMBER", "DRIVER_ID", "PHONE", "EMAIL",
    "ADDRESS", "DATE_TIME", "NAME", "AGE",
}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Detect PII in text content.

    Input:
        file_id: str
        text: str (document summary or extracted text)
        file_type: str

    Output:
        has_pii: bool
        pii_types: list[str]
        pii_count: int
    """
    file_id = event["file_id"]
    text = event.get("text", "")
    file_type = event.get("file_type", "")

    if not text or len(text.strip()) < 10:
        logger.info(f"Insufficient text for PII detection: {file_id}")
        return {
            "has_pii": False,
            "pii_types": [],
            "pii_count": 0,
        }

    # Truncate to Comprehend limit (100KB UTF-8)
    if len(text.encode("utf-8")) > 99000:
        text = text[:25000]

    logger.info(f"Detecting PII for {file_id} ({len(text)} chars)")

    comprehend_client = boto3.client("comprehend", region_name=REGION)

    try:
        # Detect PII entities
        response = comprehend_client.detect_pii_entities(
            Text=text,
            LanguageCode=LANGUAGE_CODE,
        )

        entities = response.get("Entities", [])

        # Filter to sensitive PII types with high confidence
        sensitive_entities = [
            e for e in entities
            if e["Type"] in SENSITIVE_PII_TYPES and e["Score"] >= 0.8
        ]

        pii_types = list(set(e["Type"] for e in sensitive_entities))
        has_pii = len(sensitive_entities) > 0

        logger.info(
            f"PII detection for {file_id}: has_pii={has_pii}, "
            f"types={pii_types}, count={len(sensitive_entities)}"
        )

        return {
            "has_pii": has_pii,
            "pii_types": pii_types,
            "pii_count": len(sensitive_entities),
        }

    except comprehend_client.exceptions.TextSizeLimitExceededException:
        logger.warning(f"Text too large for Comprehend: {file_id}")
        # Retry with truncated text
        truncated = text[:5000]
        response = comprehend_client.detect_pii_entities(
            Text=truncated,
            LanguageCode=LANGUAGE_CODE,
        )
        entities = response.get("Entities", [])
        sensitive = [e for e in entities if e["Type"] in SENSITIVE_PII_TYPES and e["Score"] >= 0.8]
        return {
            "has_pii": len(sensitive) > 0,
            "pii_types": list(set(e["Type"] for e in sensitive)),
            "pii_count": len(sensitive),
        }

    except Exception as e:
        logger.error(f"PII detection failed for {file_id}: {e}")
        raise

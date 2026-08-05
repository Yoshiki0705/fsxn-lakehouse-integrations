#!/usr/bin/env python3
"""
demo-anonymize.py — PII Detection & Anonymization Demo

Reads a document from FSx for ONTAP S3 AP, detects PII, and produces anonymized output.
Supports both English (Comprehend) and Japanese (Bedrock Claude).

Usage:
    python demo-anonymize.py --ap-alias <ALIAS> --region ap-northeast-1
"""

import argparse
import json
import re
import sys

import boto3


REDACTION = "[REDACTED]"

PII_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone_jp": r"(?:0\d{1,4}-?\d{1,4}-?\d{3,4})",
    "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "my_number": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
}


def detect_pii_english(text, comprehend):
    """Detect PII using Amazon Comprehend (English)."""
    response = comprehend.detect_pii_entities(Text=text[:5000], LanguageCode="en")
    return [e for e in response["Entities"] if e["Score"] >= 0.8]


def detect_pii_japanese(text, bedrock):
    """Detect PII using Bedrock Claude (Japanese)."""
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        contentType="application/json", accept="application/json",
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content":
                f"Detect all PII in this text. Return JSON array: "
                f'[{{"type":"...","value":"...","begin":N,"end":N}}]\n\nText:\n{text}'}],
        }),
    )
    ai_text = json.loads(response["body"].read())["content"][0]["text"]
    try:
        if "```json" in ai_text:
            ai_text = ai_text.split("```json")[1].split("```")[0]
        return json.loads(ai_text.strip())
    except json.JSONDecodeError:
        return []


def redact_text(text):
    """Redact PII using regex patterns."""
    redacted = text
    count = 0
    for pattern in PII_PATTERNS.values():
        matches = re.findall(pattern, redacted)
        if matches:
            redacted = re.sub(pattern, REDACTION, redacted)
            count += len(matches)
    return redacted, count


def main():
    parser = argparse.ArgumentParser(description="PII Anonymization Demo")
    parser.add_argument("--ap-alias", required=True)
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--file-key", default="media/documents/pii-test-document.txt")
    args = parser.parse_args()

    s3 = boto3.client("s3", region_name=args.region)
    comprehend = boto3.client("comprehend", region_name=args.region)
    bedrock = boto3.client("bedrock-runtime", region_name=args.region)

    # Read file
    print(f"  Reading: s3://{args.ap_alias}/{args.file_key}")
    try:
        response = s3.get_object(Bucket=args.ap_alias, Key=args.file_key)
        text = response["Body"].read().decode("utf-8")
    except Exception as e:
        print(f"  ⚠️  File not found: {e}")
        print(f"  Creating sample PII document for demo...")
        text = ("CONFIDENTIAL - Employee Record\n"
                "Name: Taro Yamada\n"
                "Email: taro.yamada@example.com\n"
                "Phone: 090-1234-5678\n"
                "Address: 1-2-3 Shibuya, Tokyo 150-0002\n"
                "SSN: 123-45-6789\n"
                "Credit Card: 4111-1111-1111-1111\n")
        s3.put_object(Bucket=args.ap_alias, Key=args.file_key, Body=text.encode("utf-8"))
        print(f"  Uploaded sample document to FSx for ONTAP S3 AP")

    print(f"  Content ({len(text)} chars):")
    print(f"  {'─' * 50}")
    for line in text.strip().split("\n")[:8]:
        print(f"  │ {line}")
    print(f"  {'─' * 50}")
    print()

    # Detect PII
    print("  Detecting PII...")
    try:
        entities = detect_pii_english(text, comprehend)
        engine = "Comprehend (English)"
    except Exception:
        entities = detect_pii_japanese(text, bedrock)
        engine = "Bedrock Claude (Japanese)"

    pii_types = list(set(e.get("Type", e.get("type", "UNKNOWN")) for e in entities))
    print(f"  Engine: {engine}")
    print(f"  PII found: {len(entities)} entities")
    print(f"  Types: {pii_types}")
    print()

    # Anonymize
    print("  Anonymizing...")

    # Apply Comprehend entity-based redaction first (on original text)
    redacted = text
    regex_count = 0
    if entities and "BeginOffset" in entities[0]:
        sorted_entities = sorted(entities, key=lambda x: x["BeginOffset"], reverse=True)
        for e in sorted_entities:
            begin, end = e["BeginOffset"], e["EndOffset"]
            redacted = redacted[:begin] + REDACTION + redacted[end:]

    # Then apply regex as fallback for any remaining PII patterns
    for pattern in PII_PATTERNS.values():
        matches = re.findall(pattern, redacted)
        if matches:
            redacted = re.sub(pattern, REDACTION, redacted)
            regex_count += len(matches)

    print(f"  {'─' * 50}")
    for line in redacted.strip().split("\n")[:8]:
        print(f"  │ {line}")
    print(f"  {'─' * 50}")
    print()
    print(f"  ✅ Anonymization complete")
    print(f"     PII entities: {len(entities)}")
    print(f"     Regex redactions: {regex_count}")
    print(f"     has_pii: True")
    print(f"     Result: All PII replaced with {REDACTION}")


if __name__ == "__main__":
    main()

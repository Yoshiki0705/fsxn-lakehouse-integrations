"""
enrich-image — Image AI Enrichment Lambda

Reads an image from FSx for ONTAP S3 AP and generates:
  - Description (what the image shows)
  - Classification (product_photo, medical_image, blueprint, satellite, screenshot, other)
  - Detected objects/elements

Uses Amazon Bedrock Claude Vision for image understanding.

Environment Variables:
    BEDROCK_MODEL_ID  - Bedrock model (default: anthropic.claude-3-haiku-20240307-v1:0)
    AWS_REGION        - AWS region
"""

import base64
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
MAX_IMAGE_BYTES = 5_000_000  # 5MB limit for Bedrock Vision

IMAGE_CLASSIFICATION_CATEGORIES = [
    "product_photo",
    "medical_image",
    "blueprint",
    "satellite",
    "screenshot",
    "diagram",
    "photograph",
    "scan",
    "other",
]

# MIME type to Bedrock media_type mapping
MEDIA_TYPE_MAP = {
    "image/jpeg": "image/jpeg",
    "image/png": "image/png",
    "image/gif": "image/gif",
    "image/webp": "image/webp",
    "image/tiff": "image/png",  # Convert needed
    "image/bmp": "image/png",   # Convert needed
}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Enrich an image file with AI-generated metadata.

    Input:
        file_id: str
        file_path: str
        file_type: str
        access_point_arn: str

    Output:
        classification: str
        confidence_score: float
        summary: str (image description)
    """
    file_id = event["file_id"]
    file_path = event["file_path"]
    file_type = event.get("file_type", "image/jpeg")
    access_point_arn = event["access_point_arn"]

    logger.info(f"Processing image: {file_path}")

    # Extract S3 key
    s3_key = "/".join(file_path.split("/")[4:])

    # Read image from FSx for ONTAP S3 AP
    s3_client = boto3.client("s3", region_name=REGION)
    try:
        response = s3_client.get_object(Bucket=access_point_arn, Key=s3_key)
        image_bytes = response["Body"].read(MAX_IMAGE_BYTES)
    except Exception as e:
        logger.error(f"Failed to read image {file_path}: {e}")
        raise

    # Determine media type for Bedrock
    media_type = MEDIA_TYPE_MAP.get(file_type, "image/jpeg")

    # Encode image as base64
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Call Bedrock Vision
    bedrock_client = boto3.client("bedrock-runtime", region_name=REGION)

    prompt = f"""Analyze this image and provide:
1. Classification: Choose exactly one from [{', '.join(IMAGE_CLASSIFICATION_CATEGORIES)}]
2. Confidence: A score from 0.0 to 1.0
3. Description: A 2-3 sentence description of what the image shows
4. Objects: Key objects or elements visible in the image

Respond in JSON format only:
{{"classification": "...", "confidence_score": 0.X, "summary": "...", "objects": ["..."]}}"""

    try:
        response = bedrock_client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_b64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            }),
        )

        response_body = json.loads(response["body"].read())
        ai_text = response_body["content"][0]["text"]

        # Parse JSON
        if "```json" in ai_text:
            ai_text = ai_text.split("```json")[1].split("```")[0]
        elif "```" in ai_text:
            ai_text = ai_text.split("```")[1].split("```")[0]

        result = json.loads(ai_text.strip())

        classification = result.get("classification", "other")
        if classification not in IMAGE_CLASSIFICATION_CATEGORIES:
            classification = "other"

        confidence = min(max(float(result.get("confidence_score", 0.5)), 0.0), 1.0)

        return {
            "classification": classification,
            "confidence_score": confidence,
            "summary": result.get("summary", "")[:500],
        }

    except json.JSONDecodeError:
        logger.warning(f"Failed to parse AI response for image {file_id}")
        return {
            "classification": "other",
            "confidence_score": 0.3,
            "summary": f"Image file: {os.path.basename(file_path)}",
        }
    except Exception as e:
        logger.error(f"Bedrock Vision failed for {file_id}: {e}")
        raise

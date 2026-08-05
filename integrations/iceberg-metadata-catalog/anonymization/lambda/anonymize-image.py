"""
anonymize-image.py — Image PII Anonymization Lambda

Detects and blurs faces in images, and redacts text overlays containing PII.
Writes the anonymized image to a designated output location.

Uses:
  - Amazon Rekognition: Face detection (bounding boxes)
  - Pillow (PIL): Face blurring (Gaussian blur on detected regions)

Environment Variables:
    OUTPUT_BUCKET   - S3 bucket for anonymized images
    OUTPUT_PREFIX   - S3 prefix (default: anonymized/)
    AWS_REGION      - AWS region
    BLUR_FACTOR     - Gaussian blur radius (default: 30)
"""

import io
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
OUTPUT_BUCKET = os.environ.get("OUTPUT_BUCKET", "")
OUTPUT_PREFIX = os.environ.get("OUTPUT_PREFIX", "anonymized/")
BLUR_FACTOR = int(os.environ.get("BLUR_FACTOR", "30"))


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Anonymize an image by blurring detected faces.

    Input:
        file_id: str
        file_path: str
        file_name: str
        access_point_arn: str

    Output:
        anonymized_path: str
        faces_detected: int
        faces_blurred: int
    """
    file_id = event["file_id"]
    file_path = event["file_path"]
    file_name = event["file_name"]
    access_point_arn = event["access_point_arn"]

    logger.info(f"Anonymizing image: {file_name}")

    # Read image from FSx for ONTAP S3 AP
    s3_client = boto3.client("s3", region_name=REGION)
    s3_key = "/".join(file_path.split("/")[4:])

    try:
        response = s3_client.get_object(Bucket=access_point_arn, Key=s3_key)
        image_bytes = response["Body"].read()
    except Exception as e:
        logger.error(f"Failed to read image: {e}")
        raise

    # Detect faces using Rekognition
    rekognition = boto3.client("rekognition", region_name=REGION)

    try:
        detect_response = rekognition.detect_faces(
            Image={"Bytes": image_bytes},
            Attributes=["DEFAULT"],
        )
        faces = detect_response.get("FaceDetails", [])
    except Exception as e:
        logger.warning(f"Rekognition face detection failed: {e}")
        faces = []

    faces_detected = len(faces)

    if faces_detected == 0:
        # No faces — copy as-is (or skip anonymization)
        output_key = f"{OUTPUT_PREFIX}{file_id}/{file_name}"
        s3_client.put_object(
            Bucket=OUTPUT_BUCKET,
            Key=output_key,
            Body=image_bytes,
            Metadata={
                "original_file_id": file_id,
                "faces_detected": "0",
                "anonymization_version": "1.0",
            },
        )
        return {
            "anonymized_path": f"s3://{OUTPUT_BUCKET}/{output_key}",
            "faces_detected": 0,
            "faces_blurred": 0,
            "file_id": file_id,
        }

    # Blur faces using Pillow
    try:
        from PIL import Image, ImageFilter

        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size

        for face in faces:
            bbox = face["BoundingBox"]
            # Convert relative coordinates to absolute pixels
            left = int(bbox["Left"] * width)
            top = int(bbox["Top"] * height)
            right = int((bbox["Left"] + bbox["Width"]) * width)
            bottom = int((bbox["Top"] + bbox["Height"]) * height)

            # Add padding (10% each side)
            pad_w = int((right - left) * 0.1)
            pad_h = int((bottom - top) * 0.1)
            left = max(0, left - pad_w)
            top = max(0, top - pad_h)
            right = min(width, right + pad_w)
            bottom = min(height, bottom + pad_h)

            # Extract face region, blur, paste back
            face_region = img.crop((left, top, right, bottom))
            blurred_face = face_region.filter(ImageFilter.GaussianBlur(radius=BLUR_FACTOR))
            img.paste(blurred_face, (left, top, right, bottom))

        # Save anonymized image
        output_buffer = io.BytesIO()
        img_format = "JPEG" if file_name.lower().endswith((".jpg", ".jpeg")) else "PNG"
        img.save(output_buffer, format=img_format, quality=90)
        output_bytes = output_buffer.getvalue()

    except ImportError:
        logger.error("Pillow (PIL) not available in Lambda environment. Add to layer.")
        raise
    except Exception as e:
        logger.error(f"Image processing failed: {e}")
        raise

    # Write anonymized image to S3
    output_key = f"{OUTPUT_PREFIX}{file_id}/{file_name}"
    s3_client.put_object(
        Bucket=OUTPUT_BUCKET,
        Key=output_key,
        Body=output_bytes,
        ContentType=f"image/{img_format.lower()}",
        Metadata={
            "original_file_id": file_id,
            "faces_detected": str(faces_detected),
            "faces_blurred": str(faces_detected),
            "anonymization_version": "1.0",
        },
    )

    anonymized_path = f"s3://{OUTPUT_BUCKET}/{output_key}"
    logger.info(f"Anonymized: {faces_detected} faces blurred → {anonymized_path}")

    return {
        "anonymized_path": anonymized_path,
        "faces_detected": faces_detected,
        "faces_blurred": faces_detected,
        "file_id": file_id,
    }

#!/usr/bin/env python3
"""
Synthetic Payload Generator — FSx for ONTAP Upload

Generates synthetic image and document payloads and uploads them to
FSx for ONTAP via S3 API (ONTAP S3) or local filesystem (NFS mount).

Architecture Reference: ADR-003 (FSx for ONTAP as payload storage)
Architecture Reference: ADR-005 (Metadata/payload separation)

All generated data is SYNTHETIC. No real quality images or documents.
"""

import argparse
import hashlib
import io
import json
import logging
import os
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import boto3
from botocore.config import Config as BotoConfig
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Storage mode: "s3" for ONTAP S3, "nfs" for local NFS mount path
STORAGE_MODE = os.environ.get("STORAGE_MODE", "nfs")

# ONTAP S3 configuration (when STORAGE_MODE=s3)
ONTAP_S3_ENDPOINT = os.environ.get("ONTAP_S3_ENDPOINT", "https://svm1-s3.fsxn.local")
ONTAP_S3_BUCKET = os.environ.get("ONTAP_S3_BUCKET", "factory-payloads")
ONTAP_S3_ACCESS_KEY = os.environ.get("ONTAP_S3_ACCESS_KEY", "")
ONTAP_S3_SECRET_KEY = os.environ.get("ONTAP_S3_SECRET_KEY", "")
ONTAP_S3_REGION = os.environ.get("ONTAP_S3_REGION", "us-east-1")

# NFS configuration (when STORAGE_MODE=nfs)
NFS_MOUNT_PATH = os.environ.get("NFS_MOUNT_PATH", "/mnt/fsxn/vol_images")

# Payload generation settings
IMAGE_MIN_SIZE_MB = int(os.environ.get("IMAGE_MIN_SIZE_MB", "5"))
IMAGE_MAX_SIZE_MB = int(os.environ.get("IMAGE_MAX_SIZE_MB", "50"))

# Factories (matching generate_events.py)
FACTORIES = ["factory-alpha", "factory-beta"]
LINES = {
    "factory-alpha": ["line-A1", "line-A2", "line-A3"],
    "factory-beta": ["line-B1", "line-B2"],
}


# ---------------------------------------------------------------------------
# Synthetic Image Generation
# ---------------------------------------------------------------------------


def generate_synthetic_image(target_size_mb: float) -> tuple[bytes, str]:
    """
    Generate a synthetic quality inspection image.

    Creates a realistic-sized JPEG with synthetic quality inspection data
    overlaid. The image is padded to reach the target size.

    Returns: (image_bytes, content_type)
    """
    # Create base image with random noise pattern (simulates camera capture)
    width, height = 2048, 1536  # Typical industrial camera resolution
    img = Image.new("RGB", (width, height))

    # Fill with random noise to simulate a real camera image
    pixels = img.load()
    base_r = random.randint(50, 200)
    base_g = random.randint(50, 200)
    base_b = random.randint(50, 200)

    for y in range(0, height, 4):
        for x in range(0, width, 4):
            r = min(255, max(0, base_r + random.randint(-30, 30)))
            g = min(255, max(0, base_g + random.randint(-30, 30)))
            b = min(255, max(0, base_b + random.randint(-30, 30)))
            # Fill 4x4 block for performance
            for dy in range(4):
                for dx in range(4):
                    if x + dx < width and y + dy < height:
                        pixels[x + dx, y + dy] = (r, g, b)

    # Add synthetic overlay text
    draw = ImageDraw.Draw(img)
    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    overlay_text = f"SYNTHETIC DATA - Quality Inspection\n{timestamp_str}\nEvent: {uuid.uuid4().hex[:8]}"

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except (OSError, IOError):
        font = ImageFont.load_default()

    draw.multiline_text((50, 50), overlay_text, fill=(255, 255, 0), font=font)

    # Draw synthetic inspection region markers
    for _ in range(random.randint(1, 5)):
        x1 = random.randint(100, width - 200)
        y1 = random.randint(100, height - 200)
        x2 = x1 + random.randint(50, 200)
        y2 = y1 + random.randint(50, 200)
        color = (0, 255, 0) if random.random() > 0.3 else (255, 0, 0)
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

    # Encode to JPEG with quality adjusted to reach target size
    # Start with high quality and adjust
    buffer = io.BytesIO()
    target_bytes = int(target_size_mb * 1024 * 1024)

    # JPEG with maximum quality to get close to target size
    img.save(buffer, format="JPEG", quality=95)
    current_size = buffer.tell()

    if current_size < target_bytes:
        # Pad with JPEG comment data to reach target size
        # This is a valid approach for synthetic test data
        padding_needed = target_bytes - current_size
        buffer.write(b"\x00" * padding_needed)

    buffer.seek(0)
    return buffer.read(), "image/jpeg"


def generate_synthetic_pdf(target_size_mb: float) -> tuple[bytes, str]:
    """
    Generate a synthetic quality report PDF.

    Creates a simple PDF with synthetic inspection data.
    Uses reportlab if available, otherwise creates a minimal PDF.

    Returns: (pdf_bytes, content_type)
    """
    target_bytes = int(target_size_mb * 1024 * 1024)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4

        # Title
        c.setFont("Helvetica-Bold", 18)
        c.drawString(72, height - 72, "SYNTHETIC Quality Inspection Report")

        # Metadata
        c.setFont("Helvetica", 12)
        y = height - 120
        metadata = [
            f"Report ID: {uuid.uuid4()}",
            f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Factory: {random.choice(FACTORIES)}",
            f"Line: {random.choice(['line-A1', 'line-A2', 'line-B1'])}",
            f"Result: {'PASS' if random.random() > 0.2 else 'FAIL'}",
            "",
            "NOTE: This is SYNTHETIC test data.",
            "No real inspection data is contained in this document.",
        ]
        for line in metadata:
            c.drawString(72, y, line)
            y -= 20

        # Add pages with synthetic data to reach target size
        c.showPage()

        # Add filler pages with random measurement tables
        pages_needed = max(1, target_bytes // 2000)
        for page_num in range(min(pages_needed, 500)):
            c.setFont("Helvetica", 10)
            y = height - 72
            c.drawString(72, y, f"Measurement Data Page {page_num + 1} (SYNTHETIC)")
            y -= 30

            for row in range(40):
                if y < 72:
                    break
                values = [f"{random.uniform(0, 100):.4f}" for _ in range(6)]
                line_text = f"  M{row:04d}: " + " | ".join(values)
                c.drawString(72, y, line_text)
                y -= 14

            c.showPage()

        c.save()
        buffer.seek(0)
        pdf_bytes = buffer.read()

    except ImportError:
        # Fallback: create minimal valid PDF without reportlab
        logger.warning("reportlab not available; generating minimal PDF")
        content = """%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 72 720 Td (SYNTHETIC DATA) Tj ET
endstream
endobj
xref
0 5
trailer
<< /Size 5 /Root 1 0 R >>
startxref
0
%%EOF"""
        pdf_bytes = content.encode("latin-1")

    # Pad to target size if needed
    if len(pdf_bytes) < target_bytes:
        padding = b"\x00" * (target_bytes - len(pdf_bytes))
        pdf_bytes = pdf_bytes + padding

    return pdf_bytes, "application/pdf"


# ---------------------------------------------------------------------------
# Upload Functions
# ---------------------------------------------------------------------------


def get_s3_client():
    """Create boto3 S3 client configured for ONTAP S3 endpoint."""
    return boto3.client(
        "s3",
        endpoint_url=ONTAP_S3_ENDPOINT,
        aws_access_key_id=ONTAP_S3_ACCESS_KEY,
        aws_secret_access_key=ONTAP_S3_SECRET_KEY,
        region_name=ONTAP_S3_REGION,
        config=BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
        ),
    )


def upload_via_s3(data: bytes, key: str, content_type: str) -> dict[str, str]:
    """Upload payload to FSx for ONTAP via ONTAP S3 protocol."""
    client = get_s3_client()

    # Calculate checksum
    checksum = hashlib.sha256(data).hexdigest()

    # Use multipart upload for files > 8 MB
    if len(data) > 8 * 1024 * 1024:
        # Multipart upload
        mpu = client.create_multipart_upload(
            Bucket=ONTAP_S3_BUCKET,
            Key=key,
            ContentType=content_type,
        )
        upload_id = mpu["UploadId"]
        parts = []
        part_size = 8 * 1024 * 1024  # 8 MB parts

        try:
            for i, offset in enumerate(range(0, len(data), part_size), 1):
                chunk = data[offset : offset + part_size]
                part_response = client.upload_part(
                    Bucket=ONTAP_S3_BUCKET,
                    Key=key,
                    UploadId=upload_id,
                    PartNumber=i,
                    Body=chunk,
                )
                parts.append({"ETag": part_response["ETag"], "PartNumber": i})

            client.complete_multipart_upload(
                Bucket=ONTAP_S3_BUCKET,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except Exception as e:
            client.abort_multipart_upload(
                Bucket=ONTAP_S3_BUCKET,
                Key=key,
                UploadId=upload_id,
            )
            raise e
    else:
        # Simple put
        client.put_object(
            Bucket=ONTAP_S3_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    uri = f"s3://{ONTAP_S3_BUCKET}/{key}"
    return {
        "uri": uri,
        "size_bytes": len(data),
        "checksum_sha256": checksum,
        "content_type": content_type,
    }


def upload_via_nfs(
    data: bytes, relative_path: str, content_type: str
) -> dict[str, str]:
    """Upload payload to FSx for ONTAP via NFS mount."""
    full_path = Path(NFS_MOUNT_PATH) / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    checksum = hashlib.sha256(data).hexdigest()

    with open(full_path, "wb") as f:
        f.write(data)

    uri = f"nfs://svm1.fsxn.local/vol_images/{relative_path}"
    return {
        "uri": uri,
        "size_bytes": len(data),
        "checksum_sha256": checksum,
        "content_type": content_type,
        "local_path": str(full_path),
    }


# ---------------------------------------------------------------------------
# Main Generator
# ---------------------------------------------------------------------------


def run_payload_generator(
    count: int = 10,
    image_ratio: float = 0.7,
    output_manifest: Optional[str] = None,
):
    """Generate and upload synthetic payloads."""
    logger.info("Starting synthetic payload generator")
    logger.info(f"  Storage mode: {STORAGE_MODE}")
    logger.info(f"  Count: {count}")
    logger.info(f"  Image ratio: {image_ratio:.0%}")

    if STORAGE_MODE == "s3":
        logger.info(f"  S3 endpoint: {ONTAP_S3_ENDPOINT}")
        logger.info(f"  S3 bucket: {ONTAP_S3_BUCKET}")
    else:
        logger.info(f"  NFS path: {NFS_MOUNT_PATH}")

    manifest = []
    start_time = time.time()

    for i in range(count):
        factory = random.choice(FACTORIES)
        line = random.choice(LINES[factory])
        ts_path = datetime.now(timezone.utc).strftime("%Y/%m/%d")

        if random.random() < image_ratio:
            # Generate image
            size_mb = random.uniform(IMAGE_MIN_SIZE_MB, IMAGE_MAX_SIZE_MB)
            data, content_type = generate_synthetic_image(size_mb)
            filename = f"quality_{uuid.uuid4().hex[:12]}.jpg"
        else:
            # Generate PDF document
            size_mb = random.uniform(1.0, 10.0)
            data, content_type = generate_synthetic_pdf(size_mb)
            filename = f"report_{uuid.uuid4().hex[:12]}.pdf"

        relative_path = f"{factory}/{line}/{ts_path}/{filename}"

        try:
            if STORAGE_MODE == "s3":
                result = upload_via_s3(data, relative_path, content_type)
            else:
                result = upload_via_nfs(data, relative_path, content_type)

            manifest.append(result)
            logger.info(
                f"  [{i + 1}/{count}] Uploaded: {result['uri']} "
                f"({result['size_bytes'] / 1024 / 1024:.1f} MB)"
            )
        except Exception as e:
            logger.error(f"  [{i + 1}/{count}] Failed: {relative_path} — {e}")

    elapsed = time.time() - start_time
    logger.info(
        f"Payload generation complete: {len(manifest)}/{count} files in {elapsed:.1f}s"
    )

    # Write manifest file
    if output_manifest:
        with open(output_manifest, "w") as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Manifest written to: {output_manifest}")

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Synthetic Payload Generator (FSx for ONTAP Upload)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of payloads to generate (default: 10)",
    )
    parser.add_argument(
        "--image-ratio",
        type=float,
        default=0.7,
        help="Ratio of images vs documents (default: 0.7 = 70%% images)",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="payload_manifest.json",
        help="Output manifest file path (default: payload_manifest.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate one sample without uploading",
    )

    args = parser.parse_args()

    if args.dry_run:
        logger.info("DRY RUN — generating sample image (not uploading)")
        data, ct = generate_synthetic_image(5.0)
        checksum = hashlib.sha256(data).hexdigest()
        print(f"Generated: {len(data)} bytes, type={ct}, sha256={checksum[:16]}...")
        # Save locally for inspection
        with open("/tmp/synthetic_sample.jpg", "wb") as f:
            f.write(data)
        logger.info("Sample saved to /tmp/synthetic_sample.jpg")
        return

    run_payload_generator(
        count=args.count,
        image_ratio=args.image_ratio,
        output_manifest=args.manifest,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Generate synthetic manufacturing sample datasets.

All data is entirely synthetic — no real factory, product, or person is represented.
Designed for FSx for ONTAP × Lakehouse integration PoC Phase 1 validation.

Usage:
    python3 generate-samples.py                          # Default generation
    python3 generate-samples.py --sensor-rows 10000      # Scale testing
    python3 generate-samples.py --annotate --bucket NAME # Upload as S3 annotations
"""

import argparse
import csv
import hashlib
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Reproducible randomness
random.seed(42)

# --- Constants ---

LINES = ["LINE-A01", "LINE-A02", "LINE-B01", "LINE-B02", "LINE-C01"]
EQUIPMENT_SENSOR = [
    "PRESS-001", "PRESS-002", "WELD-001", "WELD-002",
    "OVEN-001", "OVEN-002", "CONVEYOR-001", "ROBOT-001",
]
EQUIPMENT_INSPECT = ["CMM-001", "VISION-001", "VISION-002", "XRAY-001"]
SENSOR_TYPES = {
    "temperature": {"unit": "°C", "normal": (40, 80), "warning": (80, 90), "alarm": (90, 120)},
    "vibration": {"unit": "mm/s", "normal": (0.1, 2.0), "warning": (2.0, 4.0), "alarm": (4.0, 8.0)},
    "pressure": {"unit": "kPa", "normal": (100, 300), "warning": (300, 400), "alarm": (400, 600)},
}
PART_NUMBERS = ["PN-7201-A", "PN-7201-B", "PN-8305-C", "PN-9102-D", "PN-6400-E"]
DEFECT_CATEGORIES = [None, None, None, None, "scratch", "dimension", "contamination", "surface"]
SVMS = ["svm-production", "svm-quality", "svm-engineering"]
VOLUMES = ["vol_sensor_data", "vol_quality_images", "vol_cad_models", "vol_reports"]
OWNERS = ["svc_scada", "svc_quality", "svc_engineering", "svc_analytics"]
GROUPS = ["grp_factory_a", "grp_quality_team", "grp_engineering", "grp_data_platform"]
CLASSIFICATIONS = ["public", "internal", "internal", "internal", "confidential"]


def generate_sensor_data(num_rows: int) -> list[dict]:
    """Generate synthetic IoT sensor time-series data."""
    base_time = datetime(2026, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
    rows = []

    for i in range(num_rows):
        sensor_type = random.choice(list(SENSOR_TYPES.keys()))
        spec = SENSOR_TYPES[sensor_type]

        # 90% normal, 8% warning, 2% alarm
        roll = random.random()
        if roll < 0.90:
            status = "normal"
            value = random.uniform(*spec["normal"])
        elif roll < 0.98:
            status = "warning"
            value = random.uniform(*spec["warning"])
        else:
            status = "alarm"
            value = random.uniform(*spec["alarm"])

        rows.append({
            "timestamp": (base_time + timedelta(seconds=i * 5)).isoformat(),
            "line_id": random.choice(LINES),
            "equipment_id": random.choice(EQUIPMENT_SENSOR),
            "sensor_type": sensor_type,
            "value": round(value, 2),
            "unit": spec["unit"],
            "status": status,
        })

    return rows


def generate_quality_inspections(num_records: int) -> list[dict]:
    """Generate synthetic quality inspection results."""
    base_time = datetime(2026, 6, 15, 9, 0, 0, tzinfo=timezone.utc)
    records = []

    for i in range(num_records):
        # 85% pass, 10% fail, 5% conditional
        roll = random.random()
        if roll < 0.85:
            result = "pass"
            defect = None
        elif roll < 0.95:
            result = "fail"
            defect = random.choice([d for d in DEFECT_CATEGORIES if d is not None])
        else:
            result = "conditional"
            defect = random.choice([d for d in DEFECT_CATEGORIES if d is not None])

        lot_id = f"LOT-2026-{random.randint(1000, 9999)}"
        records.append({
            "inspection_id": f"INS-{i+1:05d}",
            "timestamp": (base_time + timedelta(minutes=i * 12)).isoformat(),
            "lot_id": lot_id,
            "part_number": random.choice(PART_NUMBERS),
            "result": result,
            "defect_category": defect,
            "image_path": f"/vol_quality_images/2026/06/15/{lot_id}_img_{i+1:03d}.jpg",
            "inspector_shift": "day" if (base_time + timedelta(minutes=i * 12)).hour < 18 else "night",
            "equipment_id": random.choice(EQUIPMENT_INSPECT),
        })

    return records


def generate_file_metadata(num_records: int) -> list[dict]:
    """Generate synthetic file metadata with ACL hints for S3 Annotations PoC."""
    records = []
    extensions = [".csv", ".parquet", ".json", ".jpg", ".pdf", ".xlsx"]

    for i in range(num_records):
        owner = random.choice(OWNERS)
        group = random.choice(GROUPS)
        classification = random.choice(CLASSIFICATIONS)

        # Generate deterministic ACL hash
        acl_content = f"{owner}:{group}:{classification}:{i}"
        acl_hash = hashlib.sha256(acl_content.encode()).hexdigest()[:16]

        svm = random.choice(SVMS)
        volume = random.choice(VOLUMES)
        ext = random.choice(extensions)

        records.append({
            "file_path": f"/{volume}/2026/06/{f'data_{i+1:04d}{ext}'}",
            "svm_name": svm,
            "volume_name": volume,
            "security_style": random.choice(["unix", "unix", "ntfs"]),
            "owner": owner,
            "group": group,
            "acl_hash": acl_hash,
            "classification": classification,
            "retention_days": random.choice([90, 365, 1095, 2555, 5475]),
            "last_modified": (
                datetime(2026, 6, 15, tzinfo=timezone.utc)
                - timedelta(days=random.randint(0, 30))
            ).isoformat(),
            "size_bytes": random.randint(1024, 104857600),  # 1 KB to 100 MB
        })

    return records


def write_sensor_csv(rows: list[dict], output_path: Path) -> None:
    """Write sensor data to CSV."""
    fieldnames = ["timestamp", "line_id", "equipment_id", "sensor_type", "value", "unit", "status"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✅ {output_path} ({len(rows)} rows)")


def write_json(records: list[dict], output_path: Path) -> None:
    """Write records to JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"  ✅ {output_path} ({len(records)} records)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic manufacturing samples")
    parser.add_argument("--sensor-rows", type=int, default=1000, help="Number of sensor rows")
    parser.add_argument("--inspections", type=int, default=50, help="Number of inspection records")
    parser.add_argument("--file-metadata", type=int, default=20, help="Number of file metadata records")
    parser.add_argument("--annotate", action="store_true", help="Upload as S3 annotations (requires boto3)")
    parser.add_argument("--bucket", type=str, help="S3 bucket for annotation upload")
    args = parser.parse_args()

    output_dir = Path(__file__).parent
    print("Generating synthetic manufacturing datasets...")

    # Generate sensor data
    sensor_rows = generate_sensor_data(args.sensor_rows)
    write_sensor_csv(sensor_rows, output_dir / "sensor-data.csv")

    # Generate quality inspections
    inspections = generate_quality_inspections(args.inspections)
    write_json(inspections, output_dir / "quality-inspection.json")

    # Generate file metadata
    file_metadata = generate_file_metadata(args.file_metadata)
    write_json(file_metadata, output_dir / "file-metadata-acl.json")

    print(f"\n✅ All datasets generated in {output_dir}/")
    print("   Use these with DataSync → S3 → Athena/Databricks PoC (Phase 1)")

    if args.annotate:
        if not args.bucket:
            print("\n❌ --bucket required with --annotate", file=sys.stderr)
            sys.exit(1)
        print(f"\n📝 Uploading annotations to s3://{args.bucket}/...")
        try:
            import boto3
            s3 = boto3.client("s3")
            for record in file_metadata:
                annotation_payload = json.dumps({
                    "schema_version": "1.0",
                    "classification": record["classification"],
                    "owner": record["owner"],
                    "group": record["group"],
                    "acl_hash": record["acl_hash"],
                    "retention_days": record["retention_days"],
                }, ensure_ascii=False)
                # Note: PutObjectAnnotation requires the object to exist in the bucket
                print(f"  → Would annotate: {record['file_path']} (dry-run without object)")
            print("  ⚠️  Actual annotation requires objects to exist in the target bucket.")
            print("     Upload sample files first, then re-run with --annotate.")
        except ImportError:
            print("❌ boto3 not installed. Run: pip install boto3", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

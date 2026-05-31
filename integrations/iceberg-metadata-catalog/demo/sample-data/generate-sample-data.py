#!/usr/bin/env python3
"""
generate-sample-data.py — Generate Realistic Sample Metadata for Demos

Creates realistic unstructured file metadata for demonstration purposes.
Supports multiple industry verticals with appropriate file names, types,
and sizes.

Usage:
    python generate-sample-data.py --industry manufacturing --count 100
    python generate-sample-data.py --industry financial --count 50 --output ./data
    python generate-sample-data.py --industry healthcare --count 200 --upload
"""

import argparse
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path


# Industry-specific file templates
INDUSTRY_DATA = {
    "manufacturing": {
        "departments": ["engineering", "quality", "production", "maintenance", "safety"],
        "file_templates": [
            {"pattern": "P-{part_num}_{component}_v{ver}.step", "type": ".step", "size_range": (5_000_000, 50_000_000), "classification": "engineering"},
            {"pattern": "{component}_assembly_drawing.dwg", "type": ".dwg", "size_range": (2_000_000, 30_000_000), "classification": "engineering"},
            {"pattern": "QC_report_{date}_{line}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "quality"},
            {"pattern": "maintenance_log_{equipment}_{date}.xlsx", "type": ".xlsx", "size_range": (100_000, 2_000_000), "classification": "maintenance"},
            {"pattern": "safety_inspection_{area}_{date}.pdf", "type": ".pdf", "size_range": (1_000_000, 8_000_000), "classification": "safety"},
            {"pattern": "BOM_{product}_rev{ver}.xlsx", "type": ".xlsx", "size_range": (200_000, 5_000_000), "classification": "engineering"},
            {"pattern": "production_schedule_{month}.xlsx", "type": ".xlsx", "size_range": (100_000, 1_000_000), "classification": "production"},
            {"pattern": "{product}_test_results_{date}.pdf", "type": ".pdf", "size_range": (2_000_000, 15_000_000), "classification": "quality"},
            {"pattern": "training_video_safety_{topic}.mp4", "type": ".mp4", "size_range": (50_000_000, 500_000_000), "classification": "training"},
            {"pattern": "ISO9001_procedure_{proc_id}.pdf", "type": ".pdf", "size_range": (500_000, 3_000_000), "classification": "compliance"},
        ],
        "components": ["pump_housing", "valve_body", "shaft_coupling", "bearing_mount", "gear_box", "motor_bracket", "heat_exchanger", "pressure_vessel", "turbine_blade", "impeller"],
        "products": ["HX-2000", "VP-500", "CP-1200", "TG-800", "PM-3000"],
        "equipment": ["CNC-01", "Press-A3", "Lathe-07", "Robot-12", "Furnace-02"],
        "areas": ["Zone-A", "Zone-B", "Assembly-1", "Warehouse", "Loading-Dock"],
    },
    "financial": {
        "departments": ["accounting", "compliance", "legal", "risk", "treasury"],
        "file_templates": [
            {"pattern": "Q{quarter}_financial_report_{year}.xlsx", "type": ".xlsx", "size_range": (500_000, 10_000_000), "classification": "financial"},
            {"pattern": "{client}_contract_{year}.pdf", "type": ".pdf", "size_range": (1_000_000, 20_000_000), "classification": "legal"},
            {"pattern": "audit_report_{scope}_{year}.pdf", "type": ".pdf", "size_range": (2_000_000, 30_000_000), "classification": "compliance"},
            {"pattern": "risk_assessment_{portfolio}_{date}.xlsx", "type": ".xlsx", "size_range": (300_000, 5_000_000), "classification": "risk"},
            {"pattern": "board_minutes_{date}.pdf", "type": ".pdf", "size_range": (200_000, 2_000_000), "classification": "governance"},
            {"pattern": "NDA_{counterparty}_{year}.pdf", "type": ".pdf", "size_range": (500_000, 3_000_000), "classification": "legal"},
            {"pattern": "tax_filing_{jurisdiction}_{year}.pdf", "type": ".pdf", "size_range": (1_000_000, 15_000_000), "classification": "financial"},
            {"pattern": "KYC_documentation_{client}.pdf", "type": ".pdf", "size_range": (2_000_000, 10_000_000), "classification": "compliance"},
            {"pattern": "investment_memo_{deal}_{date}.docx", "type": ".docx", "size_range": (500_000, 5_000_000), "classification": "financial"},
            {"pattern": "regulatory_response_{regulator}_{date}.pdf", "type": ".pdf", "size_range": (1_000_000, 8_000_000), "classification": "compliance"},
        ],
        "clients": ["Tanaka_Industries", "Suzuki_Holdings", "Yamamoto_Corp", "Global_Partners", "Pacific_Trading"],
        "portfolios": ["equity_JP", "fixed_income", "alternatives", "real_estate", "emerging_markets"],
        "regulators": ["FSA", "SEC", "FCA", "JFSA", "MAS"],
    },
    "healthcare": {
        "departments": ["radiology", "pathology", "research", "clinical_trials", "administration"],
        "file_templates": [
            {"pattern": "MRI_scan_{study_id}_{sequence}.dcm", "type": ".dcm", "size_range": (10_000_000, 500_000_000), "classification": "medical_imaging"},
            {"pattern": "CT_scan_{study_id}_{slice}.dcm", "type": ".dcm", "size_range": (5_000_000, 200_000_000), "classification": "medical_imaging"},
            {"pattern": "pathology_slide_{case_id}.svs", "type": ".svs", "size_range": (100_000_000, 2_000_000_000), "classification": "pathology"},
            {"pattern": "clinical_trial_{trial_id}_protocol.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "research"},
            {"pattern": "patient_consent_{trial_id}_{site}.pdf", "type": ".pdf", "size_range": (500_000, 3_000_000), "classification": "compliance"},
            {"pattern": "research_paper_draft_{topic}_{ver}.docx", "type": ".docx", "size_range": (1_000_000, 10_000_000), "classification": "research"},
            {"pattern": "DICOM_SR_{study_id}.dcm", "type": ".dcm", "size_range": (100_000, 1_000_000), "classification": "medical_imaging"},
            {"pattern": "lab_results_{patient_id}_{date}.pdf", "type": ".pdf", "size_range": (200_000, 2_000_000), "classification": "clinical"},
            {"pattern": "surgical_video_{procedure}_{date}.mp4", "type": ".mp4", "size_range": (500_000_000, 5_000_000_000), "classification": "surgical"},
            {"pattern": "IRB_approval_{trial_id}.pdf", "type": ".pdf", "size_range": (500_000, 5_000_000), "classification": "compliance"},
        ],
        "studies": ["STD-2024-001", "STD-2024-002", "STD-2024-003", "STD-2023-045", "STD-2023-078"],
        "trials": ["NCT-04521", "NCT-04522", "NCT-04890", "NCT-05001", "NCT-05123"],
        "procedures": ["arthroscopy", "laparoscopy", "endoscopy", "biopsy", "catheterization"],
    },
    "media": {
        "departments": ["production", "post_production", "graphics", "audio", "archive"],
        "file_templates": [
            {"pattern": "raw_footage_{project}_{scene}_{take}.mov", "type": ".mov", "size_range": (1_000_000_000, 50_000_000_000), "classification": "raw_footage"},
            {"pattern": "{project}_final_cut_v{ver}.mp4", "type": ".mp4", "size_range": (500_000_000, 10_000_000_000), "classification": "edited"},
            {"pattern": "VFX_{project}_{shot}_comp.exr", "type": ".exr", "size_range": (50_000_000, 500_000_000), "classification": "vfx"},
            {"pattern": "color_grade_{project}_{reel}.dpx", "type": ".dpx", "size_range": (100_000_000, 1_000_000_000), "classification": "color"},
            {"pattern": "audio_mix_{project}_{stem}.wav", "type": ".wav", "size_range": (50_000_000, 500_000_000), "classification": "audio"},
            {"pattern": "thumbnail_{project}_{variant}.psd", "type": ".psd", "size_range": (10_000_000, 100_000_000), "classification": "graphics"},
            {"pattern": "subtitle_{project}_{lang}.srt", "type": ".srt", "size_range": (10_000, 500_000), "classification": "subtitle"},
            {"pattern": "storyboard_{project}_{scene}.pdf", "type": ".pdf", "size_range": (5_000_000, 50_000_000), "classification": "pre_production"},
            {"pattern": "BTS_photo_{project}_{num}.raw", "type": ".raw", "size_range": (20_000_000, 80_000_000), "classification": "photography"},
            {"pattern": "music_license_{track}_{project}.pdf", "type": ".pdf", "size_range": (200_000, 2_000_000), "classification": "legal"},
        ],
        "projects": ["Sakura_Documentary", "Tokyo_Nights", "Ocean_Blue", "Mountain_Spirit", "City_Pulse"],
        "scenes": ["opening", "interview_01", "b_roll_sunset", "aerial_city", "closing"],
    },
    "public_sector": {
        "departments": ["records", "legal", "planning", "public_works", "emergency"],
        "file_templates": [
            {"pattern": "permit_application_{type}_{id}.pdf", "type": ".pdf", "size_range": (1_000_000, 10_000_000), "classification": "permit"},
            {"pattern": "council_minutes_{date}.pdf", "type": ".pdf", "size_range": (200_000, 3_000_000), "classification": "governance"},
            {"pattern": "GIS_map_{area}_{layer}.tiff", "type": ".tiff", "size_range": (50_000_000, 500_000_000), "classification": "geospatial"},
            {"pattern": "public_comment_{project}_{id}.pdf", "type": ".pdf", "size_range": (100_000, 2_000_000), "classification": "public_input"},
            {"pattern": "budget_proposal_{dept}_{fy}.xlsx", "type": ".xlsx", "size_range": (500_000, 5_000_000), "classification": "financial"},
            {"pattern": "emergency_plan_{scenario}_{ver}.pdf", "type": ".pdf", "size_range": (5_000_000, 30_000_000), "classification": "emergency"},
            {"pattern": "FOIA_request_{id}_{date}.pdf", "type": ".pdf", "size_range": (500_000, 20_000_000), "classification": "legal"},
            {"pattern": "infrastructure_report_{asset}.pdf", "type": ".pdf", "size_range": (2_000_000, 15_000_000), "classification": "engineering"},
            {"pattern": "census_data_{district}_{year}.csv", "type": ".csv", "size_range": (1_000_000, 50_000_000), "classification": "statistics"},
            {"pattern": "training_cert_{employee}_{course}.pdf", "type": ".pdf", "size_range": (200_000, 1_000_000), "classification": "hr"},
        ],
        "permit_types": ["building", "environmental", "zoning", "demolition", "occupancy"],
        "areas": ["District-1", "District-2", "Downtown", "Industrial-Zone", "Residential-North"],
    },
    "energy": {
        "departments": ["operations", "safety", "environmental", "engineering", "compliance"],
        "file_templates": [
            {"pattern": "well_log_{well_id}_{date}.las", "type": ".las", "size_range": (5_000_000, 50_000_000), "classification": "geological"},
            {"pattern": "seismic_survey_{area}_{line}.segy", "type": ".segy", "size_range": (100_000_000, 5_000_000_000), "classification": "geological"},
            {"pattern": "pipeline_inspection_{segment}_{date}.pdf", "type": ".pdf", "size_range": (5_000_000, 30_000_000), "classification": "inspection"},
            {"pattern": "SCADA_data_{plant}_{date}.csv", "type": ".csv", "size_range": (10_000_000, 100_000_000), "classification": "operations"},
            {"pattern": "environmental_impact_{project}.pdf", "type": ".pdf", "size_range": (10_000_000, 100_000_000), "classification": "environmental"},
            {"pattern": "safety_incident_{id}_{date}.pdf", "type": ".pdf", "size_range": (1_000_000, 10_000_000), "classification": "safety"},
            {"pattern": "drone_inspection_{asset}_{date}.mp4", "type": ".mp4", "size_range": (500_000_000, 5_000_000_000), "classification": "inspection"},
            {"pattern": "turbine_performance_{unit}_{month}.xlsx", "type": ".xlsx", "size_range": (500_000, 5_000_000), "classification": "operations"},
            {"pattern": "regulatory_filing_{agency}_{year}.pdf", "type": ".pdf", "size_range": (2_000_000, 20_000_000), "classification": "compliance"},
            {"pattern": "thermal_image_{equipment}_{date}.tiff", "type": ".tiff", "size_range": (10_000_000, 50_000_000), "classification": "inspection"},
        ],
        "wells": ["WL-001", "WL-002", "WL-003", "WL-045", "WL-078"],
        "plants": ["Plant-Alpha", "Plant-Beta", "Offshore-1", "Refinery-East", "Solar-Farm-3"],
        "assets": ["Turbine-01", "Pipeline-A3", "Transformer-12", "Compressor-07", "Tower-15"],
    },
}


def generate_file_name(template: dict, industry_data: dict) -> str:
    """Generate a realistic file name from a template."""
    pattern = template["pattern"]

    # Common substitutions
    replacements = {
        "{part_num}": str(random.randint(1000, 9999)),
        "{ver}": str(random.randint(1, 5)),
        "{date}": (datetime.now() - timedelta(days=random.randint(1, 730))).strftime("%Y%m%d"),
        "{month}": (datetime.now() - timedelta(days=random.randint(1, 365))).strftime("%Y-%m"),
        "{year}": str(random.choice([2022, 2023, 2024])),
        "{quarter}": str(random.randint(1, 4)),
        "{id}": f"{random.randint(1000, 9999):04d}",
        "{num}": f"{random.randint(1, 999):03d}",
        "{lang}": random.choice(["ja", "en", "zh", "ko"]),
        "{take}": f"T{random.randint(1, 12):02d}",
        "{slice}": f"S{random.randint(1, 200):03d}",
        "{sequence}": random.choice(["T1", "T2", "FLAIR", "DWI", "ADC"]),
        "{stem}": random.choice(["dialogue", "music", "sfx", "ambience", "full_mix"]),
        "{variant}": random.choice(["A", "B", "C", "wide", "square"]),
        "{reel}": f"R{random.randint(1, 10):02d}",
        "{shot}": f"SH{random.randint(100, 999)}",
        "{fy}": f"FY{random.choice([2023, 2024, 2025])}",
    }

    # Industry-specific substitutions
    if "components" in industry_data:
        replacements["{component}"] = random.choice(industry_data["components"])
    if "products" in industry_data:
        replacements["{product}"] = random.choice(industry_data["products"])
    if "equipment" in industry_data:
        replacements["{equipment}"] = random.choice(industry_data["equipment"])
    if "areas" in industry_data:
        replacements["{area}"] = random.choice(industry_data["areas"])
    if "clients" in industry_data:
        replacements["{client}"] = random.choice(industry_data["clients"])
        replacements["{counterparty}"] = random.choice(industry_data["clients"])
    if "portfolios" in industry_data:
        replacements["{portfolio}"] = random.choice(industry_data["portfolios"])
    if "regulators" in industry_data:
        replacements["{regulator}"] = random.choice(industry_data["regulators"])
        replacements["{agency}"] = random.choice(industry_data["regulators"])
    if "studies" in industry_data:
        replacements["{study_id}"] = random.choice(industry_data["studies"])
    if "trials" in industry_data:
        replacements["{trial_id}"] = random.choice(industry_data["trials"])
    if "procedures" in industry_data:
        replacements["{procedure}"] = random.choice(industry_data["procedures"])
    if "projects" in industry_data:
        replacements["{project}"] = random.choice(industry_data["projects"])
    if "scenes" in industry_data:
        replacements["{scene}"] = random.choice(industry_data["scenes"])
    if "wells" in industry_data:
        replacements["{well_id}"] = random.choice(industry_data["wells"])
    if "plants" in industry_data:
        replacements["{plant}"] = random.choice(industry_data["plants"])
    if "assets" in industry_data:
        replacements["{asset}"] = random.choice(industry_data["assets"])
    if "permit_types" in industry_data:
        replacements["{type}"] = random.choice(industry_data["permit_types"])

    # Additional context-specific replacements
    replacements["{line}"] = f"Line-{random.randint(1, 5)}"
    replacements["{proc_id}"] = f"QP-{random.randint(100, 999)}"
    replacements["{scope}"] = random.choice(["internal", "external", "SOX", "ISO"])
    replacements["{deal}"] = f"Deal-{random.randint(100, 999)}"
    replacements["{jurisdiction}"] = random.choice(["JP", "US", "UK", "SG", "HK"])
    replacements["{case_id}"] = f"CASE-{random.randint(10000, 99999)}"
    replacements["{patient_id}"] = f"PT-{random.randint(100000, 999999)}"
    replacements["{topic}"] = random.choice(["genomics", "immunology", "cardiology", "oncology"])
    replacements["{site}"] = random.choice(["Tokyo", "Osaka", "Nagoya", "Fukuoka"])
    replacements["{track}"] = f"TRK-{random.randint(1000, 9999)}"
    replacements["{segment}"] = f"SEG-{random.randint(1, 50):02d}"
    replacements["{unit}"] = f"Unit-{random.randint(1, 20):02d}"
    replacements["{layer}"] = random.choice(["elevation", "parcels", "utilities", "zoning"])
    replacements["{district}"] = random.choice(["North", "South", "East", "West", "Central"])
    replacements["{employee}"] = f"EMP-{random.randint(1000, 9999)}"
    replacements["{course}"] = random.choice(["safety", "ethics", "IT_security", "leadership"])
    replacements["{scenario}"] = random.choice(["earthquake", "flood", "fire", "pandemic"])
    replacements["{dept}"] = random.choice(["public_works", "education", "health", "transport"])

    result = pattern
    for key, value in replacements.items():
        result = result.replace(key, value)

    return result


def generate_metadata_record(industry: str, industry_data: dict) -> dict:
    """Generate a single metadata record."""
    template = random.choice(industry_data["file_templates"])
    file_name = generate_file_name(template, industry_data)
    department = random.choice(industry_data["departments"])
    file_size = random.randint(*template["size_range"])
    last_modified = datetime.now() - timedelta(
        days=random.randint(1, 730),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )

    return {
        "file_id": str(uuid.uuid4()),
        "file_name": file_name,
        "file_path": f"/vol1/{department}/{file_name}",
        "file_type": template["type"],
        "file_size": file_size,
        "last_modified": last_modified.isoformat() + "Z",
        "classification": template["classification"],
        "confidence_score": round(random.uniform(0.85, 0.99), 2),
        "department": department,
        "industry": industry,
        "is_deleted": False,
        "enrichment_status": random.choice(["completed", "completed", "completed", "pending"]),
        "content_hash": uuid.uuid4().hex[:32],
        "scan_timestamp": datetime.now().isoformat() + "Z",
    }


def generate_sample_content(industry: str, file_name: str) -> str:
    """Generate sample text content for a file (for text-based files)."""
    content_templates = {
        "manufacturing": (
            f"Document: {file_name}\n"
            f"Department: Engineering\n"
            f"Classification: Technical Document\n\n"
            f"This document contains technical specifications for the component.\n"
            f"Material: Cast Iron FC250 / Stainless Steel SUS304\n"
            f"Tolerance: ±0.05mm\n"
            f"Surface finish: Ra 1.6\n"
            f"Heat treatment: Quenching and tempering\n"
        ),
        "financial": (
            f"Document: {file_name}\n"
            f"Department: Finance & Compliance\n"
            f"Classification: Confidential\n\n"
            f"This document contains financial information subject to regulatory requirements.\n"
            f"Retention period: 7 years\n"
            f"Access: Authorized personnel only\n"
            f"Audit trail: Required\n"
        ),
        "healthcare": (
            f"Document: {file_name}\n"
            f"Department: Clinical Research\n"
            f"Classification: PHI - Protected Health Information\n\n"
            f"This document is subject to HIPAA privacy and security rules.\n"
            f"De-identification required before sharing.\n"
            f"IRB approval: Required for research use\n"
        ),
        "media": (
            f"Document: {file_name}\n"
            f"Department: Production\n"
            f"Classification: Creative Asset\n\n"
            f"Project asset for production use.\n"
            f"License: Internal use only\n"
            f"Resolution: 4K UHD (3840x2160)\n"
            f"Color space: Rec. 2020\n"
        ),
        "public_sector": (
            f"Document: {file_name}\n"
            f"Department: Public Records\n"
            f"Classification: Public Record\n\n"
            f"This document is subject to public records retention requirements.\n"
            f"FOIA: May be subject to disclosure requests\n"
            f"Retention: Per records schedule\n"
        ),
        "energy": (
            f"Document: {file_name}\n"
            f"Department: Operations\n"
            f"Classification: Operational Data\n\n"
            f"This document contains operational data for energy infrastructure.\n"
            f"Safety classification: Critical\n"
            f"Regulatory: Subject to energy commission oversight\n"
        ),
    }
    return content_templates.get(industry, f"Sample content for {file_name}\n")


def print_header(industry: str, count: int):
    """Print generation header."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Sample Data Generator — Iceberg Metadata Catalog Demo       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print(f"  Industry:    {industry}")
    print(f"  File count:  {count}")
    print(f"  Departments: {', '.join(INDUSTRY_DATA[industry]['departments'])}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Generate realistic sample unstructured file metadata for demos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Supported industries:
    manufacturing   — CAD files, QC reports, maintenance logs
    financial       — Contracts, audit reports, regulatory filings
    healthcare      — DICOM images, clinical trials, research papers
    media           — Video footage, VFX, audio, graphics
    public_sector   — Permits, GIS maps, public records
    energy          — Well logs, seismic data, pipeline inspections

Examples:
    python generate-sample-data.py --industry manufacturing --count 100
    python generate-sample-data.py --industry financial --count 50 --output ./data
    python generate-sample-data.py --industry healthcare --count 200 --with-content
        """,
    )
    parser.add_argument(
        "--industry",
        choices=list(INDUSTRY_DATA.keys()),
        required=True,
        help="Industry vertical for sample data generation",
    )
    parser.add_argument(
        "--count", type=int, default=100,
        help="Number of metadata records to generate (default: 100)",
    )
    parser.add_argument(
        "--output", type=str, default="./generated",
        help="Output directory for generated files (default: ./generated)",
    )
    parser.add_argument(
        "--with-content", action="store_true",
        help="Also generate sample text files with industry-appropriate content",
    )
    parser.add_argument(
        "--upload", action="store_true",
        help="Upload generated files to FSx S3 Access Point (requires --ap-alias)",
    )
    parser.add_argument(
        "--ap-alias", type=str, default=None,
        help="FSx S3 Access Point alias for upload",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducible generation",
    )
    args = parser.parse_args()

    if args.upload and not args.ap_alias:
        print("  ❌ --upload requires --ap-alias")
        sys.exit(1)

    if args.seed is not None:
        random.seed(args.seed)

    industry_data = INDUSTRY_DATA[args.industry]
    print_header(args.industry, args.count)

    # Generate metadata records
    records = []
    for i in range(args.count):
        record = generate_metadata_record(args.industry, industry_data)
        records.append(record)

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write metadata JSON
    metadata_file = output_dir / f"metadata_{args.industry}.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    print(f"  ✅ Generated {len(records)} metadata records")
    print(f"  📄 Metadata file: {metadata_file}")
    print()

    # Generate sample content files if requested
    if args.with_content:
        content_dir = output_dir / "content"
        content_dir.mkdir(parents=True, exist_ok=True)
        text_count = 0
        for record in records:
            if record["file_type"] in (".pdf", ".docx", ".xlsx", ".csv", ".txt"):
                content_file = content_dir / f"{record['file_name']}.txt"
                content = generate_sample_content(args.industry, record["file_name"])
                with open(content_file, "w", encoding="utf-8") as f:
                    f.write(content)
                text_count += 1
        print(f"  ✅ Generated {text_count} sample content files")
        print(f"  📁 Content directory: {content_dir}")
        print()

    # Upload to S3 if requested
    if args.upload:
        print("┌──────────────────────────────────────────────────────────────┐")
        print("│  Uploading to FSx S3 Access Point                            │")
        print("└──────────────────────────────────────────────────────────────┘")
        print()
        try:
            import boto3
            s3 = boto3.client("s3")
            uploaded = 0
            for record in records:
                if args.with_content and record["file_type"] in (".pdf", ".docx", ".xlsx", ".csv", ".txt"):
                    content_file = output_dir / "content" / f"{record['file_name']}.txt"
                    if content_file.exists():
                        key = record["file_path"].lstrip("/")
                        s3.upload_file(str(content_file), args.ap_alias, key)
                        uploaded += 1
            print(f"  ✅ Uploaded {uploaded} files to s3://{args.ap_alias}/")
        except ImportError:
            print("  ❌ boto3 not installed. Install with: pip install boto3")
        except Exception as e:
            print(f"  ❌ Upload failed: {e}")
        print()

    # Print summary statistics
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Generation Summary                                          │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()

    # Classification distribution
    classifications = {}
    total_size = 0
    for r in records:
        cls = r["classification"]
        classifications[cls] = classifications.get(cls, 0) + 1
        total_size += r["file_size"]

    print("  Classification distribution:")
    for cls, count in sorted(classifications.items(), key=lambda x: -x[1]):
        bar = "█" * (count * 30 // args.count)
        print(f"    {cls:<20} {bar} {count}")
    print()

    # File type distribution
    file_types = {}
    for r in records:
        ft = r["file_type"]
        file_types[ft] = file_types.get(ft, 0) + 1

    print("  File type distribution:")
    for ft, count in sorted(file_types.items(), key=lambda x: -x[1]):
        print(f"    {ft:<8} {count:>4} files")
    print()

    # Size summary
    avg_size = total_size / len(records)
    print(f"  Total data volume: {total_size / (1024**3):.1f} GB (simulated)")
    print(f"  Average file size: {avg_size / (1024**2):.1f} MB")
    print()
    print("  Next steps:")
    print(f"    1. Review: cat {metadata_file} | python -m json.tool | head -50")
    print(f"    2. Load into Iceberg: python initial-metadata-scan.py --from-json {metadata_file}")
    if not args.upload:
        print(f"    3. Upload to FSx: python {sys.argv[0]} --industry {args.industry} --upload --ap-alias <alias>")
    print()


if __name__ == "__main__":
    main()

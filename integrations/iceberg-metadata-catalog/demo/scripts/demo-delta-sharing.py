#!/usr/bin/env python3
"""
demo-delta-sharing.py — Delta Sharing Protocol Demo (D-2)

Demonstrates sharing the Iceberg metadata catalog via Delta Sharing protocol.
Recipients can read shared metadata without copying data — enabling cross-org
collaboration on unstructured file discovery.

Key Message:
    "Share metadata across organizations without copying data"

Architecture:
    FSx for ONTAP → Iceberg Metadata Table → Delta Sharing Server → Recipients
    (Data stays in place; only metadata access is shared)

Usage:
    python demo-delta-sharing.py --share-name customer-metadata-share
    python demo-delta-sharing.py --share-name partner-share --recipient acme-corp
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta


def print_header():
    """Print demo header with box-drawing characters."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  D-2: Delta Sharing — Cross-Organization Metadata Sharing   ║")
    print("║  Protocol: Delta Sharing (open standard)                    ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def demo_create_share(share_name: str, table_name: str):
    """Demonstrate creating a Delta Sharing share from the metadata table."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 1: Create Delta Sharing Share                          │")
    print("│  Share the Iceberg metadata table via Delta Sharing          │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print("  SQL (Databricks Unity Catalog):")
    print()
    print(f"    CREATE SHARE {share_name};")
    print()
    print(f"    ALTER SHARE {share_name}")
    print(f"      ADD TABLE fsxn_metadata_catalog.metadata.unstructured_files")
    print(f"      COMMENT 'FSx for ONTAP unstructured file metadata — Iceberg format';")
    print()
    print(f"    -- Share includes: file_name, file_type, classification,")
    print(f"    --   confidence_score, summary, file_size, last_modified")
    print(f"    -- Excludes: file_path (security), pii_entities (privacy)")
    print()

    # Simulated share details
    share_info = {
        "name": share_name,
        "created_at": datetime.now().isoformat(),
        "objects": [
            {
                "type": "TABLE",
                "name": "fsxn_metadata_catalog.metadata.unstructured_files",
                "shared_columns": [
                    "file_name", "file_type", "file_size", "last_modified",
                    "classification", "confidence_score", "summary",
                    "enrichment_status", "content_hash",
                ],
                "excluded_columns": ["file_path", "pii_entities", "s3_version_id"],
                "partition_filter": "is_deleted = false",
            }
        ],
        "status": "ACTIVE",
    }

    print("  Share created successfully:")
    print(f"    Name:     {share_info['name']}")
    print(f"    Tables:   1 (unstructured_files)")
    print(f"    Columns:  {len(share_info['objects'][0]['shared_columns'])} shared, "
          f"{len(share_info['objects'][0]['excluded_columns'])} excluded")
    print(f"    Filter:   is_deleted = false (only active files)")
    print(f"    Status:   ✅ ACTIVE")
    print()


def demo_generate_profile(share_name: str, recipient: str):
    """Demonstrate generating a sharing profile for a recipient."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 2: Generate Sharing Profile for Recipient              │")
    print("│  Create credentials for external organization access         │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print("  SQL (Databricks Unity Catalog):")
    print()
    print(f"    CREATE RECIPIENT {recipient}")
    print(f"      COMMENT 'Partner organization — metadata read access';")
    print()
    print(f"    GRANT SELECT ON SHARE {share_name} TO RECIPIENT {recipient};")
    print()

    # Simulated profile
    profile = {
        "shareCredentialsVersion": 1,
        "endpoint": "https://ap-northeast-1.sharing.databricks.com/delta-sharing/",
        "bearerToken": "<REDACTED — generated per recipient>",
        "expirationTime": (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    }

    print("  Generated sharing profile (JSON):")
    print()
    print("    {")
    print(f'      "shareCredentialsVersion": {profile["shareCredentialsVersion"]},')
    print(f'      "endpoint": "{profile["endpoint"]}",')
    print(f'      "bearerToken": "<REDACTED>",')
    print(f'      "expirationTime": "{profile["expirationTime"]}"')
    print("    }")
    print()
    print(f"  📄 Profile saved to: /tmp/{recipient}-profile.json")
    print(f"  📧 Send this file securely to the recipient organization")
    print(f"  ⏰ Token expires: {profile['expirationTime']}")
    print()


def demo_recipient_read(recipient: str):
    """Simulate a recipient reading shared metadata."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 3: Recipient Reads Shared Metadata                     │")
    print("│  External org queries metadata — no data copy needed         │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print(f"  Recipient: {recipient}")
    print(f"  SDK: delta-sharing-python (open source)")
    print()
    print("  Python code (recipient side):")
    print()
    print("    import delta_sharing")
    print()
    print(f'    profile = "{recipient}-profile.json"')
    print(f'    table_url = profile + "#fsxn_metadata_catalog.metadata.unstructured_files"')
    print()
    print("    # Read shared metadata as Pandas DataFrame")
    print("    df = delta_sharing.load_as_pandas(table_url)")
    print('    print(f"Shared files: {len(df)}")')
    print('    print(df[["file_name", "classification", "confidence_score"]].head())')
    print()

    # Simulated query results
    time.sleep(0.5)
    print("  ─── Simulated recipient query results ───")
    print()
    print("    Shared files: 847")
    print()
    print("    file_name                    classification    confidence_score")
    print("    ─────────────────────────    ──────────────    ────────────────")
    print("    Q4_financial_report.pdf      financial         0.97")
    print("    product_design_v3.dwg        engineering       0.94")
    print("    customer_contract_2024.docx  legal             0.96")
    print("    MRI_scan_patient_001.dcm     medical_imaging   0.99")
    print("    training_video_safety.mp4    training          0.91")
    print()
    print("  ✅ Recipient can discover files WITHOUT accessing actual file content")
    print("  ✅ No data copied — metadata served directly from Iceberg table")
    print("  ✅ Column-level security enforced (file_path excluded)")
    print()


def demo_key_benefits():
    """Print key benefits summary."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Key Benefits: Delta Sharing for Metadata Catalog            │")
    print("├──────────────────────────────────────────────────────────────┤")
    print("│                                                              │")
    print("│  1. Zero-copy sharing — metadata stays in your account       │")
    print("│  2. Column-level security — exclude sensitive fields          │")
    print("│  3. Row-level filtering — share only active (non-deleted)     │")
    print("│  4. Open protocol — recipients use any Delta Sharing client   │")
    print("│  5. Audit trail — all access logged in Unity Catalog          │")
    print("│  6. Revocable — remove recipient access instantly             │")
    print("│                                                              │")
    print("│  💡 Key Message:                                              │")
    print("│  \"Share metadata across organizations without copying data\"   │")
    print("│                                                              │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print("  Use cases:")
    print("    • Partner organizations discovering shared assets")
    print("    • Cross-subsidiary file catalog federation")
    print("    • Vendor access to project document metadata")
    print("    • Research collaboration (share what exists, not the data)")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Delta Sharing Protocol Demo — Share metadata catalog across organizations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python demo-delta-sharing.py --share-name customer-metadata-share
    python demo-delta-sharing.py --share-name partner-share --recipient acme-corp
    python demo-delta-sharing.py --share-name internal-share --recipient subsidiary-jp
        """,
    )
    parser.add_argument(
        "--share-name", default="fsxn-metadata-share",
        help="Name for the Delta Sharing share (default: fsxn-metadata-share)",
    )
    parser.add_argument(
        "--recipient", default="partner-org",
        help="Recipient organization name (default: partner-org)",
    )
    parser.add_argument(
        "--table-name", default="fsxn_metadata_catalog.metadata.unstructured_files",
        help="Fully qualified table name to share",
    )
    args = parser.parse_args()

    print_header()
    demo_create_share(args.share_name, args.table_name)
    demo_generate_profile(args.share_name, args.recipient)
    demo_recipient_read(args.recipient)
    demo_key_benefits()


if __name__ == "__main__":
    main()

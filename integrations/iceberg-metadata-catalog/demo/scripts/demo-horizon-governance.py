#!/usr/bin/env python3
"""
demo-horizon-governance.py — Snowflake Horizon Catalog Governance Demo (S-3)

Demonstrates enterprise governance capabilities on the metadata catalog:
- Row Access Policies (role-based data visibility)
- Dynamic Data Masking (column-level protection)
- Cross-engine enforcement (policies apply to external engines too)
- Audit via STORAGE_REQUEST_HISTORY

Key Message:
    "Same table, different views based on role — enforced on external engines too"

Usage:
    python demo-horizon-governance.py
    python demo-horizon-governance.py --role analyst
    python demo-horizon-governance.py --role admin --show-audit
"""

import argparse
import sys
import time


def print_header():
    """Print demo header."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  S-3: Horizon Catalog — Governance & Access Control          ║")
    print("║  Features: Row Access Policy + Dynamic Masking + Audit       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def demo_row_access_policy():
    """Demonstrate Row Access Policy creation and application."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 1: Row Access Policy                                   │")
    print("│  Different roles see different subsets of metadata            │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print("  SQL — Create Row Access Policy:")
    print()
    print("    CREATE OR REPLACE ROW ACCESS POLICY")
    print("      metadata.department_access_policy")
    print("    AS (classification VARCHAR) RETURNS BOOLEAN ->")
    print("      CASE")
    print("        -- Admins see everything")
    print("        WHEN IS_ROLE_IN_SESSION('METADATA_ADMIN')")
    print("          THEN TRUE")
    print("        -- Finance team sees financial + compliance docs")
    print("        WHEN IS_ROLE_IN_SESSION('FINANCE_TEAM')")
    print("          THEN classification IN ('financial', 'compliance', 'legal')")
    print("        -- Engineering sees engineering + training docs")
    print("        WHEN IS_ROLE_IN_SESSION('ENGINEERING_TEAM')")
    print("          THEN classification IN ('engineering', 'training', 'technical')")
    print("        -- HR sees HR + training + compliance docs")
    print("        WHEN IS_ROLE_IN_SESSION('HR_TEAM')")
    print("          THEN classification IN ('hr', 'training', 'compliance')")
    print("        -- Default: only public/training docs")
    print("        ELSE classification IN ('training', 'public')")
    print("      END;")
    print()
    print("  SQL — Apply to metadata table:")
    print()
    print("    ALTER TABLE fsxn_metadata_catalog.metadata.unstructured_files")
    print("      ADD ROW ACCESS POLICY metadata.department_access_policy")
    print("      ON (classification);")
    print()
    print("  ✅ Policy applied — queries automatically filtered by role")
    print()


def demo_dynamic_masking():
    """Demonstrate Dynamic Data Masking on file_path column."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 2: Dynamic Data Masking                                │")
    print("│  Sensitive columns masked based on role                       │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print("  SQL — Create Masking Policy:")
    print()
    print("    CREATE OR REPLACE MASKING POLICY")
    print("      metadata.file_path_mask")
    print("    AS (val VARCHAR) RETURNS VARCHAR ->")
    print("      CASE")
    print("        -- Admins and storage team see full path")
    print("        WHEN IS_ROLE_IN_SESSION('METADATA_ADMIN')")
    print("          OR IS_ROLE_IN_SESSION('STORAGE_ADMIN')")
    print("          THEN val")
    print("        -- Others see only filename (path redacted)")
    print("        ELSE CONCAT('***/', SPLIT_PART(val, '/', -1))")
    print("      END;")
    print()
    print("    CREATE OR REPLACE MASKING POLICY")
    print("      metadata.pii_entities_mask")
    print("    AS (val VARIANT) RETURNS VARIANT ->")
    print("      CASE")
    print("        WHEN IS_ROLE_IN_SESSION('COMPLIANCE_OFFICER')")
    print("          OR IS_ROLE_IN_SESSION('METADATA_ADMIN')")
    print("          THEN val")
    print("        ELSE TO_VARIANT('*** PII REDACTED ***')")
    print("      END;")
    print()
    print("  SQL — Apply masking policies:")
    print()
    print("    ALTER TABLE fsxn_metadata_catalog.metadata.unstructured_files")
    print("      MODIFY COLUMN file_path")
    print("      SET MASKING POLICY metadata.file_path_mask;")
    print()
    print("    ALTER TABLE fsxn_metadata_catalog.metadata.unstructured_files")
    print("      MODIFY COLUMN pii_entities")
    print("      SET MASKING POLICY metadata.pii_entities_mask;")
    print()
    print("  ✅ Masking active — sensitive data hidden from unauthorized roles")
    print()


def demo_role_switching(role: str):
    """Demonstrate different data visibility per role."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 3: Role-Based Visibility Demonstration                 │")
    print("│  Same query, different results based on active role           │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()

    roles_data = {
        "admin": {
            "role_name": "METADATA_ADMIN",
            "visible_rows": 1247,
            "file_path_visible": True,
            "pii_visible": True,
            "sample_results": [
                ("Q4_revenue.xlsx", "financial", "/vol1/finance/reports/Q4_revenue.xlsx"),
                ("pump_design.step", "engineering", "/vol1/eng/cad/pump_design.step"),
                ("employee_records.csv", "hr", "/vol1/hr/records/employee_records.csv"),
                ("safety_training.mp4", "training", "/vol1/shared/training/safety_training.mp4"),
                ("NDA_partner.pdf", "legal", "/vol1/legal/contracts/NDA_partner.pdf"),
            ],
        },
        "analyst": {
            "role_name": "FINANCE_TEAM",
            "visible_rows": 342,
            "file_path_visible": False,
            "pii_visible": False,
            "sample_results": [
                ("Q4_revenue.xlsx", "financial", "***/Q4_revenue.xlsx"),
                ("audit_report_2024.pdf", "compliance", "***/audit_report_2024.pdf"),
                ("NDA_partner.pdf", "legal", "***/NDA_partner.pdf"),
            ],
        },
        "engineer": {
            "role_name": "ENGINEERING_TEAM",
            "visible_rows": 589,
            "file_path_visible": False,
            "pii_visible": False,
            "sample_results": [
                ("pump_design.step", "engineering", "***/pump_design.step"),
                ("safety_training.mp4", "training", "***/safety_training.mp4"),
                ("API_docs_v3.md", "technical", "***/API_docs_v3.md"),
            ],
        },
    }

    # Show all roles
    for role_key, data in roles_data.items():
        is_current = (role_key == role)
        marker = " ◀ CURRENT" if is_current else ""
        print(f"  USE ROLE {data['role_name']};{marker}")
        print(f"  SELECT file_name, classification, file_path")
        print(f"    FROM unstructured_files LIMIT 5;")
        print()
        print(f"    Visible rows: {data['visible_rows']}")
        print(f"    file_path:    {'Full path visible' if data['file_path_visible'] else 'Masked (***/<filename>)'}")
        print(f"    pii_entities: {'Full PII data' if data['pii_visible'] else 'REDACTED'}")
        print()

        if is_current:
            print("    Results:")
            print("    file_name                classification  file_path")
            print("    ───────────────────────  ──────────────  ─────────────────────────────")
            for name, cls, path in data["sample_results"]:
                print(f"    {name:<25}  {cls:<14}  {path}")
            print()

        print("  ─────────────────────────────────────────────────────────")
        print()


def demo_audit_trail():
    """Demonstrate STORAGE_REQUEST_HISTORY for audit."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 4: Audit Trail (STORAGE_REQUEST_HISTORY)               │")
    print("│  Track all external engine access to Iceberg metadata         │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print("  SQL — Query access audit log:")
    print()
    print("    SELECT")
    print("      request_timestamp,")
    print("      user_name,")
    print("      role_name,")
    print("      request_type,")
    print("      table_name,")
    print("      credentials_used,")
    print("      client_application")
    print("    FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_REQUEST_HISTORY")
    print("    WHERE table_catalog = 'FSXN_METADATA_CATALOG'")
    print("    ORDER BY request_timestamp DESC")
    print("    LIMIT 10;")
    print()
    print("  Sample audit entries:")
    print()
    print("    timestamp            user        role            request_type  client")
    print("    ───────────────────  ──────────  ──────────────  ────────────  ──────────────")
    print("    2024-12-01 09:15:03  tanaka_k    FINANCE_TEAM    READ          Spark 3.5")
    print("    2024-12-01 09:12:45  suzuki_m    ENGINEERING     READ          Trino 435")
    print("    2024-12-01 08:55:12  admin_svc   METADATA_ADMIN  WRITE         PyIceberg 0.7")
    print("    2024-12-01 08:30:00  scheduler   METADATA_ADMIN  WRITE         Lambda (scan)")
    print("    2024-11-30 17:45:33  yamada_t    HR_TEAM         READ          Databricks RT")
    print()
    print("  ✅ All access logged — including external engines (Spark, Trino, Databricks)")
    print("  ✅ Policies enforced regardless of access method")
    print()


def demo_key_message():
    """Print key takeaway."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  💡 Key Message                                               │")
    print("├──────────────────────────────────────────────────────────────┤")
    print("│                                                              │")
    print("│  \"Same table, different views based on role —                 │")
    print("│   enforced on external engines too\"                           │")
    print("│                                                              │")
    print("│  Governance capabilities:                                    │")
    print("│    ✅ Row Access Policy — role-based row filtering            │")
    print("│    ✅ Dynamic Masking — column-level data protection          │")
    print("│    ✅ Cross-engine — Spark, Trino, Databricks all governed    │")
    print("│    ✅ Audit trail — who accessed what, when, from where       │")
    print("│    ✅ No application changes — policies at storage layer      │")
    print("│                                                              │")
    print("│  Compliance alignment:                                       │")
    print("│    • GDPR: PII masking + access audit                        │")
    print("│    • SOX: Financial data access controls                     │")
    print("│    • HIPAA: Healthcare data row-level isolation               │")
    print("│    • ISO 27001: Complete access audit trail                   │")
    print("│                                                              │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Horizon Catalog Governance Demo — Row access, masking, and audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python demo-horizon-governance.py
    python demo-horizon-governance.py --role analyst
    python demo-horizon-governance.py --role admin --show-audit
    python demo-horizon-governance.py --role engineer
        """,
    )
    parser.add_argument(
        "--role", choices=["admin", "analyst", "engineer"],
        default="analyst",
        help="Role to demonstrate visibility for (default: analyst)",
    )
    parser.add_argument(
        "--show-audit", action="store_true",
        help="Include audit trail demonstration",
    )
    args = parser.parse_args()

    print_header()
    demo_row_access_policy()
    demo_dynamic_masking()
    demo_role_switching(args.role)

    if args.show_audit:
        demo_audit_trail()

    demo_key_message()


if __name__ == "__main__":
    main()

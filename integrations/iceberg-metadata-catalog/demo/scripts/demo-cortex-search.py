#!/usr/bin/env python3
"""
demo-cortex-search.py — Snowflake Cortex Search Demo (S-2)

Demonstrates natural language metadata discovery using Snowflake Cortex Search.
Users can find files using conversational queries instead of SQL filters.

Key Message:
    "Find files using natural language, not just SQL filters"

Architecture:
    User NL Query → Cortex Search Service → Iceberg Metadata Table → Results
    (Automatic embedding + hybrid search — no manual vector pipeline needed)

Usage:
    python demo-cortex-search.py
    python demo-cortex-search.py --query "quarterly financial reports from last year"
    python demo-cortex-search.py --compare
"""

import argparse
import sys
import time


def print_header():
    """Print demo header."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  S-2: Cortex Search — Natural Language Metadata Discovery    ║")
    print("║  Engine: Snowflake Cortex Search (hybrid semantic + keyword) ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def demo_service_creation():
    """Show Cortex Search service creation SQL."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 1: Create Cortex Search Service                        │")
    print("│  One-time setup — automatic indexing and embedding           │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print("  SQL (Snowflake):")
    print()
    print("    CREATE OR REPLACE CORTEX SEARCH SERVICE")
    print("      fsxn_metadata_catalog.metadata.file_search_service")
    print("    ON summary                          -- Primary search column")
    print("    ATTRIBUTES")
    print("      file_name,                        -- Returned with results")
    print("      file_type,")
    print("      classification,")
    print("      confidence_score,")
    print("      file_size,")
    print("      last_modified")
    print("    WAREHOUSE = 'COMPUTE_WH'")
    print("    TARGET_LAG = '1 hour'               -- Auto-refresh interval")
    print("    AS (")
    print("      SELECT")
    print("        file_name,")
    print("        file_type,")
    print("        classification,")
    print("        confidence_score,")
    print("        file_size,")
    print("        last_modified,")
    print("        CONCAT(")
    print("          file_name, ' | ',")
    print("          COALESCE(classification, ''), ' | ',")
    print("          COALESCE(summary, '')")
    print("        ) AS summary                    -- Combined search text")
    print("      FROM fsxn_metadata_catalog.metadata.unstructured_files")
    print("      WHERE is_deleted = false")
    print("    );")
    print()
    print("  ✅ Service created — indexes automatically, refreshes hourly")
    print("  ✅ No manual embedding pipeline needed (Cortex handles it)")
    print()


def demo_natural_language_queries():
    """Demonstrate natural language queries."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 2: Natural Language Queries                            │")
    print("│  Search metadata using conversational language               │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()

    queries = [
        {
            "nl_query": "financial reports from Q4 with revenue data",
            "results": [
                {"file_name": "Q4_2024_revenue_report.xlsx", "classification": "financial",
                 "confidence": 0.97, "score": 0.94},
                {"file_name": "annual_financial_summary_2024.pdf", "classification": "financial",
                 "confidence": 0.95, "score": 0.87},
                {"file_name": "Q4_board_presentation_finance.pptx", "classification": "financial",
                 "confidence": 0.92, "score": 0.82},
            ],
        },
        {
            "nl_query": "engineering drawings for the new pump design",
            "results": [
                {"file_name": "centrifugal_pump_v4.step", "classification": "engineering",
                 "confidence": 0.96, "score": 0.91},
                {"file_name": "pump_assembly_drawing.dwg", "classification": "engineering",
                 "confidence": 0.94, "score": 0.88},
                {"file_name": "hydraulic_pump_specs.pdf", "classification": "engineering",
                 "confidence": 0.90, "score": 0.79},
            ],
        },
        {
            "nl_query": "training materials about workplace safety",
            "results": [
                {"file_name": "safety_training_2024.mp4", "classification": "training",
                 "confidence": 0.98, "score": 0.96},
                {"file_name": "workplace_hazard_guide.pdf", "classification": "compliance",
                 "confidence": 0.93, "score": 0.85},
                {"file_name": "emergency_procedures_v2.docx", "classification": "compliance",
                 "confidence": 0.91, "score": 0.78},
            ],
        },
    ]

    print("  Python (Snowflake Cortex Search SDK):")
    print()
    print("    from snowflake.core import Root")
    print()
    print("    root = Root(session)")
    print("    search_service = (root")
    print("      .databases['FSXN_METADATA_CATALOG']")
    print("      .schemas['METADATA']")
    print("      .cortex_search_services['FILE_SEARCH_SERVICE'])")
    print()
    print("    results = search_service.search(")
    print('      query="financial reports from Q4 with revenue data",')
    print("      columns=['file_name', 'classification', 'confidence_score'],")
    print("      limit=5")
    print("    )")
    print()

    for q in queries:
        time.sleep(0.3)
        print(f"  ─── Query: \"{q['nl_query']}\" ───")
        print()
        for i, r in enumerate(q["results"], 1):
            print(f"    {i}. {r['file_name']}")
            print(f"       Classification: {r['classification']} ({r['confidence']:.0%})")
            print(f"       Relevance: {r['score']:.2f}")
        print()


def demo_comparison_with_sql(query: str):
    """Compare natural language search with SQL-based search."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 3: Comparison — Natural Language vs SQL                 │")
    print("│  Same intent, different approaches                           │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()

    comparisons = [
        {
            "intent": "Find contracts expiring soon",
            "nl": 'search("contracts that are about to expire or need renewal")',
            "sql": (
                "SELECT * FROM unstructured_files\n"
                "    WHERE classification = 'legal'\n"
                "      AND file_type IN ('.pdf', '.docx')\n"
                "      AND (file_name LIKE '%contract%' OR file_name LIKE '%agreement%')\n"
                "      AND last_modified > DATEADD(month, -3, CURRENT_DATE())\n"
                "    ORDER BY last_modified DESC"
            ),
            "nl_advantage": "Finds 'renewal' and 'expiring' semantically — no exact keyword needed",
        },
        {
            "intent": "Find design documents similar to a reference",
            "nl": 'search("mechanical drawings similar to pump housing P-4200")',
            "sql": (
                "SELECT * FROM unstructured_files\n"
                "    WHERE classification = 'engineering'\n"
                "      AND file_type IN ('.dwg', '.step', '.stp')\n"
                "      AND file_name LIKE '%pump%housing%'\n"
                "    -- Cannot express 'similar to' in SQL without embeddings"
            ),
            "nl_advantage": "Semantic similarity — finds related designs even with different naming",
        },
        {
            "intent": "Find compliance documents for audit",
            "nl": 'search("documents needed for ISO 27001 security audit")',
            "sql": (
                "SELECT * FROM unstructured_files\n"
                "    WHERE classification IN ('compliance', 'security', 'policy')\n"
                "      AND (file_name LIKE '%ISO%' OR file_name LIKE '%audit%'\n"
                "           OR file_name LIKE '%security%' OR file_name LIKE '%policy%')\n"
                "    -- Misses documents about 'access control', 'incident response', etc."
            ),
            "nl_advantage": "Understands audit context — finds related policies automatically",
        },
    ]

    for comp in comparisons:
        print(f"  Intent: \"{comp['intent']}\"")
        print()
        print(f"  Natural Language (Cortex Search):")
        print(f"    {comp['nl']}")
        print()
        print(f"  SQL equivalent (approximate):")
        for line in comp["sql"].split("\n"):
            print(f"    {line}")
        print()
        print(f"  ✅ NL advantage: {comp['nl_advantage']}")
        print()
        print("  ─────────────────────────────────────────────────────────")
        print()


def demo_key_message():
    """Print key takeaway."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  💡 Key Message                                               │")
    print("├──────────────────────────────────────────────────────────────┤")
    print("│                                                              │")
    print("│  \"Find files using natural language, not just SQL filters\"    │")
    print("│                                                              │")
    print("│  Cortex Search advantages:                                   │")
    print("│    • No embedding pipeline to build or maintain              │")
    print("│    • Hybrid search (semantic + keyword) out of the box       │")
    print("│    • Auto-refresh from Iceberg table (TARGET_LAG)            │")
    print("│    • Works with existing Snowflake RBAC                      │")
    print("│    • Non-technical users can search without SQL knowledge    │")
    print("│                                                              │")
    print("│  Perfect for:                                                │")
    print("│    • Business users who don't know SQL                       │")
    print("│    • Fuzzy searches where exact keywords are unknown         │")
    print("│    • Semantic similarity (\"find similar to X\")               │")
    print("│    • Multi-language queries (JP/EN transparent)              │")
    print("│                                                              │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Cortex Search Demo — Natural language metadata discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python demo-cortex-search.py
    python demo-cortex-search.py --query "safety training videos"
    python demo-cortex-search.py --compare
        """,
    )
    parser.add_argument(
        "--query", default=None,
        help="Custom natural language query to demonstrate",
    )
    parser.add_argument(
        "--compare", action="store_true",
        help="Show NL vs SQL comparison for multiple scenarios",
    )
    args = parser.parse_args()

    print_header()
    demo_service_creation()
    demo_natural_language_queries()
    demo_comparison_with_sql(args.query or "")
    demo_key_message()


if __name__ == "__main__":
    main()

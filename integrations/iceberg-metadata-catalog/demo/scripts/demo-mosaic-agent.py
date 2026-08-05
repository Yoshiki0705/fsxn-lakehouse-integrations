#!/usr/bin/env python3
"""
demo-mosaic-agent.py — Mosaic AI Agent Demo (D-3)

Demonstrates how the Iceberg metadata catalog serves as a tool for
Databricks Mosaic AI Agents. The agent can autonomously discover and
access unstructured data stored on FSx for ONTAP.

Key Message:
    "AI agents can discover and access unstructured data autonomously"

Architecture:
    User Question → Mosaic AI Agent → Tool: search_metadata()
                                    → Tool: get_file_details()
                                    → Tool: generate_presigned_url()
                                    → Answer with evidence

This is a conceptual demo showing the pattern and conversation flow.
It does not require a live Databricks workspace to run.

Usage:
    python demo-mosaic-agent.py
    python demo-mosaic-agent.py --scenario contract-search
    python demo-mosaic-agent.py --scenario design-reuse
"""

import argparse
import json
import sys
import time


def print_header():
    """Print demo header."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  D-3: Mosaic AI Agent — Metadata Catalog as Agent Tool      ║")
    print("║  Pattern: Tool-augmented LLM with structured data access    ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def demo_tool_definitions():
    """Show the agent tool definitions."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 1: Agent Tool Definitions                              │")
    print("│  Register metadata catalog as tools for the AI agent         │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()

    tools = [
        {
            "name": "search_metadata",
            "description": "Search the FSx for ONTAP file metadata catalog using SQL or natural language",
            "parameters": {
                "query": "Natural language search query",
                "filters": "Optional: file_type, classification, date_range",
                "limit": "Max results (default: 10)",
            },
            "returns": "List of matching files with metadata",
        },
        {
            "name": "get_file_details",
            "description": "Get detailed metadata for a specific file including AI-generated summary",
            "parameters": {
                "file_name": "Name of the file",
                "include_summary": "Include AI-generated content summary",
            },
            "returns": "Full metadata record with classification and summary",
        },
        {
            "name": "generate_presigned_url",
            "description": "Generate a time-limited URL to access the actual file on FSx for ONTAP",
            "parameters": {
                "file_path": "Internal file path (from metadata)",
                "expiry_seconds": "URL validity period (default: 3600)",
            },
            "returns": "Presigned S3 URL for file download",
        },
    ]

    print("  Python (Databricks Agent Framework):")
    print()
    print("    from databricks.agents import tool")
    print()

    for t in tools:
        print(f"    @tool")
        print(f"    def {t['name']}(")
        for param, desc in t["parameters"].items():
            print(f"        {param}: str,  # {desc}")
        print(f"    ) -> dict:")
        print(f'        """{t["description"]}"""')
        print(f"        # Query Iceberg metadata table via Spark SQL")
        print(f"        ...")
        print()

    print("  Registered tools: 3")
    print("    • search_metadata    — Discovery (SQL/NL → metadata)")
    print("    • get_file_details   — Deep dive (file → full record)")
    print("    • generate_presigned_url — Access (metadata → file URL)")
    print()


def demo_conversation_flow(scenario: str):
    """Simulate an agent conversation flow."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 2: Agent Conversation Flow                             │")
    print("│  Simulated interaction showing autonomous tool usage          │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()

    scenarios = {
        "contract-search": {
            "user_query": "Find all contracts related to the Tanaka project from last quarter",
            "steps": [
                {
                    "thought": "User wants contracts for a specific project and time range. "
                               "I'll search the metadata catalog with filters.",
                    "tool": "search_metadata",
                    "args": {
                        "query": "contract Tanaka project",
                        "filters": {"classification": "legal", "date_range": "2024-Q3"},
                        "limit": 10,
                    },
                    "result": [
                        {"file_name": "Tanaka_NDA_2024.pdf", "classification": "legal",
                         "confidence": 0.97, "size": "245 KB"},
                        {"file_name": "Tanaka_MSA_v2.docx", "classification": "legal",
                         "confidence": 0.95, "size": "1.2 MB"},
                        {"file_name": "Tanaka_SOW_Q3.pdf", "classification": "legal",
                         "confidence": 0.93, "size": "890 KB"},
                    ],
                },
                {
                    "thought": "Found 3 contracts. Let me get details on the MSA "
                               "since it's likely the most comprehensive.",
                    "tool": "get_file_details",
                    "args": {"file_name": "Tanaka_MSA_v2.docx", "include_summary": True},
                    "result": {
                        "file_name": "Tanaka_MSA_v2.docx",
                        "summary": "Master Service Agreement between Corp and Tanaka Industries. "
                                   "Covers cloud infrastructure services, 3-year term, "
                                   "auto-renewal clause. Signed 2024-07-15.",
                        "last_modified": "2024-07-15T09:30:00Z",
                        "pii_detected": True,
                        "pii_types": ["PERSON_NAME", "ORGANIZATION"],
                    },
                },
            ],
            "final_answer": (
                "I found 3 contracts related to the Tanaka project from Q3 2024:\n"
                "  1. Tanaka_NDA_2024.pdf (245 KB) — Non-disclosure agreement\n"
                "  2. Tanaka_MSA_v2.docx (1.2 MB) — Master Service Agreement\n"
                "     Summary: 3-year cloud infrastructure services, signed 2024-07-15\n"
                "  3. Tanaka_SOW_Q3.pdf (890 KB) — Statement of Work\n\n"
                "The MSA (v2) is the most recent and comprehensive. "
                "Would you like me to generate a download link?"
            ),
        },
        "design-reuse": {
            "user_query": "Are there any existing CAD designs for a pump housing similar to part P-4500?",
            "steps": [
                {
                    "thought": "User wants to find similar CAD designs for reuse. "
                               "I'll search for pump housing designs in engineering files.",
                    "tool": "search_metadata",
                    "args": {
                        "query": "pump housing CAD design P-4500",
                        "filters": {"classification": "engineering", "file_type": [".dwg", ".step", ".stp"]},
                        "limit": 10,
                    },
                    "result": [
                        {"file_name": "P-4200_pump_housing_v3.step", "classification": "engineering",
                         "confidence": 0.96, "size": "15.4 MB"},
                        {"file_name": "P-4350_centrifugal_housing.dwg", "classification": "engineering",
                         "confidence": 0.94, "size": "8.7 MB"},
                        {"file_name": "pump_housing_template_2023.step", "classification": "engineering",
                         "confidence": 0.91, "size": "12.1 MB"},
                    ],
                },
                {
                    "thought": "Found 3 similar designs. P-4200 is closest in part number. "
                               "Let me get its details.",
                    "tool": "get_file_details",
                    "args": {"file_name": "P-4200_pump_housing_v3.step", "include_summary": True},
                    "result": {
                        "file_name": "P-4200_pump_housing_v3.step",
                        "summary": "3D STEP model of centrifugal pump housing. "
                                   "Material: Cast iron FC250. Dimensions: 320x280x195mm. "
                                   "Designed for 50Hz/60Hz dual operation. Rev 3 (final).",
                        "last_modified": "2023-11-20T14:22:00Z",
                    },
                },
            ],
            "final_answer": (
                "Yes! I found 3 existing pump housing designs that may be reusable:\n\n"
                "  1. P-4200_pump_housing_v3.step (15.4 MB) — Most similar\n"
                "     Cast iron FC250, 320x280x195mm, dual 50/60Hz\n"
                "     Last modified: 2023-11-20 (Rev 3 — final)\n\n"
                "  2. P-4350_centrifugal_housing.dwg (8.7 MB)\n"
                "  3. pump_housing_template_2023.step (12.1 MB) — Generic template\n\n"
                "P-4200 is the closest match to P-4500. Reusing this design could save\n"
                "~3 days of CAD work. Want me to generate a download link?"
            ),
        },
    }

    conv = scenarios.get(scenario, scenarios["contract-search"])

    print(f"  👤 User: \"{conv['user_query']}\"")
    print()

    for i, step in enumerate(conv["steps"], 1):
        time.sleep(0.3)
        print(f"  🤖 Agent (thinking): {step['thought']}")
        print()
        time.sleep(0.2)
        print(f"     → Calling tool: {step['tool']}({json.dumps(step['args'], ensure_ascii=False)[:60]}...)")
        time.sleep(0.3)
        print(f"     ← Result: {json.dumps(step['result'], ensure_ascii=False)[:80]}...")
        print()

    time.sleep(0.3)
    print(f"  🤖 Agent (final answer):")
    print()
    for line in conv["final_answer"].split("\n"):
        print(f"     {line}")
    print()


def demo_architecture_diagram():
    """Show the architecture pattern."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Architecture: Agent + Metadata Catalog                      │")
    print("├──────────────────────────────────────────────────────────────┤")
    print("│                                                              │")
    print("│   User Question                                              │")
    print("│        │                                                     │")
    print("│        ▼                                                     │")
    print("│   ┌─────────────┐    ┌──────────────────────┐               │")
    print("│   │ Mosaic AI   │───▶│ search_metadata()    │               │")
    print("│   │ Agent       │    │ get_file_details()   │               │")
    print("│   │ (LLM +      │    │ generate_presigned() │               │")
    print("│   │  Tools)     │    └──────────┬───────────┘               │")
    print("│   └──────┬──────┘               │                           │")
    print("│          │                      ▼                           │")
    print("│          │         ┌──────────────────────┐                 │")
    print("│          │         │ Iceberg Metadata     │                 │")
    print("│          │         │ Table (S3 Tables)    │                 │")
    print("│          │         └──────────┬───────────┘                 │")
    print("│          │                    │                             │")
    print("│          ▼                    ▼                             │")
    print("│   Answer with          FSx for ONTAP                        │")
    print("│   evidence             (actual files)                       │")
    print("│                                                              │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()


def demo_key_message():
    """Print key takeaway."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  💡 Key Message                                               │")
    print("├──────────────────────────────────────────────────────────────┤")
    print("│                                                              │")
    print("│  \"AI agents can discover and access unstructured data         │")
    print("│   autonomously\"                                              │")
    print("│                                                              │")
    print("│  Without metadata catalog:                                   │")
    print("│    Agent cannot search files → asks user to find manually    │")
    print("│                                                              │")
    print("│  With metadata catalog:                                      │")
    print("│    Agent searches catalog → finds relevant files → provides  │")
    print("│    answers with evidence → offers download links             │")
    print("│                                                              │")
    print("│  Value: Transform unstructured storage into agent-queryable  │")
    print("│         knowledge base — no ETL, no data movement            │")
    print("│                                                              │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Mosaic AI Agent Demo — Metadata catalog as an agent tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scenarios:
    contract-search  — Legal team finding project contracts
    design-reuse     — Engineering team finding reusable CAD designs

Examples:
    python demo-mosaic-agent.py
    python demo-mosaic-agent.py --scenario design-reuse
    python demo-mosaic-agent.py --scenario contract-search
        """,
    )
    parser.add_argument(
        "--scenario", choices=["contract-search", "design-reuse"],
        default="contract-search",
        help="Demo scenario to run (default: contract-search)",
    )
    args = parser.parse_args()

    print_header()
    demo_tool_definitions()
    demo_conversation_flow(args.scenario)
    demo_architecture_diagram()
    demo_key_message()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
compile_metrics.py - Aggregate test results into a verification report.

Reads JSON result files from the tests/results/ directory and compiles them
into a structured Markdown report with performance metrics and pass/fail
status for each acceptance criterion (REQ-1 through REQ-7).

Usage:
    python compile_metrics.py
    python compile_metrics.py --results-dir integrations/snowflake/tests/results

Output:
    integrations/snowflake/tests/results/report.md

Result File Conventions:
    - snowpark_validation.json      (REQ-7: Snowpark UDF)
    - access_validation.json        (REQ-1: Storage Integration / S3 AP)
    - snowpipe_e2e_results.json     (REQ-4: Snowpipe auto-ingest)
    - external_table_results.json   (REQ-2: External Table)
    - iceberg_results.json          (REQ-3: Iceberg Table)
    - data_sharing_results.json     (REQ-5: Secure Data Sharing)
    - directory_table_results.json  (REQ-6: Unstructured Data)
    - latency_comparison.json       (REQ-4: Snowpipe latency)
    - document_catalog_results.json (REQ-6, REQ-7: Document metadata)
    - ontap_storage_metrics.json    (ONTAP dedup/compression savings)

Requirements: REQ-1 through REQ-7
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# =============================================================================
# Constants
# =============================================================================

DEFAULT_RESULTS_DIR = "integrations/snowflake/tests/results"
REPORT_FILENAME = "report.md"

# Mapping of result files to demo scenarios and requirements
RESULT_FILE_MAP = {
    "access_validation.json": {
        "scenario": "Infrastructure",
        "requirements": ["REQ-1"],
        "description": "Storage Integration & S3 Access Point",
    },
    "external_table_results.json": {
        "scenario": "D-1",
        "requirements": ["REQ-2"],
        "description": "External Table Query (Structured Data)",
    },
    "iceberg_results.json": {
        "scenario": "D-2",
        "requirements": ["REQ-3"],
        "description": "Iceberg Table with DML & Time Travel",
    },
    "snowpipe_e2e_results.json": {
        "scenario": "D-3",
        "requirements": ["REQ-4"],
        "description": "Snowpipe Auto-Ingest (FPolicy Event-Driven)",
    },
    "latency_comparison.json": {
        "scenario": "D-3",
        "requirements": ["REQ-4"],
        "description": "Snowpipe Latency Comparison (FPolicy vs Polling)",
    },
    "data_sharing_results.json": {
        "scenario": "D-4",
        "requirements": ["REQ-5"],
        "description": "Secure Data Sharing",
    },
    "directory_table_results.json": {
        "scenario": "D-5",
        "requirements": ["REQ-6"],
        "description": "Unstructured Data — Directory Table & Pre-signed URLs",
    },
    "snowpark_validation.json": {
        "scenario": "D-6",
        "requirements": ["REQ-7"],
        "description": "Snowpark UDF Processing",
    },
    "document_catalog_results.json": {
        "scenario": "D-7",
        "requirements": ["REQ-6", "REQ-7"],
        "description": "Document Metadata Catalog",
    },
    "ontap_storage_metrics.json": {
        "scenario": "ONTAP",
        "requirements": ["REQ-1"],
        "description": "ONTAP Storage Efficiency (Dedup/Compression)",
    },
}

# Acceptance criteria per requirement
ACCEPTANCE_CRITERIA = {
    "REQ-1": "Storage Integration with IAM Role (two-phase trust setup)",
    "REQ-2": "External Table queries on Parquet, CSV, JSON via S3 AP",
    "REQ-3": "Iceberg Table with DML (INSERT/UPDATE/DELETE) and Time Travel",
    "REQ-4": "Snowpipe auto-ingest via FPolicy event-driven pipeline (<30s)",
    "REQ-5": "Secure Data Sharing with row/column filtering and revocation",
    "REQ-6": "Unstructured Data via Directory Table + Pre-signed URLs",
    "REQ-7": "Snowpark UDF processing for media/document files",
}


# =============================================================================
# Result File Parsing
# =============================================================================


def load_result_file(filepath):
    """Load a JSON result file. Returns None if file doesn't exist."""
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  ⚠️  Warning: Could not parse {filepath.name}: {e}")
        return None


def load_all_results(results_dir):
    """Load all known result files from the results directory."""
    results = {}
    results_path = Path(results_dir)

    for filename, metadata in RESULT_FILE_MAP.items():
        filepath = results_path / filename
        data = load_result_file(filepath)
        results[filename] = {
            "data": data,
            "found": data is not None,
            **metadata,
        }

    # Also scan for any additional JSON files not in the map
    if results_path.exists():
        for json_file in results_path.glob("*.json"):
            if json_file.name not in RESULT_FILE_MAP:
                data = load_result_file(json_file)
                results[json_file.name] = {
                    "data": data,
                    "found": data is not None,
                    "scenario": "Other",
                    "requirements": [],
                    "description": json_file.stem.replace("_", " ").title(),
                }

    return results


# =============================================================================
# Metrics Extraction
# =============================================================================


def extract_status(result_data):
    """Extract pass/fail status from a result data dict."""
    if result_data is None:
        return "NOT RUN"

    # Common patterns for status in result files
    for key in ("status", "result", "overall_status", "test_status"):
        if key in result_data:
            val = str(result_data[key]).upper()
            if val in ("PASS", "PASSED", "SUCCESS", "OK", "TRUE"):
                return "PASS"
            elif val in ("FAIL", "FAILED", "ERROR", "FALSE"):
                return "FAIL"
            return val

    # Check for nested tests array
    if "tests" in result_data and isinstance(result_data["tests"], list):
        all_pass = all(
            extract_status(t) == "PASS" for t in result_data["tests"]
        )
        return "PASS" if all_pass else "FAIL"

    # If data exists but no explicit status, consider it informational
    return "INFO"


def extract_performance_metrics(results):
    """Extract performance metrics from all result files."""
    metrics = {
        "query_latency": {},
        "snowpipe_latency": {},
        "udf_execution_time": {},
        "ontap_dedup_savings": {},
    }

    # External Table query latency
    ext_data = results.get("external_table_results.json", {}).get("data")
    if ext_data:
        for key in ("query_time_ms", "query_latency_ms", "avg_query_time_ms",
                    "bytes_scanned", "row_count"):
            if key in ext_data:
                metrics["query_latency"][key] = ext_data[key]
        # Check nested queries
        if "queries" in ext_data and isinstance(ext_data["queries"], list):
            for q in ext_data["queries"]:
                name = q.get("name", q.get("query_name", "unknown"))
                latency = q.get("execution_time_ms", q.get("latency_ms"))
                if latency is not None:
                    metrics["query_latency"][name] = f"{latency} ms"

    # Iceberg DML latency
    ice_data = results.get("iceberg_results.json", {}).get("data")
    if ice_data:
        for key in ("insert_time_ms", "update_time_ms", "delete_time_ms",
                    "time_travel_query_ms", "dml_latency_ms"):
            if key in ice_data:
                metrics["query_latency"][f"iceberg_{key}"] = ice_data[key]

    # Snowpipe latency
    pipe_data = results.get("snowpipe_e2e_results.json", {}).get("data")
    if pipe_data:
        for key in ("end_to_end_latency_seconds", "latency_seconds",
                    "detection_time_seconds", "copy_time_seconds",
                    "total_latency_ms"):
            if key in pipe_data:
                metrics["snowpipe_latency"][key] = pipe_data[key]

    # Latency comparison (FPolicy vs Polling)
    lat_data = results.get("latency_comparison.json", {}).get("data")
    if lat_data:
        for key in ("fpolicy_latency_seconds", "polling_latency_seconds",
                    "improvement_percent", "fpolicy_avg_ms", "polling_avg_ms"):
            if key in lat_data:
                metrics["snowpipe_latency"][key] = lat_data[key]

    # UDF execution time
    udf_data = results.get("snowpark_validation.json", {}).get("data")
    if udf_data:
        for key in ("udf_execution_time_ms", "execution_time_ms",
                    "avg_udf_time_ms", "classification_accuracy",
                    "success_rate"):
            if key in udf_data:
                metrics["udf_execution_time"][key] = udf_data[key]

    # Document catalog UDF
    doc_data = results.get("document_catalog_results.json", {}).get("data")
    if doc_data:
        for key in ("processing_time_ms", "catalog_completeness",
                    "files_processed", "avg_extraction_time_ms"):
            if key in doc_data:
                metrics["udf_execution_time"][f"doc_{key}"] = doc_data[key]

    # ONTAP storage metrics
    ontap_data = results.get("ontap_storage_metrics.json", {}).get("data")
    if ontap_data:
        for key in ("dedup_savings_percent", "compression_ratio",
                    "total_savings_percent", "logical_used_bytes",
                    "physical_used_bytes", "dedup_ratio"):
            if key in ontap_data:
                metrics["ontap_dedup_savings"][key] = ontap_data[key]

    return metrics


# =============================================================================
# Report Generation
# =============================================================================


def generate_summary_table(results):
    """Generate the summary table section of the report."""
    lines = []
    lines.append("## Summary")
    lines.append("")
    lines.append("| Scenario | Description | Requirements | Status |")
    lines.append("|----------|-------------|--------------|--------|")

    # Order by scenario
    scenario_order = [
        "Infrastructure", "D-1", "D-2", "D-3", "D-4", "D-5", "D-6", "D-7", "ONTAP", "Other"
    ]

    seen_scenarios = set()
    for scenario in scenario_order:
        for filename, info in sorted(results.items()):
            if info["scenario"] == scenario and filename not in seen_scenarios:
                seen_scenarios.add(filename)
                status = extract_status(info["data"])
                status_icon = _status_icon(status)
                reqs = ", ".join(info["requirements"]) if info["requirements"] else "—"
                lines.append(
                    f"| {info['scenario']} | {info['description']} | {reqs} | {status_icon} {status} |"
                )

    lines.append("")
    return "\n".join(lines)


def generate_acceptance_criteria_section(results):
    """Generate acceptance criteria pass/fail section."""
    lines = []
    lines.append("## Acceptance Criteria")
    lines.append("")
    lines.append("| Requirement | Criteria | Status |")
    lines.append("|-------------|----------|--------|")

    for req_id, criteria in ACCEPTANCE_CRITERIA.items():
        # Find all results that map to this requirement
        related_results = [
            info for info in results.values()
            if req_id in info.get("requirements", [])
        ]

        if not related_results:
            status = "NOT RUN"
        elif all(extract_status(r["data"]) == "PASS" for r in related_results if r["found"]):
            if any(r["found"] for r in related_results):
                status = "PASS"
            else:
                status = "NOT RUN"
        elif any(extract_status(r["data"]) == "FAIL" for r in related_results):
            status = "FAIL"
        else:
            status = "PARTIAL"

        status_icon = _status_icon(status)
        lines.append(f"| {req_id} | {criteria} | {status_icon} {status} |")

    lines.append("")
    return "\n".join(lines)


def generate_performance_section(metrics):
    """Generate performance metrics section."""
    lines = []
    lines.append("## Performance Metrics")
    lines.append("")

    # Query Latency
    lines.append("### Query Latency")
    lines.append("")
    if metrics["query_latency"]:
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for key, value in metrics["query_latency"].items():
            label = key.replace("_", " ").title()
            lines.append(f"| {label} | {value} |")
    else:
        lines.append("_No query latency data available._")
    lines.append("")

    # Snowpipe Latency
    lines.append("### Snowpipe Latency")
    lines.append("")
    if metrics["snowpipe_latency"]:
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for key, value in metrics["snowpipe_latency"].items():
            label = key.replace("_", " ").title()
            lines.append(f"| {label} | {value} |")
    else:
        lines.append("_No Snowpipe latency data available._")
    lines.append("")

    # UDF Execution Time
    lines.append("### UDF Execution Time")
    lines.append("")
    if metrics["udf_execution_time"]:
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for key, value in metrics["udf_execution_time"].items():
            label = key.replace("_", " ").title()
            lines.append(f"| {label} | {value} |")
    else:
        lines.append("_No UDF execution time data available._")
    lines.append("")

    # ONTAP Dedup Savings
    lines.append("### ONTAP Storage Efficiency")
    lines.append("")
    if metrics["ontap_dedup_savings"]:
        lines.append("| Metric | Value |")
        lines.append("|--------|-------|")
        for key, value in metrics["ontap_dedup_savings"].items():
            label = key.replace("_", " ").title()
            lines.append(f"| {label} | {value} |")
    else:
        lines.append("_No ONTAP storage metrics available._")
    lines.append("")

    return "\n".join(lines)


def generate_detailed_sections(results):
    """Generate detailed sections for each demo scenario."""
    lines = []
    lines.append("## Detailed Results")
    lines.append("")

    scenario_order = [
        ("D-1", "External Table Query (Structured Data)"),
        ("D-2", "Iceberg Table with DML & Time Travel"),
        ("D-3", "Snowpipe Auto-Ingest (FPolicy Event-Driven)"),
        ("D-4", "Secure Data Sharing"),
        ("D-5", "Unstructured Data — Directory Table"),
        ("D-6", "Snowpark UDF Processing"),
        ("D-7", "Document Metadata Catalog"),
    ]

    for scenario_id, scenario_title in scenario_order:
        lines.append(f"### {scenario_id}: {scenario_title}")
        lines.append("")

        # Find all results for this scenario
        scenario_results = [
            (fname, info) for fname, info in results.items()
            if info["scenario"] == scenario_id
        ]

        if not scenario_results:
            lines.append("_No test results available for this scenario._")
            lines.append("")
            continue

        for filename, info in scenario_results:
            status = extract_status(info["data"])
            status_icon = _status_icon(status)
            lines.append(f"**{info['description']}** ({filename}): {status_icon} {status}")
            lines.append("")

            if info["data"] and isinstance(info["data"], dict):
                # Output key metrics from the result data
                detail_keys = _get_detail_keys(info["data"])
                if detail_keys:
                    lines.append("| Key | Value |")
                    lines.append("|-----|-------|")
                    for k, v in detail_keys:
                        lines.append(f"| {k} | {v} |")
                    lines.append("")

                # Output test details if present
                if "tests" in info["data"] and isinstance(info["data"]["tests"], list):
                    lines.append("| Test | Status |")
                    lines.append("|------|--------|")
                    for test in info["data"]["tests"]:
                        test_name = test.get("name", test.get("test_name", "—"))
                        test_status = extract_status(test)
                        test_icon = _status_icon(test_status)
                        lines.append(f"| {test_name} | {test_icon} {test_status} |")
                    lines.append("")

                # Output error/message if present
                for msg_key in ("error", "message", "notes"):
                    if msg_key in info["data"] and info["data"][msg_key]:
                        lines.append(f"> **{msg_key.title()}**: {info['data'][msg_key]}")
                        lines.append("")

    return "\n".join(lines)


def generate_report(results, metrics, results_dir):
    """Generate the full Markdown report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # Count statuses
    total = len([r for r in results.values() if r["found"]])
    passed = len([
        r for r in results.values()
        if r["found"] and extract_status(r["data"]) == "PASS"
    ])
    failed = len([
        r for r in results.values()
        if r["found"] and extract_status(r["data"]) == "FAIL"
    ])
    not_run = len([r for r in results.values() if not r["found"]])

    sections = []

    # Header
    sections.append("# FSx for ONTAP × Snowflake Integration — Verification Report")
    sections.append("")
    sections.append(f"**Generated**: {now}  ")
    sections.append(f"**Results Directory**: `{results_dir}`  ")
    sections.append(f"**Total Tests**: {total} run, {passed} passed, {failed} failed, {not_run} not run")
    sections.append("")
    sections.append("---")
    sections.append("")

    # Summary table
    sections.append(generate_summary_table(results))

    # Acceptance criteria
    sections.append(generate_acceptance_criteria_section(results))

    # Performance metrics
    sections.append(generate_performance_section(metrics))

    # Detailed results
    sections.append(generate_detailed_sections(results))

    # Footer
    sections.append("---")
    sections.append("")
    sections.append("## Notes")
    sections.append("")
    sections.append("- Results are aggregated from JSON files in the results directory.")
    sections.append("- Performance metrics depend on warehouse size and network conditions.")
    sections.append("- Snowpipe latency includes FPolicy detection + SQS + Lambda + SNS + COPY INTO.")
    sections.append("- ONTAP dedup savings are measured at the volume level.")
    sections.append(f"- Report generated by `compile_metrics.py` at {now}.")
    sections.append("")

    return "\n".join(sections)


# =============================================================================
# Helpers
# =============================================================================


def _status_icon(status):
    """Return an emoji icon for a given status string."""
    icons = {
        "PASS": "✅",
        "FAIL": "❌",
        "NOT RUN": "⬜",
        "PARTIAL": "🟡",
        "INFO": "ℹ️",
    }
    return icons.get(status, "❓")


def _get_detail_keys(data):
    """Extract notable key-value pairs from result data for display."""
    skip_keys = {"status", "result", "overall_status", "test_status",
                 "tests", "error", "message", "notes", "timestamp",
                 "verified_at", "generated_at"}
    pairs = []
    for key, value in data.items():
        if key in skip_keys:
            continue
        if isinstance(value, (dict, list)):
            continue
        label = key.replace("_", " ").title()
        pairs.append((label, value))
    # Limit to 10 most relevant keys
    return pairs[:10]


# =============================================================================
# CLI
# =============================================================================


def create_parser():
    parser = argparse.ArgumentParser(
        description="Compile test results into a verification report"
    )
    parser.add_argument(
        "--results-dir",
        default=DEFAULT_RESULTS_DIR,
        help=f"Directory containing JSON result files (default: {DEFAULT_RESULTS_DIR})",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output report path (default: <results-dir>/report.md)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed processing information",
    )
    return parser


# =============================================================================
# Main
# =============================================================================


def main():
    parser = create_parser()
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    output_path = Path(args.output) if args.output else results_dir / REPORT_FILENAME

    print(f"\n{'='*60}")
    print("FSx for ONTAP × Snowflake — Metrics Compilation")
    print(f"{'='*60}")
    print(f"  Results dir:  {results_dir}")
    print(f"  Output:       {output_path}")
    print(f"  Time:         {datetime.now(timezone.utc).isoformat()}")
    print(f"{'='*60}\n")

    # Ensure results directory exists
    if not results_dir.exists():
        print(f"  ⚠️  Results directory does not exist: {results_dir}")
        print("     Creating directory...")
        results_dir.mkdir(parents=True, exist_ok=True)

    # Load all result files
    print("  Loading result files...")
    results = load_all_results(results_dir)

    found_count = sum(1 for r in results.values() if r["found"])
    total_count = len(results)
    print(f"  Found {found_count}/{total_count} result files\n")

    if args.verbose:
        for filename, info in sorted(results.items()):
            icon = "✅" if info["found"] else "⬜"
            print(f"    {icon} {filename}")
        print()

    # Extract performance metrics
    print("  Extracting performance metrics...")
    metrics = extract_performance_metrics(results)

    metric_count = sum(len(v) for v in metrics.values())
    print(f"  Extracted {metric_count} metric(s)\n")

    # Generate report
    print("  Generating report...")
    report_content = generate_report(results, metrics, str(results_dir))

    # Write report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    print(f"  ✅ Report written to: {output_path}")
    print(f"     Size: {len(report_content)} bytes")
    print()

    # Print quick summary
    passed = len([
        r for r in results.values()
        if r["found"] and extract_status(r["data"]) == "PASS"
    ])
    failed = len([
        r for r in results.values()
        if r["found"] and extract_status(r["data"]) == "FAIL"
    ])
    print(f"  Summary: {passed} passed, {failed} failed, {found_count} total run")
    print()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
FSxN Athena Integration — Query Execution Script

Submits Athena queries, waits for results, and records execution metrics
(query time, data scanned, cost).

Usage:
    python execute_queries.py [--workgroup fsxn-verification] [--database fsxn_athena_db]
"""

import argparse
import json
import time
from pathlib import Path

import boto3


class AthenaQueryRunner:
    """Executes Athena queries and collects metrics."""

    COST_PER_TB = 5.0  # USD per TB scanned

    def __init__(self, workgroup: str, database: str, region: str = "ap-northeast-1"):
        self.client = boto3.client("athena", region_name=region)
        self.workgroup = workgroup
        self.database = database
        self.results = []

    def execute_query(self, query: str, label: str = "") -> dict:
        """Submit query and wait for completion."""
        print(f"  ▶ Executing: {label or query[:60]}...")

        response = self.client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={"Database": self.database},
            WorkGroup=self.workgroup,
        )
        execution_id = response["QueryExecutionId"]

        # Poll for completion
        while True:
            status = self.client.get_query_execution(QueryExecutionId=execution_id)
            state = status["QueryExecution"]["Status"]["State"]

            if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
                break
            time.sleep(1)

        execution = status["QueryExecution"]
        result = {
            "label": label,
            "query_id": execution_id,
            "state": state,
            "query": query[:200],
        }

        if state == "SUCCEEDED":
            stats = execution.get("Statistics", {})
            result["execution_time_ms"] = stats.get("EngineExecutionTimeInMillis", 0)
            result["data_scanned_bytes"] = stats.get("DataScannedInBytes", 0)
            result["data_scanned_mb"] = result["data_scanned_bytes"] / (1024 * 1024)
            result["cost_usd"] = (result["data_scanned_bytes"] / (1024**4)) * self.COST_PER_TB
            result["total_time_ms"] = stats.get("TotalExecutionTimeInMillis", 0)

            print(f"    ✅ {result['execution_time_ms']}ms | "
                  f"{result['data_scanned_mb']:.2f} MB scanned | "
                  f"${result['cost_usd']:.6f}")
        else:
            reason = execution["Status"].get("StateChangeReason", "Unknown")
            result["error"] = reason
            print(f"    ❌ {state}: {reason}")

        self.results.append(result)
        return result

    def run_sql_file(self, sql_file: Path) -> list:
        """Execute all queries in a SQL file (separated by semicolons)."""
        content = sql_file.read_text()

        # Split by semicolons, skip comments and empty
        queries = []
        for block in content.split(";"):
            # Remove comment lines
            lines = [l for l in block.strip().split("\n")
                     if l.strip() and not l.strip().startswith("--")]
            query = "\n".join(lines).strip()
            if query:
                queries.append(query)

        print(f"\n📄 Running {sql_file.name} ({len(queries)} queries)")
        print("-" * 60)

        results = []
        for i, query in enumerate(queries, 1):
            # Extract label from first line or use index
            first_line = query.split("\n")[0][:60]
            label = f"{sql_file.stem}_Q{i}: {first_line}"
            result = self.execute_query(query, label)
            results.append(result)

        return results

    def generate_report(self, output_path: Path) -> None:
        """Generate metrics report."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        successful = [r for r in self.results if r["state"] == "SUCCEEDED"]
        failed = [r for r in self.results if r["state"] != "SUCCEEDED"]

        report = {
            "summary": {
                "total_queries": len(self.results),
                "successful": len(successful),
                "failed": len(failed),
                "total_data_scanned_mb": sum(r.get("data_scanned_mb", 0) for r in successful),
                "total_cost_usd": sum(r.get("cost_usd", 0) for r in successful),
                "avg_execution_time_ms": (
                    sum(r.get("execution_time_ms", 0) for r in successful) / len(successful)
                    if successful else 0
                ),
            },
            "queries": self.results,
        }

        with open(output_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n📊 Report saved to: {output_path}")
        print(f"   Total queries: {report['summary']['total_queries']}")
        print(f"   Successful: {report['summary']['successful']}")
        print(f"   Total data scanned: {report['summary']['total_data_scanned_mb']:.2f} MB")
        print(f"   Total cost: ${report['summary']['total_cost_usd']:.6f}")
        print(f"   Avg execution time: {report['summary']['avg_execution_time_ms']:.0f} ms")


def main():
    parser = argparse.ArgumentParser(description="Execute Athena queries on FSxN data")
    parser.add_argument("--workgroup", default="fsxn-verification")
    parser.add_argument("--database", default="fsxn_athena_db")
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--sql-dir", default=None, help="Directory with SQL files to execute")
    parser.add_argument("--output", default="tests/results/query_metrics.json")
    args = parser.parse_args()

    script_dir = Path(__file__).parent.parent
    sql_dir = Path(args.sql_dir) if args.sql_dir else script_dir / "sql"
    output_path = script_dir / args.output

    print("=" * 60)
    print("FSxN Athena Integration — Query Execution")
    print("=" * 60)
    print(f"Workgroup: {args.workgroup}")
    print(f"Database:  {args.database}")
    print(f"Region:    {args.region}")
    print(f"SQL dir:   {sql_dir}")

    runner = AthenaQueryRunner(args.workgroup, args.database, args.region)

    # Execute SQL files in order
    sql_files = sorted(sql_dir.glob("*.sql"))
    if not sql_files:
        print(f"\n❌ No SQL files found in {sql_dir}")
        return

    for sql_file in sql_files:
        runner.run_sql_file(sql_file)

    # Generate report
    runner.generate_report(output_path)


if __name__ == "__main__":
    main()

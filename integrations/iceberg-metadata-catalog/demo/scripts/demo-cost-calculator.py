#!/usr/bin/env python3
"""
demo-cost-calculator.py — Demo Cost & ROI Calculator

Shows:
  1. Actual cost of this demo session
  2. Projected monthly cost at customer scale
  3. ROI calculation (savings vs current approach)

Usage:
    python demo-cost-calculator.py --files-processed 5 --queries-run 10
    python demo-cost-calculator.py --customer-files 100000 --customer-changes-per-day 1000
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="Cost & ROI Calculator")
    parser.add_argument("--files-processed", type=int, default=5, help="Files processed in this demo")
    parser.add_argument("--queries-run", type=int, default=10, help="Athena queries run in this demo")
    parser.add_argument("--customer-files", type=int, default=100000, help="Customer total file count")
    parser.add_argument("--customer-data-tb", type=float, default=10, help="Customer data volume in TB")
    parser.add_argument("--customer-changes-per-day", type=int, default=1000, help="Daily file changes")
    parser.add_argument("--analysts", type=int, default=10, help="Number of data analysts")
    parser.add_argument("--hours-searching-per-week", type=float, default=5, help="Hours/week spent searching for data")
    parser.add_argument("--hourly-rate", type=float, default=75, help="Analyst hourly rate (USD)")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Cost & ROI Calculator                                       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # =========================================================================
    # Section 1: This Demo Session Cost
    # =========================================================================
    demo_bedrock = args.files_processed * 0.01  # $0.01/file
    demo_athena = args.queries_run * 0.000005  # ~$5/TB scanned, metadata is tiny
    demo_lambda = args.files_processed * 0.0001  # Lambda cost
    demo_opensearch = 0.24 * 0.1  # ~6 min of 1 OCU
    demo_total = demo_bedrock + demo_athena + demo_lambda + demo_opensearch

    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  This Demo Session Cost                                       │")
    print("├──────────────────────────────────────────────────────────────┤")
    print(f"│  Bedrock AI ({args.files_processed} files × $0.01):     ${demo_bedrock:>8.4f}          │")
    print(f"│  Athena ({args.queries_run} queries):              ${demo_athena:>8.6f}          │")
    print(f"│  Lambda processing:                ${demo_lambda:>8.4f}          │")
    print(f"│  OpenSearch (~6 min active):        ${demo_opensearch:>8.4f}          │")
    print(f"│                                                              │")
    print(f"│  💰 Total demo cost:                ${demo_total:>8.4f}          │")
    print(f"│  💤 Idle cost after demo:           $   0.0000          │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # Section 2: Projected Monthly Cost at Customer Scale
    # =========================================================================
    monthly_s3tables = 5  # ~$5 for metadata
    monthly_lambda = (args.customer_changes_per_day * 30 * 0.0002) + (args.customer_changes_per_day * 30 * 0.01 * 0.1)  # sync + enrichment subset
    monthly_bedrock = args.customer_changes_per_day * 30 * 0.1 * 0.01  # 10% new files need AI
    monthly_opensearch = 0.24 * 8 * 22  # 8 hours/day, 22 days/month active
    monthly_sqs = 1
    monthly_total = monthly_s3tables + monthly_lambda + monthly_bedrock + monthly_opensearch + monthly_sqs

    # Current cost (S3 copy)
    current_s3_cost = args.customer_data_tb * 23  # $23/TB/month for S3 Standard

    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Projected Monthly Cost (Customer Scale)                      │")
    print(f"│  Files: {args.customer_files:>10,}  |  Data: {args.customer_data_tb:.0f} TB  |  Changes: {args.customer_changes_per_day:,}/day  │")
    print("├──────────────────────────────────────────────────────────────┤")
    print(f"│  S3 Tables (metadata):              ${monthly_s3tables:>8.0f}/month       │")
    print(f"│  Lambda (sync + AI):                ${monthly_lambda:>8.0f}/month       │")
    print(f"│  Bedrock (AI enrichment):           ${monthly_bedrock:>8.0f}/month       │")
    print(f"│  OpenSearch (business hours):       ${monthly_opensearch:>8.0f}/month       │")
    print(f"│  SQS + misc:                        ${monthly_sqs:>8.0f}/month       │")
    print(f"│                                                              │")
    print(f"│  📊 Total (this solution):          ${monthly_total:>8.0f}/month       │")
    print(f"│  📊 Current (S3 copy only):         ${current_s3_cost:>8.0f}/month       │")
    print(f"│  📊 Net savings (storage):          ${current_s3_cost - monthly_s3tables:>8.0f}/month       │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()

    # =========================================================================
    # Section 3: ROI (including labor savings)
    # =========================================================================
    annual_labor_before = args.analysts * args.hours_searching_per_week * 52 * args.hourly_rate
    annual_labor_after = annual_labor_before * 0.1  # 90% reduction
    annual_labor_savings = annual_labor_before - annual_labor_after

    annual_infra_cost = monthly_total * 12
    annual_s3_savings = current_s3_cost * 12

    total_annual_savings = annual_labor_savings + annual_s3_savings
    total_annual_cost = annual_infra_cost
    roi_percent = ((total_annual_savings - total_annual_cost) / total_annual_cost) * 100

    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  3-Year ROI Analysis                                          │")
    print(f"│  Analysts: {args.analysts}  |  Search time: {args.hours_searching_per_week}h/week  |  Rate: ${args.hourly_rate}/hr   │")
    print("├──────────────────────────────────────────────────────────────┤")
    print(f"│  Annual labor savings (90% reduction): ${annual_labor_savings:>12,.0f}     │")
    print(f"│  Annual S3 copy elimination:           ${annual_s3_savings:>12,.0f}     │")
    print(f"│  Annual solution cost:                -${annual_infra_cost:>12,.0f}     │")
    print(f"│                                                              │")
    print(f"│  📈 Annual net benefit:                ${total_annual_savings - total_annual_cost:>12,.0f}     │")
    print(f"│  📈 3-year net benefit:                ${(total_annual_savings - total_annual_cost) * 3:>12,.0f}     │")
    print(f"│  📈 ROI:                               {roi_percent:>11,.0f}%     │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print("  ⚠️  Labor savings estimate assumes 90% reduction in data search time.")
    print("     Actual savings depend on organizational data usage patterns.")
    print("     Recommend measuring Before/After in PoC to validate.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
demo-roi-interactive.py — Interactive ROI Calculator

Prompts the customer for their specific parameters and calculates
personalized ROI. Designed for use at the end of a demo session.

Usage:
    python demo-roi-interactive.py
"""

import sys


def get_input(prompt, default, type_fn=int):
    """Get user input with default value."""
    try:
        value = input(f"  {prompt} [{default}]: ").strip()
        return type_fn(value) if value else default
    except (ValueError, EOFError):
        return default


def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  Interactive ROI Calculator — Your Organization              ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("  Enter your organization's parameters (press Enter for defaults):")
    print()

    # Gather inputs
    total_files = get_input("Total unstructured files", 100000)
    data_tb = get_input("Total data volume (TB)", 10, float)
    daily_changes = get_input("Daily file changes (new + modified)", 500)
    analysts = get_input("Number of data analysts/scientists", 10)
    search_hours = get_input("Hours/week analysts spend searching for data", 5, float)
    hourly_rate = get_input("Average analyst hourly rate (USD)", 75, float)
    s3_copy_exists = get_input("Currently copying to S3? (1=yes, 0=no)", 1)

    print()
    print("  Calculating...")
    print()

    # Current costs
    current_s3_monthly = data_tb * 23 * s3_copy_exists  # $23/TB S3 Standard
    current_labor_annual = analysts * search_hours * 52 * hourly_rate

    # Solution costs
    solution_s3tables = 5 + (total_files / 100000) * 5  # Scale with file count
    solution_lambda = daily_changes * 30 * 0.0003  # Sync + enrichment
    solution_bedrock = daily_changes * 30 * 0.1 * 0.01  # 10% need AI
    solution_opensearch = 0.24 * 8 * 22  # Business hours only
    solution_monthly = solution_s3tables + solution_lambda + solution_bedrock + solution_opensearch

    # Savings
    s3_annual_savings = current_s3_monthly * 12
    labor_reduction = 0.9  # 90% reduction in search time
    labor_annual_savings = current_labor_annual * labor_reduction
    solution_annual_cost = solution_monthly * 12

    net_annual_benefit = s3_annual_savings + labor_annual_savings - solution_annual_cost
    three_year_benefit = net_annual_benefit * 3
    payback_months = solution_annual_cost / (net_annual_benefit / 12) if net_annual_benefit > 0 else 999

    # Display results
    print("  ╔══════════════════════════════════════════════════════════╗")
    print("  ║  YOUR ORGANIZATION'S ROI                                 ║")
    print("  ╠══════════════════════════════════════════════════════════╣")
    print(f"  ║  Files: {total_files:>10,}  |  Data: {data_tb:.0f} TB  |  Analysts: {analysts}       ║")
    print("  ╠══════════════════════════════════════════════════════════╣")
    print("  ║                                                          ║")
    print(f"  ║  Current S3 copy cost:        ${current_s3_monthly:>8,.0f}/month          ║")
    print(f"  ║  Current labor (data search):  ${current_labor_annual:>8,.0f}/year           ║")
    print("  ║                                                          ║")
    print(f"  ║  Solution cost:                ${solution_monthly:>8,.0f}/month          ║")
    print("  ║                                                          ║")
    print("  ╠══════════════════════════════════════════════════════════╣")
    print(f"  ║  Annual S3 savings:            ${s3_annual_savings:>10,.0f}              ║")
    print(f"  ║  Annual labor savings (90%):   ${labor_annual_savings:>10,.0f}              ║")
    print(f"  ║  Annual solution cost:         -${solution_annual_cost:>9,.0f}              ║")
    print("  ║                                                          ║")
    print(f"  ║  📈 Annual net benefit:         ${net_annual_benefit:>10,.0f}              ║")
    print(f"  ║  📈 3-year net benefit:         ${three_year_benefit:>10,.0f}              ║")
    print(f"  ║  📈 Payback period:             {payback_months:>7.1f} months            ║")
    print("  ║                                                          ║")
    print("  ╚══════════════════════════════════════════════════════════╝")
    print()
    print("  ⚠️  Labor savings assumes 90% reduction in data search time.")
    print("     Validate with Before/After measurement in PoC.")
    print()
    print("  Next steps:")
    print("    1. Run PoC with your actual data (1 day)")
    print("    2. Measure Before/After search time")
    print("    3. Calculate actual ROI with measured values")
    print("    4. Present business case to stakeholders")


if __name__ == "__main__":
    main()

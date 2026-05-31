#!/usr/bin/env python3
"""
demo-fabricpool.py — FabricPool Automatic Tiering Visualization (ST-3)

Demonstrates how FabricPool automatically tiers cold data to cheaper storage
while keeping hot metadata fast. Shows cost savings and latency impact.

Key Message:
    "Cold data automatically moves to cheaper storage, hot metadata stays fast"

Architecture:
    FSx ONTAP Performance Tier (SSD)  ←→  Capacity Tier (S3)
         ↑ Hot data (recent files)          ↑ Cold data (old files)
         ↑ Metadata always here             ↑ Auto-tiered by policy

Usage:
    python demo-fabricpool.py
    python demo-fabricpool.py --total-data 50TB --cold-ratio 0.8
    python demo-fabricpool.py --policy auto --cooling-days 30
"""

import argparse
import sys


def print_header():
    """Print demo header."""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  ST-3: FabricPool — Automatic Storage Tiering                ║")
    print("║  Hot data on SSD, cold data on S3 — transparent to apps      ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def demo_tiering_concept(total_tb: float, cold_ratio: float, policy: str, cooling_days: int):
    """Show hot/cold data distribution concept."""
    hot_tb = total_tb * (1 - cold_ratio)
    cold_tb = total_tb * cold_ratio

    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 1: Data Temperature Distribution                       │")
    print("│  Most unstructured data is cold — accessed rarely             │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print(f"  Total unstructured data: {total_tb:.0f} TB")
    print(f"  Tiering policy: {policy} (cooling period: {cooling_days} days)")
    print()

    # Visual bar chart
    hot_pct = (1 - cold_ratio) * 100
    cold_pct = cold_ratio * 100
    hot_bars = int(hot_pct / 2)
    cold_bars = int(cold_pct / 2)

    print("  Data temperature distribution:")
    print()
    print(f"    HOT  (< {cooling_days} days) │{'█' * hot_bars}{' ' * (50 - hot_bars)}│ {hot_pct:.0f}% ({hot_tb:.1f} TB)")
    print(f"    COLD (> {cooling_days} days) │{'░' * cold_bars}{' ' * (50 - cold_bars)}│ {cold_pct:.0f}% ({cold_tb:.1f} TB)")
    print()
    print("  Typical unstructured data pattern:")
    print("    • Design files: accessed during project, cold after release")
    print("    • Financial docs: hot during quarter-end, cold after audit")
    print("    • Medical images: hot during diagnosis, cold after 30 days")
    print("    • Video assets: hot during editing, cold after publication")
    print()

    # Storage tier diagram
    print("  ┌─────────────────────────────────────────────────────────┐")
    print("  │  FSx ONTAP Storage Architecture with FabricPool         │")
    print("  ├─────────────────────────────────────────────────────────┤")
    print("  │                                                         │")
    print(f"  │  ┌─────────────────────┐  Performance Tier (SSD)       │")
    print(f"  │  │  HOT: {hot_tb:>5.1f} TB       │  • Sub-ms latency             │")
    print(f"  │  │  + ALL metadata      │  • {hot_pct:.0f}% of data                │")
    print(f"  │  │  + Iceberg catalog   │  • Always fast for queries    │")
    print(f"  │  └─────────┬───────────┘                               │")
    print(f"  │            │ Auto-tier                                  │")
    print(f"  │            ▼ (transparent)                              │")
    print(f"  │  ┌─────────────────────┐  Capacity Tier (S3)           │")
    print(f"  │  │  COLD: {cold_tb:>5.1f} TB      │  • ~10ms first-byte latency   │")
    print(f"  │  │  (data blocks only)  │  • {cold_pct:.0f}% of data                │")
    print(f"  │  │                      │  • 70-80% cheaper per GB      │")
    print(f"  │  └─────────────────────┘                               │")
    print("  │                                                         │")
    print("  └─────────────────────────────────────────────────────────┘")
    print()


def demo_cost_savings(total_tb: float, cold_ratio: float):
    """Show cost savings from tiering."""
    hot_tb = total_tb * (1 - cold_ratio)
    cold_tb = total_tb * cold_ratio

    # Pricing (approximate, per TB/month)
    ssd_cost_per_tb = 230.0   # FSx ONTAP SSD tier
    s3_cost_per_tb = 23.0     # S3 Standard (capacity tier)

    # Without FabricPool: all on SSD
    cost_no_tiering = total_tb * ssd_cost_per_tb

    # With FabricPool: hot on SSD, cold on S3
    cost_with_tiering = (hot_tb * ssd_cost_per_tb) + (cold_tb * s3_cost_per_tb)

    savings_monthly = cost_no_tiering - cost_with_tiering
    savings_pct = (savings_monthly / cost_no_tiering) * 100
    savings_annual = savings_monthly * 12

    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 2: Cost Savings Analysis                               │")
    print("│  FabricPool reduces storage cost by tiering cold data         │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print("  Pricing assumptions (per TB/month):")
    print(f"    Performance Tier (SSD): ${ssd_cost_per_tb:.0f}/TB/month")
    print(f"    Capacity Tier (S3):     ${s3_cost_per_tb:.0f}/TB/month")
    print()
    print("  ┌────────────────────────────────────────────────────────┐")
    print("  │  Cost Comparison                                       │")
    print("  ├────────────────────────────────────────────────────────┤")
    print(f"  │  Without FabricPool:                                   │")
    print(f"  │    {total_tb:.0f} TB × ${ssd_cost_per_tb:.0f}/TB = ${cost_no_tiering:>10,.0f}/month         │")
    print(f"  │                                                        │")
    print(f"  │  With FabricPool:                                      │")
    print(f"  │    Hot:  {hot_tb:.1f} TB × ${ssd_cost_per_tb:.0f}/TB = ${hot_tb * ssd_cost_per_tb:>8,.0f}/month     │")
    print(f"  │    Cold: {cold_tb:.1f} TB × ${s3_cost_per_tb:.0f}/TB  = ${cold_tb * s3_cost_per_tb:>8,.0f}/month     │")
    print(f"  │    Total:              = ${cost_with_tiering:>10,.0f}/month         │")
    print(f"  │                                                        │")
    print(f"  │  💰 Monthly savings: ${savings_monthly:>10,.0f} ({savings_pct:.0f}%)          │")
    print(f"  │  💰 Annual savings:  ${savings_annual:>10,.0f}                   │")
    print("  └────────────────────────────────────────────────────────┘")
    print()


def demo_metadata_latency_impact():
    """Show impact on AI processing latency for cold data."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  Step 3: Impact on AI Processing & Metadata Queries           │")
    print("│  Metadata stays fast; cold file access adds minimal latency   │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()
    print("  Latency comparison by operation:")
    print()
    print("    Operation                    Hot Data    Cold Data    Impact")
    print("    ─────────────────────────    ────────    ─────────    ──────────────")
    print("    Metadata query (Athena)      < 2s        < 2s         None ✅")
    print("    Iceberg table scan           < 1s        < 1s         None ✅")
    print("    Vector search (OpenSearch)   < 100ms     < 100ms      None ✅")
    print("    File content read (small)    < 10ms      ~50ms        Minimal ✅")
    print("    File content read (large)    < 100ms     ~500ms       Acceptable ⚠️")
    print("    AI enrichment (Bedrock)      ~3s         ~3.5s        Negligible ✅")
    print()
    print("  Key insight:")
    print("    • Metadata operations are ALWAYS fast (metadata stays on SSD)")
    print("    • Only actual file content reads are affected by tiering")
    print("    • AI enrichment latency dominated by model inference, not I/O")
    print("    • Cold data is automatically recalled to SSD on access")
    print()
    print("  FabricPool tiering policies:")
    print()
    print("    Policy          Behavior")
    print("    ──────────────  ─────────────────────────────────────────────")
    print("    auto            Tier cold blocks; recall on read (default)")
    print("    snapshot-only   Only tier snapshot data (most conservative)")
    print("    all             Tier all user data (most aggressive savings)")
    print("    none            Disable tiering for this volume")
    print()
    print("  Recommended for metadata catalog workload: 'auto' with 30-day cooling")
    print("    → Metadata queries unaffected")
    print("    → AI re-enrichment triggers automatic recall")
    print("    → Maximum cost savings with minimal latency impact")
    print()


def demo_key_message():
    """Print key takeaway."""
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│  💡 Key Message                                               │")
    print("├──────────────────────────────────────────────────────────────┤")
    print("│                                                              │")
    print("│  \"Cold data automatically moves to cheaper storage,           │")
    print("│   hot metadata stays fast\"                                    │")
    print("│                                                              │")
    print("│  Why this matters for metadata catalog:                       │")
    print("│    1. Metadata table (Iceberg) → always on SSD → fast queries │")
    print("│    2. Actual files → auto-tiered → 70%+ cost savings          │")
    print("│    3. No application changes → transparent to all engines     │")
    print("│    4. On-demand recall → cold files warmed up automatically   │")
    print("│                                                              │")
    print("│  Result: Enterprise-scale unstructured data at object-storage │")
    print("│  pricing, with NAS performance for active workloads           │")
    print("│                                                              │")
    print("└──────────────────────────────────────────────────────────────┘")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="FabricPool Tiering Demo — Automatic hot/cold data management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python demo-fabricpool.py
    python demo-fabricpool.py --total-data 50 --cold-ratio 0.8
    python demo-fabricpool.py --total-data 100 --cold-ratio 0.9 --policy auto
    python demo-fabricpool.py --cooling-days 14  # Aggressive tiering
        """,
    )
    parser.add_argument(
        "--total-data", type=float, default=50.0,
        help="Total unstructured data in TB (default: 50)",
    )
    parser.add_argument(
        "--cold-ratio", type=float, default=0.8,
        help="Ratio of cold data (0.0-1.0, default: 0.8)",
    )
    parser.add_argument(
        "--policy", choices=["auto", "snapshot-only", "all", "none"],
        default="auto",
        help="FabricPool tiering policy (default: auto)",
    )
    parser.add_argument(
        "--cooling-days", type=int, default=30,
        help="Days before data is considered cold (default: 30)",
    )
    args = parser.parse_args()

    print_header()
    demo_tiering_concept(args.total_data, args.cold_ratio, args.policy, args.cooling_days)
    demo_cost_savings(args.total_data, args.cold_ratio)
    demo_metadata_latency_impact()
    demo_key_message()


if __name__ == "__main__":
    main()

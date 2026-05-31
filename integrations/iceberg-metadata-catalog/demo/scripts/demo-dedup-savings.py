#!/usr/bin/env python3
"""
demo-dedup-savings.py — ONTAP Deduplication Savings Visualization

Shows the storage efficiency of FSx for ONTAP compared to S3 full copy.
Key message: "ONTAP deduplication is why we keep data on FSx instead of copying to S3."

Usage:
    python demo-dedup-savings.py --region ap-northeast-1
"""

import argparse
import json

import boto3


def main():
    parser = argparse.ArgumentParser(description="Dedup Savings Demo")
    parser.add_argument("--region", default="ap-northeast-1")
    parser.add_argument("--fs-id", default="fs-09ffe72a3b2b7dbbd")
    args = parser.parse_args()

    fsx = boto3.client("fsx", region_name=args.region)

    print("╔══════════════════════════════════════════════════════════════╗")
    print("║  ONTAP Storage Efficiency: Why Data Stays on FSx             ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

    # Get FSx file system info
    try:
        response = fsx.describe_file_systems(FileSystemIds=[args.fs_id])
        fs = response["FileSystems"][0]
        storage_capacity_gb = fs["StorageCapacity"]
        throughput = fs["OntapConfiguration"]["ThroughputCapacity"]

        print(f"  File System: {args.fs_id}")
        print(f"  Storage Capacity: {storage_capacity_gb} GB")
        print(f"  Throughput: {throughput} MB/s")
        print()
    except Exception as e:
        print(f"  ⚠️  Could not query FSx: {e}")
        storage_capacity_gb = 1024
        print(f"  Using default: {storage_capacity_gb} GB")
        print()

    # Get volume info
    try:
        volumes = fsx.describe_volumes(
            Filters=[{"Name": "file-system-id", "Values": [args.fs_id]}]
        )["Volumes"]

        print("  ┌────────────────────────────────────────────────────────────┐")
        print("  │  Volume Storage Efficiency                                  │")
        print("  ├──────────────────────┬──────────┬──────────┬───────────────┤")
        print("  │  Volume              │  Used GB │  Logical │  Savings      │")
        print("  ├──────────────────────┼──────────┼──────────┼───────────────┤")

        total_used = 0
        for vol in volumes:
            name = vol.get("Name", "unknown")[:20]
            ontap_config = vol.get("OntapConfiguration", {})
            size_mb = ontap_config.get("SizeInMegabytes", 0)
            # Note: actual dedup stats require ONTAP CLI (volume efficiency show)
            # Here we show volume sizes as a proxy
            used_gb = size_mb / 1024
            total_used += used_gb
            print(f"  │  {name:<20} │  {used_gb:>6.1f}  │          │               │")

        print("  ├──────────────────────┼──────────┼──────────┼───────────────┤")
        print(f"  │  TOTAL               │  {total_used:>6.1f}  │          │               │")
        print("  └──────────────────────┴──────────┴──────────┴───────────────┘")
        print()
    except Exception as e:
        print(f"  ⚠️  Could not query volumes: {e}")
        print()

    # Dedup savings explanation
    print("  ┌────────────────────────────────────────────────────────────┐")
    print("  │  Deduplication Savings by Data Pattern                      │")
    print("  ├──────────────────────────────┬─────────────────────────────┤")
    print("  │  Pattern                      │  Expected Savings           │")
    print("  ├──────────────────────────────┼─────────────────────────────┤")
    print("  │  Same file, 5 departments     │  70-80% (block-level dedup) │")
    print("  │  Document versions (v1,v2,v3) │  30-50% (shared blocks)     │")
    print("  │  Unique images/video          │  5-15% (headers only)       │")
    print("  │  Log/sensor data              │  20-40% (repeating patterns)│")
    print("  │  Pre-compressed (ZIP, MP4)    │  0-5% (already compressed)  │")
    print("  └──────────────────────────────┴─────────────────────────────┘")
    print()
    print("  Key insight:")
    print("  • S3 has NO deduplication — every copy is full storage cost")
    print("  • ONTAP deduplication operates at 4KB block level")
    print("  • Combined with compression: 50-70% total savings typical")
    print("  • This is why the architecture keeps data on FSx (not S3)")
    print()
    print("  To see actual dedup ratio:")
    print("    ssh fsxadmin@<management-ip> 'volume efficiency show'")
    print()
    print("  ┌────────────────────────────────────────────────────────────┐")
    print("  │  Cost Comparison (10 TB data)                               │")
    print("  ├──────────────────────────────┬─────────────────────────────┤")
    print("  │  Approach                     │  Monthly Storage Cost       │")
    print("  ├──────────────────────────────┼─────────────────────────────┤")
    print("  │  S3 Standard (no dedup)       │  $230/month                 │")
    print("  │  FSx for ONTAP (50% dedup)    │  $225/month (5TB effective) │")
    print("  │  FSx + FabricPool (80% cold)  │  $135/month                 │")
    print("  │  This solution (no S3 copy)   │  $0 additional S3 cost      │")
    print("  └──────────────────────────────┴─────────────────────────────┘")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate OpenSharing credential profiles for Databricks CREATE PROVIDER.

Usage:
    # Generate profile for a specific recipient
    python3 scripts/generate-profile.py \
        --endpoint https://abc123.lambda-url.ap-northeast-1.on.aws/api/v1 \
        --recipient quality-team \
        --output ./profiles/quality-team.share

    # Generate profiles for all recipients
    python3 scripts/generate-profile.py \
        --endpoint https://abc123.lambda-url.ap-northeast-1.on.aws/api/v1 \
        --all \
        --output-dir ./profiles/

    # With custom config file
    python3 scripts/generate-profile.py \
        --config config/volumes.yaml \
        --endpoint https://abc123.lambda-url.ap-northeast-1.on.aws/api/v1 \
        --all

Then in Databricks SQL:
    -- Upload the .share file and create a provider
    CREATE PROVIDER fsxontap_provider;
    -- Follow the UI to upload the credential profile file

Or via Databricks CLI:
    databricks unity-catalog providers create --name fsxontap_provider --authentication-type TOKEN
    -- Then configure with the profile endpoint URL
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_config
from src.profile import generate_profile, save_profile, generate_all_profiles


def main():
    parser = argparse.ArgumentParser(
        description="Generate OpenSharing credential profiles for Databricks CREATE PROVIDER"
    )
    parser.add_argument(
        "--config",
        default="config/volumes.yaml",
        help="Path to the server config YAML (default: config/volumes.yaml)",
    )
    parser.add_argument(
        "--endpoint",
        required=True,
        help="Public URL of the OpenSharing server (e.g., https://abc.lambda-url.region.on.aws/api/v1)",
    )
    parser.add_argument(
        "--recipient",
        help="Recipient name to generate profile for (mutually exclusive with --all)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate profiles for all configured recipients",
    )
    parser.add_argument(
        "--output",
        help="Output file path (for single recipient, e.g., ./quality-team.share)",
    )
    parser.add_argument(
        "--output-dir",
        default="./profiles",
        help="Output directory (for --all, default: ./profiles/)",
    )
    parser.add_argument(
        "--expiration",
        help="Optional ISO 8601 expiration time (e.g., 2026-12-31T23:59:59Z)",
    )

    args = parser.parse_args()

    # Validate arguments
    if not args.recipient and not args.all:
        parser.error("Specify either --recipient <name> or --all")
    if args.recipient and args.all:
        parser.error("--recipient and --all are mutually exclusive")

    # Load config
    config = load_config(args.config)
    print(f"Loaded config: {len(config.shares)} shares, {len(config.auth.tokens)} recipients")

    if args.all:
        # Generate for all recipients
        paths = generate_all_profiles(
            config=config,
            endpoint=args.endpoint,
            output_dir=args.output_dir,
            expiration_time=args.expiration,
        )
        print(f"\nGenerated {len(paths)} profiles:")
        for p in paths:
            print(f"  {p}")
    else:
        # Generate for single recipient
        profile = generate_profile(
            config=config,
            endpoint=args.endpoint,
            recipient_name=args.recipient,
            expiration_time=args.expiration,
        )

        if args.output:
            path = save_profile(profile, args.output)
            print(f"\nProfile saved: {path}")
        else:
            # Print to stdout
            print(json.dumps(profile, indent=2))

    print("\n--- Next Steps ---")
    print("1. Upload the .share file to Databricks workspace")
    print("2. In Databricks SQL:")
    print("   CREATE PROVIDER fsxontap_provider;")
    print("   -- Use Catalog Explorer to upload the credential profile")
    print("3. Verify:")
    print("   SHOW SHARES IN PROVIDER fsxontap_provider;")
    print("4. Create catalog from share:")
    print("   CREATE CATALOG my_data USING SHARE fsxontap_provider.<share_name>;")


if __name__ == "__main__":
    main()

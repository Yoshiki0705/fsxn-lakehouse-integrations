#!/usr/bin/env python3
"""
Screenshot Masking Script
=========================
Masks personal information in screenshots before committing to public repository.

Mask targets:
- AWS Account ID in console header (top-right corner)
- Usernames, email addresses, organization names
- Trial/billing information banners

Usage:
    python3 shared/scripts/mask-screenshots.py [--dir <directory>] [--dry-run]

Dependencies:
    pip install Pillow

Configuration:
    Define mask regions per screenshot in MASK_CONFIGS below.
    Each entry maps a filename pattern to a list of mask regions.
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Error: Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


# =============================================================================
# Mask Configuration
# =============================================================================
# Define regions to mask per screenshot filename pattern.
# Format: { "filename_pattern": [ (x1, y1, x2, y2, color), ... ] }
#
# Common AWS Console regions to mask:
#   - Account dropdown (top-right): varies by resolution
#   - Trial banner (top): full width, ~40px height
#   - Sidebar user info (bottom-left): varies
#
# Colors should match the UI background:
#   - AWS Console dark header: (35, 47, 62) or #232F3E
#   - AWS Console light body: (255, 255, 255)
#   - Databricks sidebar: (41, 46, 57) or #292E39
#   - Snowflake header: (41, 50, 65)
# =============================================================================

# Default mask color (dark, matches most console headers)
DEFAULT_MASK_COLOR = (35, 47, 62)

# Databricks UI colors
DATABRICKS_SIDEBAR = (41, 46, 57)
DATABRICKS_HEADER = (255, 255, 255)

# AWS Console colors
AWS_HEADER = (35, 47, 62)
AWS_BODY = (255, 255, 255)

# Per-file mask configurations
# Add entries as you identify PII regions in specific screenshots
MASK_CONFIGS: dict[str, list[tuple[int, int, int, int, tuple[int, int, int]]]] = {
    # Example:
    # "10_catalog_explorer_apne1.png": [
    #     (1100, 0, 1400, 40, AWS_HEADER),      # Account ID in header
    #     (0, 40, 1400, 80, AWS_BODY),           # Trial banner
    # ],
}


def mask_region(
    img: Image.Image,
    box: tuple[int, int, int, int],
    color: tuple[int, int, int] = DEFAULT_MASK_COLOR,
) -> None:
    """Mask a rectangular region with a solid color fill."""
    draw = ImageDraw.Draw(img)
    draw.rectangle(box, fill=color)


def find_screenshots(directory: Path) -> list[Path]:
    """Find all PNG/JPEG screenshots in directory recursively."""
    extensions = {".png", ".jpg", ".jpeg"}
    screenshots = []
    for ext in extensions:
        screenshots.extend(directory.rglob(f"*{ext}"))
    return sorted(screenshots)


def process_screenshot(filepath: Path, dry_run: bool = False) -> bool:
    """
    Apply mask regions to a screenshot if configured.
    Returns True if masks were applied.
    """
    filename = filepath.name

    # Check if this file has mask configurations
    config = None
    for pattern, regions in MASK_CONFIGS.items():
        if pattern in filename or filename == pattern:
            config = regions
            break

    if not config:
        return False

    if dry_run:
        print(f"  [DRY RUN] Would mask {len(config)} region(s) in: {filepath}")
        return True

    img = Image.open(filepath)

    for region in config:
        if len(region) == 5:
            x1, y1, x2, y2, color = region
        else:
            x1, y1, x2, y2 = region[:4]
            color = DEFAULT_MASK_COLOR

        # Validate region is within image bounds
        width, height = img.size
        x1 = max(0, min(x1, width))
        y1 = max(0, min(y1, height))
        x2 = max(0, min(x2, width))
        y2 = max(0, min(y2, height))

        mask_region(img, (x1, y1, x2, y2), color)

    img.save(filepath)
    print(f"  ✓ Masked {len(config)} region(s) in: {filepath.name}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Mask personal information in screenshots"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Directory to scan (default: all docs/ and integrations/ screenshot dirs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be masked without modifying files",
    )
    args = parser.parse_args()

    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    # Determine directories to scan
    if args.dir:
        dirs_to_scan = [args.dir]
    else:
        dirs_to_scan = [
            project_root / "docs" / "images",
            project_root / "integrations",
        ]

    print("=" * 50)
    print(" Screenshot Masking Tool")
    print("=" * 50)
    print()

    if args.dry_run:
        print("[DRY RUN MODE - no files will be modified]")
        print()

    total_found = 0
    total_masked = 0

    for scan_dir in dirs_to_scan:
        if not scan_dir.exists():
            continue

        screenshots = find_screenshots(scan_dir)
        if not screenshots:
            continue

        print(f"📁 Scanning: {scan_dir.relative_to(project_root)}")
        total_found += len(screenshots)

        for screenshot in screenshots:
            if process_screenshot(screenshot, dry_run=args.dry_run):
                total_masked += 1

    print()
    print("-" * 50)
    print(f"Found: {total_found} screenshot(s)")
    print(f"Masked: {total_masked} screenshot(s)")

    if total_found > 0 and total_masked == 0 and MASK_CONFIGS:
        print()
        print("ℹ️  No screenshots matched configured patterns.")
        print("   Add entries to MASK_CONFIGS in this script for new screenshots.")
    elif not MASK_CONFIGS:
        print()
        print("ℹ️  No mask configurations defined yet.")
        print("   Edit MASK_CONFIGS in this script to define regions to mask.")
        print()
        print("   Example:")
        print('   MASK_CONFIGS = {')
        print('       "my_screenshot.png": [')
        print(f"           (1100, 0, 1400, 40, {AWS_HEADER}),  # Account ID")
        print("       ],")
        print("   }")


if __name__ == "__main__":
    main()

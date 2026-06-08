#!/usr/bin/env python3
"""
Mask sensitive information in Snowflake screenshots.
- Screenshots 01-03: No URL bar visible, no sensitive info -> copy as-is
- Screenshot 04 (SELECT *): FILE_PATH column shows S3 Tables internal bucket name -> mask it
"""

from PIL import Image, ImageDraw, ImageFont
import os
import sys

RAW_DIR = os.path.join(os.path.dirname(__file__), "raw")
OUTPUT_DIR = os.path.dirname(__file__)


def mask_file_path_column(img: Image.Image) -> Image.Image:
    """
    Mask the FILE_PATH column in the SELECT * results.
    The S3 Tables internal bucket name is account-specific.
    
    From the screenshot (approx 2048x1148 at 2x):
    - Results table starts around y=730 (at 2x)
    - FILE_PATH column is approximately x=310 to x=680
    - Data rows are from approximately y=780 to y=1100
    """
    draw = ImageDraw.Draw(img)
    width, height = img.size
    
    # FILE_PATH column data area (the actual s3:// paths)
    # Based on the screenshot layout - FILE_PATH is the 2nd data column
    # Approximate coordinates from the chat image (appears ~1024x wide viewport)
    # At 2x: FILE_PATH column data ~ x=290-680, rows ~ y=760-1100
    
    # We'll mask the s3:// bucket name portion in each row
    # The column header "FILE_PATH" can stay, just mask the data values
    fp_x_start = 288
    fp_x_end = 680
    fp_y_start = 778  # First data row
    fp_y_end = height - 20  # All data rows to bottom
    
    draw.rectangle(
        [fp_x_start, fp_y_start, fp_x_end, fp_y_end],
        fill=(240, 240, 240)  # Light gray to indicate masked
    )
    
    # Add text indicating masking
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except (OSError, IOError):
        font = ImageFont.load_default()
    
    draw.text(
        (fp_x_start + 10, fp_y_start + 20),
        "s3://<s3-tables-internal-bucket>/...",
        fill=(128, 128, 128),
        font=font
    )
    draw.text(
        (fp_x_start + 10, fp_y_start + 50),
        "(masked: account-specific bucket)",
        fill=(128, 128, 128),
        font=font
    )
    
    return img


def process_screenshots():
    """Process all raw screenshots and save output versions."""
    if not os.path.exists(RAW_DIR):
        print(f"Error: Raw directory not found: {RAW_DIR}")
        sys.exit(1)
    
    raw_files = sorted([f for f in os.listdir(RAW_DIR) if f.endswith(".png")])
    
    if not raw_files:
        print("No PNG files found in raw directory")
        sys.exit(1)
    
    print(f"Processing {len(raw_files)} screenshots...")
    
    for filename in raw_files:
        input_path = os.path.join(RAW_DIR, filename)
        output_filename = filename.replace(".png", "-v2.png")
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        img = Image.open(input_path)
        
        if "04-select-star" in filename:
            # Mask the FILE_PATH column with internal bucket names
            print(f"  {filename} -> {output_filename} (masking FILE_PATH)")
            img = mask_file_path_column(img)
        else:
            # No masking needed - just copy
            print(f"  {filename} -> {output_filename} (no masking needed)")
        
        img.save(output_path, "PNG", optimize=True)
    
    print(f"\nDone! Output screenshots saved to: {OUTPUT_DIR}")
    print("\nPlease verify visually before publishing.")


if __name__ == "__main__":
    process_screenshots()

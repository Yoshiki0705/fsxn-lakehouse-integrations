"""
Snowpark UDF Reference Implementation — Media File Processing
==============================================================

Standalone Python implementations of the Snowpark UDFs defined in
09_snowpark_image_udf.sql. This module serves two purposes:

1. Local testing and validation of UDF logic without a Snowflake connection
2. Documentation of classification rules and expected behavior

The functions here are identical to the inline Python in the SQL script.
They use ONLY Python standard library modules (os, re) — no external packages.

Requirements: REQ-7 (Snowpark UDF processing for media files)
"""

import os
import re


# =============================================================================
# UDF 1: parse_image_filename
# =============================================================================

def parse_image_filename(file_path: str) -> dict:
    """
    Parse a file path and extract structured metadata.

    This function mirrors the inline Python in the PARSE_IMAGE_FILENAME UDF
    (09_snowpark_image_udf.sql). It uses os.path for cross-platform path
    parsing and normalizes the extension to lowercase.

    Args:
        file_path: Relative or absolute path to the file.
                   Example: 'images/2024/photo_001.jpg'

    Returns:
        dict with keys:
            - filename:  Full filename with extension (e.g., 'photo_001.jpg')
            - extension: File extension including dot, lowercase (e.g., '.jpg')
            - directory: Parent directory path (e.g., 'images/2024')
            - base_name: Filename without extension (e.g., 'photo_001')

    Examples:
        >>> parse_image_filename('media/photos/sunset.png')
        {'filename': 'sunset.png', 'extension': '.png', 'directory': 'media/photos', 'base_name': 'sunset'}

        >>> parse_image_filename('')
        {'filename': None, 'extension': None, 'directory': None, 'base_name': None}
    """
    if not file_path:
        return {
            'filename': None,
            'extension': None,
            'directory': None,
            'base_name': None
        }

    # Extract components using os.path
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    base_name, extension = os.path.splitext(filename)

    # Normalize extension to lowercase
    extension = extension.lower()

    # If directory is empty (file at root), use empty string
    if not directory:
        directory = ''

    return {
        'filename': filename,
        'extension': extension,
        'directory': directory,
        'base_name': base_name
    }


# =============================================================================
# UDF 2: classify_media_file
# =============================================================================

# Extension sets for file type classification
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}
DOCUMENT_EXTS = {'.pdf', '.docx', '.doc', '.xlsx', '.pptx', '.txt', '.md', '.csv'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv'}
AUDIO_EXTS = {'.wav', '.mp3', '.flac', '.ogg', '.aac', '.wma'}


def classify_media_file(file_path: str, file_size: int) -> dict:
    """
    Classify a media file based on its extension and size.

    This function mirrors the inline Python in the CLASSIFY_MEDIA_FILE UDF
    (09_snowpark_image_udf.sql). It categorizes files by type and size, and
    determines whether they are suitable for inline Snowpark UDF processing.

    Classification Rules:
        Type (by extension):
            - image:    .jpg, .jpeg, .png, .tiff, .tif, .bmp, .gif, .webp
            - document: .pdf, .docx, .doc, .xlsx, .pptx, .txt, .md, .csv
            - video:    .mp4, .mov, .avi, .mkv, .wmv, .flv
            - audio:    .wav, .mp3, .flac, .ogg, .aac, .wma
            - other:    anything else

        Size category:
            - small:  < 1 MB
            - medium: 1 MB – 100 MB
            - large:  > 100 MB

        Processable (inline Snowpark UDF feasibility):
            - Images < 50 MB → processable
            - Documents < 10 MB → processable
            - Audio < 20 MB → processable
            - Video, large files, 'other' → NOT processable
              (use External Functions / AWS Lambda instead)

    Args:
        file_path: Relative or absolute path to the file.
        file_size: File size in bytes.

    Returns:
        dict with keys:
            - estimated_type:  'image', 'document', 'video', 'audio', or 'other'
            - size_category:   'small', 'medium', or 'large'
            - is_processable:  True if inline UDF processing is feasible

    Examples:
        >>> classify_media_file('photos/sunset.jpg', 2_500_000)
        {'estimated_type': 'image', 'size_category': 'medium', 'is_processable': True}

        >>> classify_media_file('videos/demo.mp4', 500_000_000)
        {'estimated_type': 'video', 'size_category': 'large', 'is_processable': False}
    """
    # Extract extension
    ext = os.path.splitext(file_path)[1].lower() if file_path else ''

    # File type classification by extension
    if ext in IMAGE_EXTS:
        estimated_type = 'image'
    elif ext in DOCUMENT_EXTS:
        estimated_type = 'document'
    elif ext in VIDEO_EXTS:
        estimated_type = 'video'
    elif ext in AUDIO_EXTS:
        estimated_type = 'audio'
    else:
        estimated_type = 'other'

    # Size category classification
    size_mb = (file_size or 0) / (1024 * 1024)
    if size_mb < 1:
        size_category = 'small'
    elif size_mb <= 100:
        size_category = 'medium'
    else:
        size_category = 'large'

    # Determine if file is processable by inline Snowpark UDFs
    # Images under 50 MB and documents under 10 MB are processable
    if estimated_type == 'image' and size_mb < 50:
        is_processable = True
    elif estimated_type == 'document' and size_mb < 10:
        is_processable = True
    elif estimated_type == 'audio' and size_mb < 20:
        is_processable = True
    else:
        # Video, large files, and 'other' types require external functions
        is_processable = False

    return {
        'estimated_type': estimated_type,
        'size_category': size_category,
        'is_processable': is_processable
    }


# =============================================================================
# Main — Demonstration with sample file paths
# =============================================================================

if __name__ == '__main__':
    import json

    print("=" * 70)
    print("Snowpark UDF Reference Implementation — Media File Processing")
    print("=" * 70)

    # Sample file paths simulating FSxN media/ directory structure
    sample_files = [
        ('media/images/product_photo_001.jpg', 3_200_000),       # 3.2 MB JPEG
        ('media/images/banner_hero.png', 850_000),               # 850 KB PNG
        ('media/images/scan_highres.tiff', 75_000_000),          # 75 MB TIFF
        ('media/documents/annual_report_2024.pdf', 4_500_000),   # 4.5 MB PDF
        ('media/documents/meeting_notes.docx', 120_000),         # 120 KB DOCX
        ('media/documents/data_export.csv', 15_000_000),         # 15 MB CSV
        ('media/video/product_demo.mp4', 250_000_000),           # 250 MB MP4
        ('media/video/clip_short.mov', 45_000_000),              # 45 MB MOV
        ('media/audio/podcast_episode.mp3', 18_000_000),         # 18 MB MP3
        ('media/audio/notification.wav', 500_000),               # 500 KB WAV
        ('media/other/archive.zip', 100_000_000),                # 100 MB ZIP
        ('', 0),                                                  # Empty path
    ]

    # --- PARSE_IMAGE_FILENAME demonstration ---
    print("\n" + "-" * 70)
    print("UDF 1: PARSE_IMAGE_FILENAME")
    print("-" * 70)
    for file_path, _ in sample_files:
        result = parse_image_filename(file_path)
        print(f"\n  Input:  '{file_path}'")
        print(f"  Output: {json.dumps(result, indent=None)}")

    # --- CLASSIFY_MEDIA_FILE demonstration ---
    print("\n" + "-" * 70)
    print("UDF 2: CLASSIFY_MEDIA_FILE")
    print("-" * 70)
    for file_path, file_size in sample_files:
        result = classify_media_file(file_path, file_size)
        size_display = f"{file_size / (1024*1024):.1f} MB" if file_size else "0 B"
        print(f"\n  Input:  '{file_path}' ({size_display})")
        print(f"  Output: {json.dumps(result, indent=None)}")

    # --- Summary table ---
    print("\n" + "-" * 70)
    print("Summary: Classification Results")
    print("-" * 70)
    print(f"  {'File Path':<45} {'Type':<10} {'Size':<8} {'Processable'}")
    print(f"  {'-'*45} {'-'*10} {'-'*8} {'-'*11}")
    for file_path, file_size in sample_files:
        if not file_path:
            continue
        cls = classify_media_file(file_path, file_size)
        print(
            f"  {file_path:<45} "
            f"{cls['estimated_type']:<10} "
            f"{cls['size_category']:<8} "
            f"{cls['is_processable']}"
        )

    print("\n" + "=" * 70)
    print("Done. This output matches the expected behavior of the inline")
    print("Python UDFs in 09_snowpark_image_udf.sql.")
    print("=" * 70)

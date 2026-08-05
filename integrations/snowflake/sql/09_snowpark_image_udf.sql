-- =============================================================================
-- 09 - Snowpark Python UDF for Media File Processing
-- =============================================================================
-- Creates Snowpark Python UDFs to parse and classify unstructured media files
-- stored on FSx for ONTAP via S3 Access Point, then builds an enriched catalog table.
--
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ Snowpark Python UDF Runtime Notes                                       │
-- ├─────────────────────────────────────────────────────────────────────────┤
-- │ 1. Python UDFs execute in Snowflake's secure Python sandbox.            │
-- │    Each UDF invocation runs in an isolated container with limited        │
-- │    resources. Cold start may add 1-3 seconds on first call.             │
-- │                                                                         │
-- │ 2. Available Python packages come from the Snowflake Anaconda channel.  │
-- │    Pre-installed packages include: os, re, json, datetime, math, etc.   │
-- │    Additional packages (e.g., Pillow, pandas) can be imported via:      │
-- │      PACKAGES = ('pillow', 'pandas')                                    │
-- │    See: https://repo.anaconda.com/pkgs/snowflake/                       │
-- │                                                                         │
-- │ 3. For this script, we use ONLY built-in Python modules (os, re) to     │
-- │    avoid Anaconda package dependencies and minimize cold start time.     │
-- │                                                                         │
-- │ 4. RUNTIME_VERSION = '3.11' is recommended for latest Python features.  │
-- │    Supported versions: 3.8, 3.9, 3.10, 3.11 (check account settings).  │
-- │                                                                         │
-- │ 5. For heavy binary processing (OCR, ML inference, image resize),       │
-- │    consider External Functions (AWS Lambda) instead of inline UDFs.     │
-- │    Inline UDFs are best for lightweight metadata extraction.             │
-- │                                                                         │
-- │ 6. UDF return type VARIANT allows flexible JSON-like structured output. │
-- │    Access fields with colon notation: column:field_name::TYPE            │
-- └─────────────────────────────────────────────────────────────────────────┘
--
-- Requirements: REQ-7 (Snowpark UDF processing for media files)
-- =============================================================================

-- =============================================================================
-- 1. Context Setup
-- =============================================================================
USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA MEDIA;

-- =============================================================================
-- 2. Snowpark UDF: PARSE_IMAGE_FILENAME
-- =============================================================================
-- Parses a file path to extract filename components using Python os.path and re.
-- Returns VARIANT with: filename, extension, directory, base_name
--
-- Snowpark Runtime: Python 3.11 (built-in modules only — no Anaconda packages)
-- Anaconda Channel: Not required (uses only os, re from Python stdlib)
-- =============================================================================
CREATE OR REPLACE FUNCTION PARSE_IMAGE_FILENAME(file_path STRING)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ()
HANDLER = 'parse_image_filename'
COMMENT = 'Parses file path to extract filename, extension, directory, and base_name. Uses Python os.path and re modules (no external packages).'
AS
$$
import os
import re

def parse_image_filename(file_path: str) -> dict:
    """
    Parse a file path and extract structured metadata.

    Returns:
        dict with keys:
            - filename: full filename with extension (e.g., 'photo_001.jpg')
            - extension: file extension including dot, lowercase (e.g., '.jpg')
            - directory: parent directory path (e.g., 'images/2024')
            - base_name: filename without extension (e.g., 'photo_001')
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
$$;

-- Test PARSE_IMAGE_FILENAME UDF
SELECT
    RELATIVE_PATH,
    PARSE_IMAGE_FILENAME(RELATIVE_PATH) AS parsed_info
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
LIMIT 10;

-- =============================================================================
-- 3. Snowpark UDF: CLASSIFY_MEDIA_FILE
-- =============================================================================
-- Classifies a file by its extension and size into media categories.
-- Returns VARIANT with: estimated_type, size_category, is_processable
--
-- Classification rules:
--   image:    .jpg, .jpeg, .png, .tiff, .tif, .bmp, .gif, .webp
--   document: .pdf, .docx, .doc, .xlsx, .pptx, .txt, .md, .csv
--   video:    .mp4, .mov, .avi, .mkv, .wmv, .flv
--   audio:    .wav, .mp3, .flac, .ogg, .aac, .wma
--   other:    anything else
--
-- Size categories:
--   small:  < 1 MB
--   medium: 1 MB - 100 MB
--   large:  > 100 MB
--
-- Processable: files that can be processed by inline Snowpark UDFs
--   (images < 50 MB, documents < 10 MB are considered processable)
--
-- Snowpark Runtime: Python 3.11 (built-in modules only — no Anaconda packages)
-- Anaconda Channel: Not required (uses only os from Python stdlib)
-- =============================================================================
CREATE OR REPLACE FUNCTION CLASSIFY_MEDIA_FILE(file_path STRING, file_size NUMBER)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ()
HANDLER = 'classify_media_file'
COMMENT = 'Classifies media file by extension (image/document/video/audio/other) and size (small/medium/large). Returns estimated_type, size_category, is_processable.'
AS
$$
import os

def classify_media_file(file_path: str, file_size: int) -> dict:
    """
    Classify a media file based on its extension and size.

    Args:
        file_path: relative or absolute path to the file
        file_size: file size in bytes

    Returns:
        dict with keys:
            - estimated_type: 'image', 'document', 'video', 'audio', or 'other'
            - size_category: 'small' (<1MB), 'medium' (1-100MB), or 'large' (>100MB)
            - is_processable: whether the file can be processed by inline Snowpark UDFs
    """
    # Extract extension
    ext = os.path.splitext(file_path)[1].lower() if file_path else ''

    # File type classification by extension
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}
    DOCUMENT_EXTS = {'.pdf', '.docx', '.doc', '.xlsx', '.pptx', '.txt', '.md', '.csv'}
    VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv'}
    AUDIO_EXTS = {'.wav', '.mp3', '.flac', '.ogg', '.aac', '.wma'}

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
$$;

-- Test CLASSIFY_MEDIA_FILE UDF
SELECT
    RELATIVE_PATH,
    SIZE,
    CLASSIFY_MEDIA_FILE(RELATIVE_PATH, SIZE) AS classified_info
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
ORDER BY SIZE DESC
LIMIT 10;

-- =============================================================================
-- 4. Create ENRICHED_MEDIA_CATALOG Table
-- =============================================================================
-- Stores enriched metadata for all media files on FSx for ONTAP, combining Directory
-- Table metadata with UDF-extracted information.
--
-- Columns:
--   file_path       - Full relative path from stage root
--   file_name       - Extracted filename (from PARSE_IMAGE_FILENAME)
--   extension       - File extension, lowercase (from PARSE_IMAGE_FILENAME)
--   media_type      - Classified type: image/document/video/audio/other
--   size_bytes      - File size in bytes
--   size_category   - small/medium/large (from CLASSIFY_MEDIA_FILE)
--   is_processable  - Whether inline UDF processing is feasible
--   parsed_info     - Full VARIANT output from PARSE_IMAGE_FILENAME
--   classified_info - Full VARIANT output from CLASSIFY_MEDIA_FILE
--   last_modified   - File last modified timestamp (from Directory Table)
--   enriched_at     - Timestamp when this record was created
-- =============================================================================
CREATE OR REPLACE TABLE ENRICHED_MEDIA_CATALOG (
    file_path        STRING        NOT NULL,
    file_name        STRING,
    extension        STRING,
    media_type       STRING,
    size_bytes       NUMBER,
    size_category    STRING,
    is_processable   BOOLEAN,
    parsed_info      VARIANT,
    classified_info  VARIANT,
    last_modified    TIMESTAMP_NTZ,
    enriched_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'Enriched media catalog built by applying Snowpark UDFs (PARSE_IMAGE_FILENAME, CLASSIFY_MEDIA_FILE) to Directory Table metadata from FSx for ONTAP.';

-- =============================================================================
-- 5. Populate ENRICHED_MEDIA_CATALOG from Directory Table + UDFs
-- =============================================================================
-- Apply both UDFs to every file in the Directory Table and insert results.
-- This demonstrates Snowpark UDF processing at scale across all media files.
INSERT INTO ENRICHED_MEDIA_CATALOG (
    file_path,
    file_name,
    extension,
    media_type,
    size_bytes,
    size_category,
    is_processable,
    parsed_info,
    classified_info,
    last_modified,
    enriched_at
)
SELECT
    RELATIVE_PATH                                                AS file_path,
    PARSE_IMAGE_FILENAME(RELATIVE_PATH):filename::STRING         AS file_name,
    PARSE_IMAGE_FILENAME(RELATIVE_PATH):extension::STRING        AS extension,
    CLASSIFY_MEDIA_FILE(RELATIVE_PATH, SIZE):estimated_type::STRING AS media_type,
    SIZE                                                         AS size_bytes,
    CLASSIFY_MEDIA_FILE(RELATIVE_PATH, SIZE):size_category::STRING  AS size_category,
    CLASSIFY_MEDIA_FILE(RELATIVE_PATH, SIZE):is_processable::BOOLEAN AS is_processable,
    PARSE_IMAGE_FILENAME(RELATIVE_PATH)                          AS parsed_info,
    CLASSIFY_MEDIA_FILE(RELATIVE_PATH, SIZE)                     AS classified_info,
    LAST_MODIFIED                                                 AS last_modified,
    CURRENT_TIMESTAMP()                                          AS enriched_at
FROM DIRECTORY(@FSXN_MEDIA_STAGE);

-- =============================================================================
-- 6. Verification Queries
-- =============================================================================

-- 6a. View all enriched catalog entries
SELECT * FROM ENRICHED_MEDIA_CATALOG
ORDER BY last_modified DESC;

-- 6b. Count by media_type — verify classification distribution
SELECT
    media_type,
    COUNT(*)                                    AS file_count,
    SUM(size_bytes)                             AS total_bytes,
    ROUND(SUM(size_bytes) / 1024.0 / 1024.0, 2) AS total_size_mb,
    SUM(CASE WHEN is_processable THEN 1 ELSE 0 END) AS processable_count,
    ROUND(AVG(size_bytes) / 1024.0, 2)          AS avg_size_kb
FROM ENRICHED_MEDIA_CATALOG
GROUP BY media_type
ORDER BY file_count DESC;

-- 6c. Size category distribution
SELECT
    size_category,
    COUNT(*) AS file_count,
    ROUND(SUM(size_bytes) / 1024.0 / 1024.0, 2) AS total_size_mb
FROM ENRICHED_MEDIA_CATALOG
GROUP BY size_category
ORDER BY
    CASE size_category
        WHEN 'small' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'large' THEN 3
    END;

-- 6d. Processable vs non-processable files
SELECT
    is_processable,
    media_type,
    COUNT(*) AS file_count
FROM ENRICHED_MEDIA_CATALOG
GROUP BY is_processable, media_type
ORDER BY is_processable DESC, file_count DESC;

-- 6e. Sample parsed_info and classified_info VARIANT data
SELECT
    file_path,
    parsed_info:filename::STRING     AS parsed_filename,
    parsed_info:extension::STRING    AS parsed_extension,
    parsed_info:directory::STRING    AS parsed_directory,
    parsed_info:base_name::STRING    AS parsed_base_name,
    classified_info:estimated_type::STRING   AS classified_type,
    classified_info:size_category::STRING    AS classified_size,
    classified_info:is_processable::BOOLEAN  AS classified_processable
FROM ENRICHED_MEDIA_CATALOG
LIMIT 10;

-- =============================================================================
-- End of Script
-- =============================================================================
-- Summary:
--   - PARSE_IMAGE_FILENAME: Extracts filename, extension, directory, base_name
--   - CLASSIFY_MEDIA_FILE: Classifies by type (image/document/video/audio/other),
--     size (small/medium/large), and processability
--   - ENRICHED_MEDIA_CATALOG: Persisted table combining Directory Table metadata
--     with UDF-enriched fields for downstream analytics
--
-- Next Steps:
--   - Use ENRICHED_MEDIA_CATALOG for reporting and dashboards
--   - Filter is_processable = TRUE for files suitable for further UDF processing
--   - For large/video files, use External Functions (AWS Lambda) instead
--   - Schedule periodic refresh: ALTER STAGE REFRESH + re-INSERT for new files
-- =============================================================================

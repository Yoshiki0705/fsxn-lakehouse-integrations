-- =============================================================================
-- 09 - Snowpark Python UDF for Image/Document Processing
-- =============================================================================
-- Creates Snowpark Python UDFs to extract metadata from unstructured files
-- stored on FSxN via S3 Access Point.
--
-- Note: Snowpark UDFs run in Snowflake's Python sandbox.
-- For heavy processing, consider external functions (Lambda) instead.
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA MEDIA;

-- =============================================================================
-- Snowpark UDF: Extract Image Dimensions from Filename Pattern
-- (Lightweight — no binary processing needed)
-- =============================================================================
CREATE OR REPLACE FUNCTION PARSE_IMAGE_FILENAME(file_path STRING)
RETURNS OBJECT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'parse_filename'
AS
$$
import re
import os

def parse_filename(file_path: str) -> dict:
    """Parse image filename for metadata hints."""
    basename = os.path.basename(file_path)
    name, ext = os.path.splitext(basename)

    # Try to extract dimensions from filename (e.g., photo_1920x1080.jpg)
    dim_match = re.search(r'(\d{3,5})x(\d{3,5})', name)
    width = int(dim_match.group(1)) if dim_match else None
    height = int(dim_match.group(2)) if dim_match else None

    # Extract date from filename (e.g., IMG_20240101_120000.jpg)
    date_match = re.search(r'(\d{4})(\d{2})(\d{2})', name)
    date_str = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else None

    return {
        'filename': basename,
        'name_without_ext': name,
        'extension': ext.lower(),
        'width': width,
        'height': height,
        'date_from_name': date_str,
        'is_thumbnail': 'thumb' in name.lower(),
    }
$$;

-- Test the UDF
SELECT
    RELATIVE_PATH,
    PARSE_IMAGE_FILENAME(RELATIVE_PATH) AS parsed_info
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE RELATIVE_PATH LIKE '%.jpg'
LIMIT 10;

-- =============================================================================
-- Snowpark UDF: Classify File by Extension and Size
-- =============================================================================
CREATE OR REPLACE FUNCTION CLASSIFY_MEDIA_FILE(file_path STRING, file_size NUMBER)
RETURNS OBJECT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'classify_file'
AS
$$
import os

def classify_file(file_path: str, file_size: int) -> dict:
    """Classify media file by extension and size."""
    ext = os.path.splitext(file_path)[1].lower()

    # File type classification
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}
    VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.ts'}
    AUDIO_EXTS = {'.wav', '.mp3', '.flac', '.ogg', '.aac', '.wma'}
    DOC_EXTS = {'.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.md', '.csv'}

    if ext in IMAGE_EXTS:
        media_type = 'image'
    elif ext in VIDEO_EXTS:
        media_type = 'video'
    elif ext in AUDIO_EXTS:
        media_type = 'audio'
    elif ext in DOC_EXTS:
        media_type = 'document'
    else:
        media_type = 'other'

    # Size classification
    size_mb = file_size / 1024 / 1024
    if size_mb < 1:
        size_class = 'small'
    elif size_mb < 100:
        size_class = 'medium'
    elif size_mb < 1000:
        size_class = 'large'
    else:
        size_class = 'very_large'

    # Processing recommendation
    if media_type == 'image' and size_mb < 50:
        processing = 'inline_udf'
    elif media_type == 'document' and size_mb < 10:
        processing = 'inline_udf'
    else:
        processing = 'external_function'

    return {
        'media_type': media_type,
        'extension': ext,
        'size_mb': round(size_mb, 2),
        'size_class': size_class,
        'recommended_processing': processing,
    }
$$;

-- Apply classification to all files
SELECT
    RELATIVE_PATH,
    SIZE,
    CLASSIFY_MEDIA_FILE(RELATIVE_PATH, SIZE) AS classification
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
ORDER BY SIZE DESC
LIMIT 20;

-- =============================================================================
-- Snowpark UDF: Generate Document Summary (for small text files)
-- =============================================================================
CREATE OR REPLACE FUNCTION SUMMARIZE_TEXT_FILE(file_content STRING)
RETURNS OBJECT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'summarize'
AS
$$
def summarize(content: str) -> dict:
    """Generate basic statistics for text content."""
    if not content:
        return {'error': 'empty content'}

    lines = content.split('\n')
    words = content.split()
    sentences = [s.strip() for s in content.split('.') if s.strip()]

    return {
        'char_count': len(content),
        'word_count': len(words),
        'line_count': len(lines),
        'sentence_count': len(sentences),
        'avg_word_length': round(sum(len(w) for w in words) / max(len(words), 1), 1),
        'preview': content[:200],
    }
$$;

-- =============================================================================
-- Create Enriched Media Catalog Table
-- =============================================================================
CREATE OR REPLACE TABLE ENRICHED_MEDIA_CATALOG AS
SELECT
    RELATIVE_PATH AS file_path,
    SIZE AS file_size_bytes,
    LAST_MODIFIED,
    MD5 AS file_hash,
    PARSE_IMAGE_FILENAME(RELATIVE_PATH) AS filename_info,
    CLASSIFY_MEDIA_FILE(RELATIVE_PATH, SIZE) AS classification,
    GET_PRESIGNED_URL(@FSXN_MEDIA_STAGE, RELATIVE_PATH, 86400) AS access_url_24h,
    CURRENT_TIMESTAMP() AS cataloged_at
FROM DIRECTORY(@FSXN_MEDIA_STAGE);

-- Query enriched catalog
SELECT
    file_path,
    classification:media_type::STRING AS media_type,
    classification:size_mb::FLOAT AS size_mb,
    classification:recommended_processing::STRING AS processing_method,
    filename_info:date_from_name::STRING AS date_from_filename
FROM ENRICHED_MEDIA_CATALOG
ORDER BY LAST_MODIFIED DESC
LIMIT 20;

-- =============================================================================
-- Aggregate Statistics
-- =============================================================================
SELECT
    classification:media_type::STRING AS media_type,
    COUNT(*) AS file_count,
    ROUND(SUM(classification:size_mb::FLOAT), 2) AS total_size_mb,
    ROUND(AVG(classification:size_mb::FLOAT), 2) AS avg_size_mb,
    classification:size_class::STRING AS typical_size
FROM ENRICHED_MEDIA_CATALOG
GROUP BY media_type, typical_size
ORDER BY total_size_mb DESC;

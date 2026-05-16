-- =============================================================================
-- 08 - Directory Table for Unstructured Data on FSxN
-- =============================================================================
-- Manages metadata for unstructured files (images, video, audio, documents)
-- stored on FSx for NetApp ONTAP via S3 Access Point.
--
-- Snowflake cannot directly query binary file content, but Directory Tables
-- provide metadata (name, size, last_modified, etag) and Pre-signed URLs
-- for external application access.
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;
CREATE SCHEMA IF NOT EXISTS MEDIA COMMENT = 'Unstructured media files on FSxN';
USE SCHEMA MEDIA;

-- =============================================================================
-- Stage with Directory Table Enabled
-- =============================================================================
CREATE OR REPLACE STAGE FSXN_MEDIA_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<S3AccessPointAlias>/media/'
  DIRECTORY = (ENABLE = TRUE AUTO_REFRESH = FALSE)
  COMMENT = 'FSxN media files (images, video, audio, documents) with directory listing';

-- =============================================================================
-- Refresh Directory Table (manual — FSxN does not support S3 Event Notifications)
-- =============================================================================
ALTER STAGE FSXN_MEDIA_STAGE REFRESH;

-- =============================================================================
-- Query Directory Table — All Files
-- =============================================================================
SELECT
    RELATIVE_PATH,
    SIZE,
    LAST_MODIFIED,
    MD5,
    ETAG,
    FILE_URL
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
ORDER BY LAST_MODIFIED DESC
LIMIT 50;

-- =============================================================================
-- Query by File Type
-- =============================================================================

-- Images
SELECT
    RELATIVE_PATH AS file_name,
    SIZE / 1024 AS size_kb,
    LAST_MODIFIED
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE RELATIVE_PATH LIKE '%.jpg'
   OR RELATIVE_PATH LIKE '%.jpeg'
   OR RELATIVE_PATH LIKE '%.png'
   OR RELATIVE_PATH LIKE '%.tiff'
ORDER BY SIZE DESC;

-- Videos
SELECT
    RELATIVE_PATH AS file_name,
    SIZE / 1024 / 1024 AS size_mb,
    LAST_MODIFIED
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE RELATIVE_PATH LIKE '%.mp4'
   OR RELATIVE_PATH LIKE '%.mov'
   OR RELATIVE_PATH LIKE '%.avi'
ORDER BY SIZE DESC;

-- Documents
SELECT
    RELATIVE_PATH AS file_name,
    SIZE / 1024 AS size_kb,
    LAST_MODIFIED
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE RELATIVE_PATH LIKE '%.pdf'
   OR RELATIVE_PATH LIKE '%.docx'
   OR RELATIVE_PATH LIKE '%.xlsx'
ORDER BY LAST_MODIFIED DESC;

-- Audio
SELECT
    RELATIVE_PATH AS file_name,
    SIZE / 1024 AS size_kb,
    LAST_MODIFIED
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE RELATIVE_PATH LIKE '%.wav'
   OR RELATIVE_PATH LIKE '%.mp3'
   OR RELATIVE_PATH LIKE '%.flac'
ORDER BY SIZE DESC;

-- =============================================================================
-- Generate Pre-Signed URLs (for external application access)
-- =============================================================================

-- Single file pre-signed URL (valid for 1 hour)
SELECT
    RELATIVE_PATH,
    GET_PRESIGNED_URL(@FSXN_MEDIA_STAGE, RELATIVE_PATH, 3600) AS presigned_url
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE RELATIVE_PATH LIKE '%.jpg'
LIMIT 5;

-- =============================================================================
-- Media Catalog View (structured metadata from unstructured files)
-- =============================================================================
CREATE OR REPLACE VIEW MEDIA_CATALOG AS
SELECT
    RELATIVE_PATH AS file_path,
    SPLIT_PART(RELATIVE_PATH, '/', 1) AS category,  -- images/, videos/, etc.
    SPLIT_PART(RELATIVE_PATH, '.', -1) AS extension,
    SIZE AS file_size_bytes,
    ROUND(SIZE / 1024.0, 2) AS file_size_kb,
    ROUND(SIZE / 1024.0 / 1024.0, 2) AS file_size_mb,
    LAST_MODIFIED,
    MD5 AS file_hash,
    CASE
        WHEN RELATIVE_PATH LIKE '%.jpg' OR RELATIVE_PATH LIKE '%.jpeg'
             OR RELATIVE_PATH LIKE '%.png' OR RELATIVE_PATH LIKE '%.tiff' THEN 'image'
        WHEN RELATIVE_PATH LIKE '%.mp4' OR RELATIVE_PATH LIKE '%.mov'
             OR RELATIVE_PATH LIKE '%.avi' THEN 'video'
        WHEN RELATIVE_PATH LIKE '%.wav' OR RELATIVE_PATH LIKE '%.mp3'
             OR RELATIVE_PATH LIKE '%.flac' THEN 'audio'
        WHEN RELATIVE_PATH LIKE '%.pdf' OR RELATIVE_PATH LIKE '%.docx'
             OR RELATIVE_PATH LIKE '%.xlsx' THEN 'document'
        ELSE 'other'
    END AS media_type
FROM DIRECTORY(@FSXN_MEDIA_STAGE);

-- Query the catalog
SELECT media_type, COUNT(*) AS file_count,
       SUM(file_size_mb) AS total_size_mb,
       AVG(file_size_kb) AS avg_size_kb
FROM MEDIA_CATALOG
GROUP BY media_type
ORDER BY total_size_mb DESC;

-- =============================================================================
-- Summary Statistics
-- =============================================================================
SELECT
    COUNT(*) AS total_files,
    SUM(SIZE) / 1024 / 1024 / 1024 AS total_size_gb,
    MIN(LAST_MODIFIED) AS oldest_file,
    MAX(LAST_MODIFIED) AS newest_file
FROM DIRECTORY(@FSXN_MEDIA_STAGE);

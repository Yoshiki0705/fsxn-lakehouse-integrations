-- =============================================================================
-- 08 - Directory Table for Unstructured Data on FSx for ONTAP
-- =============================================================================
-- Manages metadata for unstructured files (images, video, audio, documents)
-- stored on FSx for NetApp ONTAP via S3 Access Point.
--
-- Snowflake cannot directly query binary file content, but Directory Tables
-- provide metadata (name, size, last_modified, etag) and Pre-signed URLs
-- for external application access.
--
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ IMPORTANT: FSx for ONTAP S3 Access Point Limitations with Directory Tables       │
-- ├─────────────────────────────────────────────────────────────────────────┤
-- │ 1. AUTO_REFRESH = FALSE is REQUIRED.                                    │
-- │    FSx for ONTAP S3 Access Points do NOT support S3 Event Notifications,         │
-- │    which Snowflake relies on for automatic directory refresh.            │
-- │                                                                         │
-- │ 2. Manual refresh (ALTER STAGE ... REFRESH) must be executed:            │
-- │    - After uploading new files to FSx for ONTAP via NFS/SMB                      │
-- │    - Before querying the Directory Table for up-to-date results         │
-- │    - Can be automated via Snowflake Task on a schedule                  │
-- │                                                                         │
-- │ 3. Refresh latency depends on file count:                               │
-- │    - < 1,000 files: 5-10 seconds                                        │
-- │    - 1,000-10,000 files: 10-30 seconds                                  │
-- │    - > 10,000 files: 30+ seconds (consider partitioning by subfolder)   │
-- │                                                                         │
-- │ 4. Alternative for near-real-time: Use FPolicy event-driven approach    │
-- │    (see 06_snowpipe.sql) to trigger refresh on file changes.            │
-- └─────────────────────────────────────────────────────────────────────────┘
-- =============================================================================

-- =============================================================================
-- 1. Context Setup
-- =============================================================================
USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA MEDIA;

-- =============================================================================
-- 2. Stage with Directory Table Enabled
-- =============================================================================
-- NOTE: AUTO_REFRESH = FALSE because FSx for ONTAP S3 Access Points do NOT support
-- S3 Event Notifications. Snowflake cannot receive automatic notifications
-- when files are added/removed on FSx for ONTAP. Manual refresh is required.
--
-- AWS_ACCESS_POINT_ARN is mandatory. Without it the Directory Table can be
-- refreshed and listed, but every attempt to read file bytes — which is what
-- pre-signed URL retrieval and the Snowpark UDFs in 09/10 do — fails with
-- "Failed to access remote file: access denied". Verified 2026-08-06; see
-- integrations/snowflake/docs/en/snowpipe-verification-results.md
CREATE OR REPLACE STAGE FSXN_MEDIA_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<AP_ALIAS>/media/'
  AWS_ACCESS_POINT_ARN = '<AP_ARN>'
  DIRECTORY = (ENABLE = TRUE, AUTO_REFRESH = FALSE)
  COMMENT = 'FSx for ONTAP media files with Directory Table. AUTO_REFRESH=FALSE due to FSx for ONTAP S3 AP limitation (no S3 Event Notifications).';

-- =============================================================================
-- 3. Manual Directory Refresh
-- =============================================================================
-- Since AUTO_REFRESH is disabled, we must manually refresh to index files.
-- This scans the stage location and updates the Directory Table metadata.
-- Run this after uploading new files to FSx for ONTAP via NFS/SMB.
ALTER STAGE FSXN_MEDIA_STAGE REFRESH;

-- =============================================================================
-- 4. Verify Directory Table — Query File Metadata
-- =============================================================================
-- The Directory Table exposes: RELATIVE_PATH, SIZE, LAST_MODIFIED, MD5, ETAG, FILE_URL
SELECT * FROM DIRECTORY(@FSXN_MEDIA_STAGE);

-- Detailed view with all metadata columns
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
-- 5. MEDIA_CATALOG View — Categorize Files by Type
-- =============================================================================
-- Categorizes files into: Images, Documents, Videos, Audio, Other
-- File type classification:
--   Images:    .jpg, .jpeg, .png, .gif, .bmp, .tiff
--   Documents: .pdf, .docx, .doc, .xlsx, .pptx
--   Videos:    .mp4, .avi, .mov, .mkv
--   Audio:     .mp3, .wav, .flac
CREATE OR REPLACE VIEW MEDIA_CATALOG AS
SELECT
    RELATIVE_PATH AS file_path,
    -- Extract filename from path
    SPLIT_PART(RELATIVE_PATH, '/', -1) AS file_name,
    -- Extract subdirectory (first path component)
    CASE
        WHEN CONTAINS(RELATIVE_PATH, '/') THEN SPLIT_PART(RELATIVE_PATH, '/', 1)
        ELSE '(root)'
    END AS subdirectory,
    -- Extract file extension (lowercase for consistent matching)
    LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) AS extension,
    -- File sizes in multiple units
    SIZE AS file_size_bytes,
    ROUND(SIZE / 1024.0, 2) AS file_size_kb,
    ROUND(SIZE / 1024.0 / 1024.0, 4) AS file_size_mb,
    -- Timestamps
    LAST_MODIFIED,
    -- File integrity
    MD5 AS file_hash,
    ETAG,
    -- Media type classification
    CASE
        -- Images: .jpg, .jpeg, .png, .gif, .bmp, .tiff
        WHEN LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff')
            THEN 'Image'
        -- Documents: .pdf, .docx, .doc, .xlsx, .pptx
        WHEN LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('pdf', 'docx', 'doc', 'xlsx', 'pptx')
            THEN 'Document'
        -- Videos: .mp4, .avi, .mov, .mkv
        WHEN LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('mp4', 'avi', 'mov', 'mkv')
            THEN 'Video'
        -- Audio: .mp3, .wav, .flac
        WHEN LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('mp3', 'wav', 'flac')
            THEN 'Audio'
        ELSE 'Other'
    END AS media_type
FROM DIRECTORY(@FSXN_MEDIA_STAGE);

-- =============================================================================
-- 6. File Count by Type
-- =============================================================================
-- Summary: how many files of each media type are stored on FSx for ONTAP
SELECT
    media_type,
    COUNT(*) AS file_count,
    ROUND(SUM(file_size_mb), 2) AS total_size_mb,
    ROUND(AVG(file_size_kb), 2) AS avg_size_kb,
    MIN(LAST_MODIFIED) AS oldest_file,
    MAX(LAST_MODIFIED) AS newest_file
FROM MEDIA_CATALOG
GROUP BY media_type
ORDER BY file_count DESC;

-- =============================================================================
-- 7. Total Size Summary
-- =============================================================================
-- Overall storage consumption for media files on FSx for ONTAP
SELECT
    COUNT(*) AS total_files,
    ROUND(SUM(SIZE) / 1024.0 / 1024.0, 2) AS total_size_mb,
    ROUND(SUM(SIZE) / 1024.0 / 1024.0 / 1024.0, 4) AS total_size_gb,
    MIN(LAST_MODIFIED) AS oldest_file,
    MAX(LAST_MODIFIED) AS newest_file
FROM DIRECTORY(@FSXN_MEDIA_STAGE);

-- Breakdown by file extension
SELECT
    LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) AS extension,
    COUNT(*) AS file_count,
    ROUND(SUM(SIZE) / 1024.0 / 1024.0, 2) AS total_size_mb
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
GROUP BY extension
ORDER BY total_size_mb DESC;

-- =============================================================================
-- 8. Pre-Signed URLs for External Application Access
-- =============================================================================
-- NOTE: AWS documentation states that Presign is "Not supported" for FSx for ONTAP S3
-- Access Points. However, testing confirms GET_PRESIGNED_URL() works correctly
-- with FSx for ONTAP S3 AP in practice. URLs are generated and files are accessible.
--
-- Use cases:
--   1. Provide temporary download links to external applications
--   2. Embed image URLs in dashboards or reports
--   3. Share files with users who don't have direct S3/NFS access
-- =============================================================================

-- Generate Pre-signed URLs for image files (1-hour expiry)
SELECT
    RELATIVE_PATH,
    GET_PRESIGNED_URL(@FSXN_MEDIA_STAGE, RELATIVE_PATH, 3600) AS presigned_url
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('jpg', 'jpeg', 'png')
LIMIT 5;

-- =============================================================================
-- 9. Optional: Scheduled Refresh Task
-- =============================================================================
-- Since FSx for ONTAP doesn't support auto-refresh, you can schedule periodic refreshes
-- using a Snowflake Task. This ensures the Directory Table stays reasonably current.
--
-- CREATE OR REPLACE TASK REFRESH_MEDIA_DIRECTORY
--   WAREHOUSE = COMPUTE_WH
--   SCHEDULE = 'USING CRON 0 */1 * * * UTC'  -- Every hour
-- AS
--   ALTER STAGE FSXN_MEDIA_STAGE REFRESH;
--
-- ALTER TASK REFRESH_MEDIA_DIRECTORY RESUME;
--
-- NOTE: Adjust schedule based on how frequently files are added to FSx for ONTAP.
-- For near-real-time needs, consider FPolicy event-driven refresh instead.
-- =============================================================================

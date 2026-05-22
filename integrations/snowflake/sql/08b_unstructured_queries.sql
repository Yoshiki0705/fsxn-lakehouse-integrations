-- =============================================================================
-- 08b - Unstructured Data Queries: Directory Table + Pre-signed URLs
-- =============================================================================
-- Demonstrates querying unstructured file metadata from FSx for NetApp ONTAP
-- via Directory Table, filtering by file type, and generating Pre-signed URLs
-- for external access.
--
-- Prerequisites:
--   - 08_directory_table.sql executed (FSXN_MEDIA_STAGE + MEDIA_CATALOG view)
--   - Media files uploaded to FSxN media/ path via NFS/SMB
--   - ALTER STAGE FSXN_MEDIA_STAGE REFRESH executed after upload
--
-- Validates: REQ-6 (Unstructured Data via Directory Table + Pre-signed URLs)
-- =============================================================================

-- =============================================================================
-- 1. Context Setup
-- =============================================================================
USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA MEDIA;

-- =============================================================================
-- 2. Refresh Directory Table (ensure latest file listing)
-- =============================================================================
-- Required before querying because FSxN S3 AP does NOT support auto-refresh.
-- See 08_directory_table.sql for details on this limitation.
ALTER STAGE FSXN_MEDIA_STAGE REFRESH;

-- =============================================================================
-- 3. File Type Filtering — Images
-- =============================================================================
-- Query Directory Table for image files (JPEG, PNG)
-- These are the primary image formats uploaded by upload-media-samples.sh
SELECT
    RELATIVE_PATH,
    SIZE AS file_size_bytes,
    ROUND(SIZE / 1024.0, 2) AS file_size_kb,
    LAST_MODIFIED,
    MD5
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('jpg', 'jpeg', 'png')
ORDER BY LAST_MODIFIED DESC;

-- =============================================================================
-- 4. File Type Filtering — Documents
-- =============================================================================
-- Query Directory Table for document files (PDF, DOCX)
SELECT
    RELATIVE_PATH,
    SIZE AS file_size_bytes,
    ROUND(SIZE / 1024.0, 2) AS file_size_kb,
    LAST_MODIFIED,
    MD5
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('pdf', 'docx')
ORDER BY LAST_MODIFIED DESC;

-- =============================================================================
-- 5. File Type Filtering — Videos
-- =============================================================================
-- Query Directory Table for video files (MP4)
SELECT
    RELATIVE_PATH,
    SIZE AS file_size_bytes,
    ROUND(SIZE / 1024.0 / 1024.0, 2) AS file_size_mb,
    LAST_MODIFIED,
    MD5
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('mp4')
ORDER BY LAST_MODIFIED DESC;

-- =============================================================================
-- 6. Pre-signed URL Generation
-- =============================================================================
-- NOTE: AWS documentation states that Presign is "Not supported" for FSxN S3
-- Access Points. However, testing confirms GET_PRESIGNED_URL() works correctly
-- with FSxN S3 AP in practice. URLs are generated and files are accessible.
-- =============================================================================

-- 6a. Pre-signed URLs for ALL files
SELECT
    RELATIVE_PATH,
    ROUND(SIZE / 1024.0, 2) AS file_size_kb,
    GET_PRESIGNED_URL(@FSXN_MEDIA_STAGE, RELATIVE_PATH, 3600) AS presigned_url
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
ORDER BY RELATIVE_PATH;

-- 6b. Pre-signed URLs for images only
SELECT
    RELATIVE_PATH,
    ROUND(SIZE / 1024.0, 2) AS file_size_kb,
    GET_PRESIGNED_URL(@FSXN_MEDIA_STAGE, RELATIVE_PATH, 3600) AS presigned_url
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('jpg', 'jpeg', 'png')
ORDER BY RELATIVE_PATH;

-- 6c. Pre-signed URLs for documents only
SELECT
    RELATIVE_PATH,
    ROUND(SIZE / 1024.0, 2) AS file_size_kb,
    GET_PRESIGNED_URL(@FSXN_MEDIA_STAGE, RELATIVE_PATH, 3600) AS presigned_url
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('pdf', 'docx')
ORDER BY RELATIVE_PATH;

-- 6d. Pre-signed URLs for videos only
SELECT
    RELATIVE_PATH,
    ROUND(SIZE / 1024.0 / 1024.0, 2) AS file_size_mb,
    GET_PRESIGNED_URL(@FSXN_MEDIA_STAGE, RELATIVE_PATH, 3600) AS presigned_url
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('mp4')
ORDER BY RELATIVE_PATH;

-- =============================================================================
-- 7. MEDIA_CATALOG View — Reference and Verification
-- =============================================================================
-- The MEDIA_CATALOG view is defined in 08_directory_table.sql.
-- It categorizes files by media_type (Image, Document, Video, Audio, Other)
-- and provides normalized metadata columns.
--
-- If the view does not exist (e.g., running this script standalone), create it:
CREATE VIEW IF NOT EXISTS MEDIA_CATALOG AS
SELECT
    RELATIVE_PATH AS file_path,
    SPLIT_PART(RELATIVE_PATH, '/', -1) AS file_name,
    CASE
        WHEN CONTAINS(RELATIVE_PATH, '/') THEN SPLIT_PART(RELATIVE_PATH, '/', 1)
        ELSE '(root)'
    END AS subdirectory,
    LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) AS extension,
    SIZE AS file_size_bytes,
    ROUND(SIZE / 1024.0, 2) AS file_size_kb,
    ROUND(SIZE / 1024.0 / 1024.0, 4) AS file_size_mb,
    LAST_MODIFIED,
    MD5 AS file_hash,
    ETAG,
    CASE
        WHEN LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff')
            THEN 'Image'
        WHEN LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('pdf', 'docx', 'doc', 'xlsx', 'pptx')
            THEN 'Document'
        WHEN LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('mp4', 'avi', 'mov', 'mkv')
            THEN 'Video'
        WHEN LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('mp3', 'wav', 'flac')
            THEN 'Audio'
        ELSE 'Other'
    END AS media_type
FROM DIRECTORY(@FSXN_MEDIA_STAGE);

-- =============================================================================
-- 8. MEDIA_CATALOG Aggregation Queries
-- =============================================================================

-- 8a. File count and total size by media type
SELECT
    media_type,
    COUNT(*) AS file_count,
    ROUND(SUM(file_size_mb), 2) AS total_size_mb,
    ROUND(SUM(file_size_mb) / 1024.0, 4) AS total_size_gb,
    ROUND(AVG(file_size_kb), 2) AS avg_size_kb,
    MIN(LAST_MODIFIED) AS oldest_file,
    MAX(LAST_MODIFIED) AS newest_file
FROM MEDIA_CATALOG
GROUP BY media_type
ORDER BY file_count DESC;

-- 8b. File count by extension (detailed breakdown)
SELECT
    extension,
    media_type,
    COUNT(*) AS file_count,
    ROUND(SUM(file_size_mb), 2) AS total_size_mb
FROM MEDIA_CATALOG
GROUP BY extension, media_type
ORDER BY media_type, file_count DESC;

-- 8c. Files by subdirectory
SELECT
    subdirectory,
    COUNT(*) AS file_count,
    ROUND(SUM(file_size_mb), 2) AS total_size_mb
FROM MEDIA_CATALOG
GROUP BY subdirectory
ORDER BY file_count DESC;

-- =============================================================================
-- 9. Acceptance Criteria Verification Queries
-- =============================================================================
-- These queries validate REQ-6 acceptance criteria for unstructured data access.

-- 9a. Total files cataloged in Directory Table
SELECT
    'Total Files Cataloged' AS metric,
    COUNT(*) AS value
FROM DIRECTORY(@FSXN_MEDIA_STAGE);

-- 9b. File count by type (Images, Documents, Videos)
SELECT
    media_type,
    COUNT(*) AS file_count
FROM MEDIA_CATALOG
WHERE media_type IN ('Image', 'Document', 'Video')
GROUP BY media_type
ORDER BY
    CASE media_type
        WHEN 'Image' THEN 1
        WHEN 'Document' THEN 2
        WHEN 'Video' THEN 3
    END;

-- 9c. Total storage size in GB
SELECT
    'Total Size (GB)' AS metric,
    ROUND(SUM(SIZE) / 1024.0 / 1024.0 / 1024.0, 4) AS value_gb
FROM DIRECTORY(@FSXN_MEDIA_STAGE);

-- 9d. Verification summary — single row with all key metrics
SELECT
    COUNT(*) AS total_files,
    SUM(CASE WHEN media_type = 'Image' THEN 1 ELSE 0 END) AS image_count,
    SUM(CASE WHEN media_type = 'Document' THEN 1 ELSE 0 END) AS document_count,
    SUM(CASE WHEN media_type = 'Video' THEN 1 ELSE 0 END) AS video_count,
    ROUND(SUM(file_size_mb), 2) AS total_size_mb,
    ROUND(SUM(file_size_mb) / 1024.0, 4) AS total_size_gb
FROM MEDIA_CATALOG;

-- =============================================================================
-- 10. Pre-signed URL Accessibility Testing
-- =============================================================================
-- After generating Pre-signed URLs (Section 6), verify accessibility using:
--
-- Option A: curl (command line)
--   Copy a presigned_url value from the query results and run:
--
--   curl -o downloaded_file.jpg "<PRESIGNED_URL>"
--
--   Expected: HTTP 200, file downloaded successfully.
--   If HTTP 403: Check Storage Integration permissions or URL expiry.
--
-- Option B: Browser
--   Paste the presigned_url directly into a web browser address bar.
--   The file should download or display (for images/PDFs).
--
-- Option C: Python (programmatic verification)
--   import requests
--   url = "<PRESIGNED_URL>"
--   response = requests.get(url)
--   assert response.status_code == 200
--   print(f"Downloaded {len(response.content)} bytes")
--
-- Notes:
--   - Pre-signed URLs expire after the specified duration (3600s = 1 hour)
--   - URLs are tied to the Storage Integration IAM Role credentials
--   - Each URL is unique per file and generation time
--   - Expired URLs return HTTP 403 Forbidden
--   - URLs work from any network (no VPN/VPC required)
-- =============================================================================

-- End of 08b_unstructured_queries.sql

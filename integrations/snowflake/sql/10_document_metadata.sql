-- =============================================================================
-- 10 - Document Metadata Catalog (PDF/DOCX) with Snowpark UDF
-- =============================================================================
-- Queries the Directory Table for document files (PDF, DOCX) stored on FSxN,
-- applies a Snowpark Python UDF to estimate page counts based on file size,
-- and builds a persistent DOCUMENT_CATALOG table for downstream analytics.
--
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ LIMITATIONS: Page Count Estimation vs Actual Page Count                  │
-- ├─────────────────────────────────────────────────────────────────────────┤
-- │ 1. This UDF ESTIMATES page count from file size — it does NOT parse     │
-- │    the actual PDF/DOCX binary content. Accuracy varies significantly.   │
-- │                                                                         │
-- │ 2. Estimation heuristics:                                               │
-- │    - PDF: ~100 KB per page (text-heavy). Image-heavy PDFs may be        │
-- │      500 KB–2 MB per page, leading to underestimation.                  │
-- │    - DOCX: ~50 KB per page (text-heavy). Embedded images inflate size.  │
-- │                                                                         │
-- │ 3. For accurate page counts, use External Functions (AWS Lambda) with   │
-- │    libraries like PyPDF2 (PDF) or python-docx (DOCX) to parse binary    │
-- │    content directly. This requires reading file bytes via Pre-signed URL.│
-- │                                                                         │
-- │ 4. Confidence levels returned by the UDF:                               │
-- │    - 'high':   Small text-heavy files (< 500 KB) — estimation reliable  │
-- │    - 'medium': Medium files (500 KB – 5 MB) — reasonable estimate       │
-- │    - 'low':    Large files (> 5 MB) — likely image/scan-heavy,          │
-- │               estimation unreliable                                      │
-- │                                                                         │
-- │ 5. The 'method' field documents the estimation approach for transparency.│
-- └─────────────────────────────────────────────────────────────────────────┘
--
-- Requirements: REQ-6 (Unstructured Data via Directory Table)
--               REQ-7 (Snowpark UDF processing for media files)
-- =============================================================================

-- =============================================================================
-- 1. Context Setup
-- =============================================================================
USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA MEDIA;

-- =============================================================================
-- 2. Query Directory Table for PDF/DOCX Files Only
-- =============================================================================
-- Filter the Directory Table to show only document files (PDF, DOCX).
-- This demonstrates targeted querying of unstructured file metadata on FSxN.

-- Refresh stage to ensure latest files are indexed
ALTER STAGE FSXN_MEDIA_STAGE REFRESH;

-- Query documents only
SELECT
    RELATIVE_PATH,
    SPLIT_PART(RELATIVE_PATH, '/', -1) AS file_name,
    LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) AS extension,
    SIZE AS file_size_bytes,
    ROUND(SIZE / 1024.0, 2) AS file_size_kb,
    ROUND(SIZE / 1024.0 / 1024.0, 4) AS file_size_mb,
    LAST_MODIFIED
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('pdf', 'docx')
ORDER BY SIZE DESC;

-- =============================================================================
-- 3. Snowpark UDF: ESTIMATE_DOCUMENT_PAGES
-- =============================================================================
-- Estimates the number of pages in a document based on file size and extension.
-- Returns VARIANT with: estimated_pages, confidence, method
--
-- Estimation heuristics:
--   PDF:  ~100 KB per page (text-heavy average)
--   DOCX: ~50 KB per page (text-heavy average, compressed XML)
--
-- Confidence levels:
--   'high':   File < 500 KB — likely text-only, estimation reliable
--   'medium': File 500 KB – 5 MB — mixed content, reasonable estimate
--   'low':    File > 5 MB — likely image/scan-heavy, estimation unreliable
--
-- Snowpark Runtime: Python 3.11 (built-in modules only — no Anaconda packages)
-- =============================================================================
CREATE OR REPLACE FUNCTION ESTIMATE_DOCUMENT_PAGES(file_size NUMBER, extension STRING)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ()
HANDLER = 'estimate_document_pages'
COMMENT = 'Estimates page count for PDF/DOCX based on file size. Returns estimated_pages, confidence, and method. NOTE: This is a heuristic estimate — not actual page count parsing.'
AS
$$
def estimate_document_pages(file_size: int, extension: str) -> dict:
    """
    Estimate the number of pages in a document based on file size and type.

    Heuristics:
        - PDF: average ~100 KB per page (text-heavy)
        - DOCX: average ~50 KB per page (compressed XML, text-heavy)

    Args:
        file_size: file size in bytes
        extension: file extension (e.g., 'pdf', 'docx')

    Returns:
        dict with:
            - estimated_pages: int, estimated number of pages (minimum 1)
            - confidence: str, 'high', 'medium', or 'low'
            - method: str, description of estimation approach
    """
    if not file_size or file_size <= 0:
        return {
            'estimated_pages': 0,
            'confidence': 'none',
            'method': 'no_data — file size is zero or missing'
        }

    # Normalize extension
    ext = (extension or '').lower().strip().lstrip('.')

    # Bytes per page heuristic by document type
    if ext == 'pdf':
        bytes_per_page = 100 * 1024  # ~100 KB per page
        method = 'size_heuristic — PDF avg 100 KB/page (text-heavy assumption)'
    elif ext in ('docx', 'doc'):
        bytes_per_page = 50 * 1024   # ~50 KB per page
        method = 'size_heuristic — DOCX avg 50 KB/page (compressed XML assumption)'
    else:
        # Fallback for unknown document types
        bytes_per_page = 75 * 1024   # ~75 KB per page (generic)
        method = 'size_heuristic — generic avg 75 KB/page (unknown document type)'

    # Calculate estimated pages (minimum 1)
    estimated_pages = max(1, round(file_size / bytes_per_page))

    # Determine confidence based on file size
    file_size_kb = file_size / 1024.0
    if file_size_kb < 500:
        confidence = 'high'
    elif file_size_kb <= 5120:  # 5 MB
        confidence = 'medium'
    else:
        confidence = 'low'

    return {
        'estimated_pages': estimated_pages,
        'confidence': confidence,
        'method': method
    }
$$;

-- Test ESTIMATE_DOCUMENT_PAGES UDF with sample values
SELECT
    ESTIMATE_DOCUMENT_PAGES(102400, 'pdf')   AS pdf_1page,    -- 100 KB → ~1 page
    ESTIMATE_DOCUMENT_PAGES(512000, 'pdf')   AS pdf_5pages,   -- 500 KB → ~5 pages
    ESTIMATE_DOCUMENT_PAGES(1048576, 'docx') AS docx_20pages; -- 1 MB → ~20 pages

-- Apply UDF to actual Directory Table documents
SELECT
    RELATIVE_PATH,
    SIZE,
    LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) AS ext,
    ESTIMATE_DOCUMENT_PAGES(SIZE, LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1))) AS page_estimate
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('pdf', 'docx')
ORDER BY SIZE DESC;

-- =============================================================================
-- 4. Create DOCUMENT_CATALOG Table
-- =============================================================================
-- Persistent table storing document metadata enriched with page estimates.
-- Combines Directory Table metadata with ESTIMATE_DOCUMENT_PAGES UDF output.
--
-- Columns:
--   file_path       - Full relative path from stage root
--   file_name       - Extracted filename
--   extension       - File extension (pdf, docx)
--   estimated_pages - Estimated page count from UDF
--   file_size_bytes - Raw file size in bytes
--   file_size_kb    - File size in kilobytes
--   last_modified   - File last modified timestamp (from Directory Table)
--   cataloged_at    - Timestamp when this record was inserted
-- =============================================================================
CREATE OR REPLACE TABLE DOCUMENT_CATALOG (
    file_path        STRING        NOT NULL,
    file_name        STRING        NOT NULL,
    extension        STRING        NOT NULL,
    estimated_pages  NUMBER,
    file_size_bytes  NUMBER,
    file_size_kb     NUMBER(18, 2),
    last_modified    TIMESTAMP_NTZ,
    cataloged_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'Document catalog for PDF/DOCX files on FSxN. Page counts are ESTIMATES based on file size heuristics (not actual binary parsing). See ESTIMATE_DOCUMENT_PAGES UDF for methodology.';

-- =============================================================================
-- 5. Populate DOCUMENT_CATALOG from Directory Table + UDF
-- =============================================================================
-- Insert all PDF/DOCX files with their estimated page counts.
INSERT INTO DOCUMENT_CATALOG (
    file_path,
    file_name,
    extension,
    estimated_pages,
    file_size_bytes,
    file_size_kb,
    last_modified,
    cataloged_at
)
SELECT
    RELATIVE_PATH                                              AS file_path,
    SPLIT_PART(RELATIVE_PATH, '/', -1)                         AS file_name,
    LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1))                  AS extension,
    ESTIMATE_DOCUMENT_PAGES(
        SIZE,
        LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1))
    ):estimated_pages::NUMBER                                   AS estimated_pages,
    SIZE                                                        AS file_size_bytes,
    ROUND(SIZE / 1024.0, 2)                                    AS file_size_kb,
    LAST_MODIFIED                                               AS last_modified,
    CURRENT_TIMESTAMP()                                        AS cataloged_at
FROM DIRECTORY(@FSXN_MEDIA_STAGE)
WHERE LOWER(SPLIT_PART(RELATIVE_PATH, '.', -1)) IN ('pdf', 'docx');

-- =============================================================================
-- 6. Verification Queries
-- =============================================================================

-- 6a. Total documents cataloged
SELECT
    COUNT(*) AS total_documents,
    COUNT(DISTINCT extension) AS distinct_extensions,
    SUM(estimated_pages) AS total_estimated_pages,
    ROUND(AVG(estimated_pages), 1) AS avg_pages_per_document
FROM DOCUMENT_CATALOG;

-- 6b. Document count and average size by extension
SELECT
    extension,
    COUNT(*) AS document_count,
    ROUND(AVG(file_size_kb), 2) AS avg_size_kb,
    ROUND(SUM(file_size_kb) / 1024.0, 2) AS total_size_mb,
    SUM(estimated_pages) AS total_estimated_pages,
    ROUND(AVG(estimated_pages), 1) AS avg_pages
FROM DOCUMENT_CATALOG
GROUP BY extension
ORDER BY document_count DESC;

-- 6c. Page estimate distribution with confidence levels
-- Join back to UDF for full VARIANT output including confidence
SELECT
    dc.file_path,
    dc.file_name,
    dc.extension,
    dc.estimated_pages,
    dc.file_size_kb,
    ESTIMATE_DOCUMENT_PAGES(dc.file_size_bytes, dc.extension):confidence::STRING AS confidence,
    ESTIMATE_DOCUMENT_PAGES(dc.file_size_bytes, dc.extension):method::STRING AS method
FROM DOCUMENT_CATALOG dc
ORDER BY dc.estimated_pages DESC;

-- 6d. Confidence level summary
SELECT
    ESTIMATE_DOCUMENT_PAGES(file_size_bytes, extension):confidence::STRING AS confidence_level,
    COUNT(*) AS document_count,
    ROUND(AVG(estimated_pages), 1) AS avg_estimated_pages,
    ROUND(AVG(file_size_kb), 2) AS avg_size_kb
FROM DOCUMENT_CATALOG
GROUP BY confidence_level
ORDER BY
    CASE confidence_level
        WHEN 'high' THEN 1
        WHEN 'medium' THEN 2
        WHEN 'low' THEN 3
        ELSE 4
    END;

-- 6e. Largest documents (potential scan/image-heavy files)
SELECT
    file_name,
    extension,
    file_size_kb,
    estimated_pages,
    ESTIMATE_DOCUMENT_PAGES(file_size_bytes, extension):confidence::STRING AS confidence
FROM DOCUMENT_CATALOG
ORDER BY file_size_bytes DESC
LIMIT 10;

-- =============================================================================
-- End of Script
-- =============================================================================
-- Summary:
--   - Queried Directory Table for PDF/DOCX files on FSxN
--   - Created ESTIMATE_DOCUMENT_PAGES UDF (Python 3.11, no external packages)
--   - Built DOCUMENT_CATALOG table with estimated page counts
--   - Verification queries show document distribution and confidence levels
--
-- Limitations (IMPORTANT):
--   - Page counts are ESTIMATES based on file size heuristics
--   - Accuracy depends heavily on document content type:
--       * Text-heavy documents: estimation is reasonably accurate
--       * Image-heavy/scanned PDFs: pages will be significantly underestimated
--       * DOCX with embedded media: pages may be overestimated
--   - For production use cases requiring accurate page counts, implement
--     External Functions (AWS Lambda) with PyPDF2/python-docx binary parsing
--   - The confidence field helps identify which estimates are reliable
--
-- Next Steps:
--   - Use DOCUMENT_CATALOG for document inventory reporting
--   - Filter by confidence = 'high' for reliable page estimates
--   - Implement Lambda-based External Function for accurate page extraction
--   - Schedule periodic refresh: ALTER STAGE REFRESH + MERGE for new documents
-- =============================================================================

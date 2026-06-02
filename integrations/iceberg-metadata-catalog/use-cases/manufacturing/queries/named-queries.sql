-- Manufacturing — Athena Named Queries
-- Catalog: s3tablescatalog/fsxn-metadata-catalog
-- Namespace: metadata
-- Table: unstructured_files

-- =============================================================================
-- 1. Find engineering drawings by part number
-- =============================================================================
-- Name: mfg_drawings_by_part
SELECT file_name, file_path, revision, confidence_score, modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'engineering_drawing'
  AND file_name LIKE '%P-2000%'
  AND is_deleted = false
ORDER BY modified_at DESC;

-- =============================================================================
-- 2. QC reports mentioning temperature deviation (last 6 months)
-- =============================================================================
-- Name: mfg_qc_temperature
SELECT file_name, classification, summary, confidence_score, modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'quality_report'
  AND summary LIKE '%temperature%'
  AND modified_at > current_timestamp - interval '6' month
  AND is_deleted = false
ORDER BY modified_at DESC;

-- =============================================================================
-- 3. Files modified since last ISO audit date
-- =============================================================================
-- Name: mfg_since_last_audit
SELECT file_name, file_type, classification, change_type, modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE modified_at > TIMESTAMP '2026-01-15 00:00:00'  -- Replace with last audit date
  AND is_deleted = false
ORDER BY modified_at DESC
LIMIT 100;

-- =============================================================================
-- 4. Document distribution by category
-- =============================================================================
-- Name: mfg_category_distribution
SELECT classification, COUNT(*) AS file_count,
       SUM(file_size) / (1024*1024) AS total_mb,
       AVG(confidence_score) AS avg_confidence
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
GROUP BY classification
ORDER BY file_count DESC;

-- =============================================================================
-- 5. Latest record per file (deduplication)
-- =============================================================================
-- Name: mfg_latest_records
WITH ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY file_id ORDER BY modified_at DESC) as rn
  FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
)
SELECT file_name, file_type, classification, confidence_score, modified_at
FROM ranked
WHERE rn = 1 AND is_deleted = false
ORDER BY modified_at DESC
LIMIT 50;

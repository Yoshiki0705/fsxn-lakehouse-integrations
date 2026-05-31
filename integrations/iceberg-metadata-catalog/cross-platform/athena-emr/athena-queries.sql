-- =============================================================================
-- Athena Named Queries for Iceberg Metadata Catalog
-- =============================================================================
-- Prerequisites:
--   - S3 Tables table bucket registered in Glue Catalog (via SageMaker Lakehouse)
--   - Lake Formation permissions granted to querying role
--   - Athena workgroup configured with results location
--
-- Catalog: Use the S3 Tables catalog name registered in Glue
-- Database: metadata
-- Table: unstructured_files
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Basic Discovery: File type distribution
-- ---------------------------------------------------------------------------
SELECT
    file_type,
    COUNT(*) AS file_count,
    SUM(file_size) AS total_bytes,
    ROUND(SUM(file_size) / 1024.0 / 1024.0 / 1024.0, 2) AS total_gb,
    MIN(created_at) AS earliest_file,
    MAX(created_at) AS latest_file
FROM "metadata"."unstructured_files"
WHERE is_deleted = false
GROUP BY file_type
ORDER BY total_bytes DESC;

-- ---------------------------------------------------------------------------
-- 2. Search by classification (AI-enriched)
-- ---------------------------------------------------------------------------
SELECT
    file_name,
    file_path,
    classification,
    confidence_score,
    summary,
    created_at
FROM "metadata"."unstructured_files"
WHERE classification = 'contract'
  AND confidence_score >= 0.7
  AND is_deleted = false
ORDER BY created_at DESC
LIMIT 50;

-- ---------------------------------------------------------------------------
-- 3. Find files by tag (department filter)
-- ---------------------------------------------------------------------------
SELECT
    file_name,
    file_path,
    file_type,
    element_at(tags, 'department') AS department,
    element_at(tags, 'project') AS project
FROM "metadata"."unstructured_files"
WHERE element_at(tags, 'department') = 'engineering'
  AND is_deleted = false
ORDER BY modified_at DESC
LIMIT 100;

-- ---------------------------------------------------------------------------
-- 4. PII-containing files (compliance review)
-- ---------------------------------------------------------------------------
SELECT
    file_name,
    file_path,
    file_type,
    classification,
    sensitivity_level,
    anonymization_status,
    enriched_at
FROM "metadata"."unstructured_files"
WHERE has_pii = true
  AND is_deleted = false
ORDER BY enriched_at DESC;

-- ---------------------------------------------------------------------------
-- 5. Files pending AI enrichment
-- ---------------------------------------------------------------------------
SELECT
    file_name,
    file_path,
    file_type,
    file_size,
    created_at
FROM "metadata"."unstructured_files"
WHERE enrichment_status = 'pending'
  AND is_deleted = false
ORDER BY created_at ASC
LIMIT 100;

-- ---------------------------------------------------------------------------
-- 6. Recently added files (last 7 days)
-- ---------------------------------------------------------------------------
SELECT
    file_name,
    file_path,
    file_type,
    file_size,
    classification,
    created_at
FROM "metadata"."unstructured_files"
WHERE created_at >= current_timestamp - interval '7' day
  AND is_deleted = false
ORDER BY created_at DESC;

-- ---------------------------------------------------------------------------
-- 7. Large files (> 100MB) — candidates for FabricPool tiering review
-- ---------------------------------------------------------------------------
SELECT
    file_name,
    file_path,
    file_type,
    ROUND(file_size / 1024.0 / 1024.0, 1) AS size_mb,
    source_volume,
    modified_at
FROM "metadata"."unstructured_files"
WHERE file_size > 104857600  -- 100MB
  AND is_deleted = false
ORDER BY file_size DESC
LIMIT 50;

-- ---------------------------------------------------------------------------
-- 8. Enrichment pipeline health check
-- ---------------------------------------------------------------------------
SELECT
    enrichment_status,
    COUNT(*) AS count,
    MIN(created_at) AS oldest_record,
    MAX(enriched_at) AS latest_enrichment
FROM "metadata"."unstructured_files"
WHERE is_deleted = false
GROUP BY enrichment_status
ORDER BY count DESC;

-- ---------------------------------------------------------------------------
-- 9. Classification distribution (AI results quality)
-- ---------------------------------------------------------------------------
SELECT
    classification,
    COUNT(*) AS count,
    ROUND(AVG(confidence_score), 3) AS avg_confidence,
    ROUND(MIN(confidence_score), 3) AS min_confidence,
    ROUND(MAX(confidence_score), 3) AS max_confidence
FROM "metadata"."unstructured_files"
WHERE enrichment_status = 'completed'
  AND is_deleted = false
GROUP BY classification
ORDER BY count DESC;

-- ---------------------------------------------------------------------------
-- 10. Cross-volume file distribution (storage planning)
-- ---------------------------------------------------------------------------
SELECT
    source_volume,
    COUNT(*) AS file_count,
    ROUND(SUM(file_size) / 1024.0 / 1024.0 / 1024.0, 2) AS total_gb,
    COUNT(CASE WHEN has_pii = true THEN 1 END) AS pii_files,
    COUNT(CASE WHEN enrichment_status = 'pending' THEN 1 END) AS pending_enrichment
FROM "metadata"."unstructured_files"
WHERE is_deleted = false
GROUP BY source_volume
ORDER BY total_gb DESC;

-- =============================================================================
-- Genomics — Named Queries
-- Industry: genomics
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: whole_genome, exome, rna_seq, variant_call,
--   quality_report, clinical_annotation
-- =============================================================================

-- Name: Samples by Sequencing Platform
-- Description: Inventory of genomic samples grouped by sequencing platform
SELECT
    sequencing_platform,
    classification,
    COUNT(*) AS sample_count,
    AVG(read_depth) AS avg_read_depth,
    SUM(file_size) AS total_size_bytes,
    MAX(modified_at) AS latest_upload
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND sequencing_platform IS NOT NULL
GROUP BY sequencing_platform, classification
ORDER BY sequencing_platform, sample_count DESC;

-- Name: High-Quality Variant Calls
-- Description: Find variant call files with high read depth and variant count
SELECT
    file_id,
    file_name,
    sample_id,
    study_id,
    sequencing_platform,
    read_depth,
    variant_count,
    confidence_score,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'variant_call'
  AND read_depth >= 30.0
  AND variant_count > 0
ORDER BY read_depth DESC, variant_count DESC;

-- Name: Cross-Study Sample Inventory
-- Description: Find samples shared across multiple studies for data reuse
SELECT
    sample_id,
    COUNT(DISTINCT study_id) AS study_count,
    ARRAY_AGG(DISTINCT study_id) AS studies,
    ARRAY_AGG(DISTINCT sequencing_platform) AS platforms,
    SUM(file_size) AS total_size_bytes
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND sample_id IS NOT NULL
  AND study_id IS NOT NULL
GROUP BY sample_id
HAVING COUNT(DISTINCT study_id) > 1
ORDER BY study_count DESC;

-- Name: Latest Record per File (Deduplication)
-- Description: Deduplicated view showing only the most recent version of each file
SELECT *
FROM (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY file_path
            ORDER BY modified_at DESC
        ) AS row_num
    FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
    WHERE is_deleted = false
) deduped
WHERE row_num = 1
ORDER BY modified_at DESC;

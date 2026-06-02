-- =============================================================================
-- Life Sciences — Named Queries
-- Industry: life-sciences
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: assay_result, compound_structure, microscopy_image,
--   lab_notebook, regulatory_submission, patent_filing
-- =============================================================================

-- Name: Assays by Compound
-- Description: Find assay results grouped by compound for drug discovery analysis
SELECT
    compound_id,
    assay_type,
    COUNT(*) AS assay_count,
    COUNT(DISTINCT experiment_id) AS unique_experiments,
    SUM(file_size) AS total_size_bytes,
    MAX(modified_at) AS latest_result
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'assay_result'
  AND compound_id IS NOT NULL
GROUP BY compound_id, assay_type
ORDER BY compound_id, assay_count DESC;

-- Name: Microscopy Images by Experiment
-- Description: Find microscopy images organized by experiment for analysis
SELECT
    experiment_id,
    file_id,
    file_name,
    compound_id,
    researcher,
    lab_notebook_ref,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'microscopy_image'
  AND experiment_id IS NOT NULL
ORDER BY experiment_id, modified_at DESC;

-- Name: Regulatory Submissions
-- Description: Track regulatory submission documents for compliance management
SELECT
    file_id,
    file_name,
    compound_id,
    researcher,
    lab_notebook_ref,
    confidence_score,
    sensitivity_level,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification IN ('regulatory_submission', 'patent_filing')
ORDER BY classification, modified_at DESC;

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

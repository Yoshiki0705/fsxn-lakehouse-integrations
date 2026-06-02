-- =============================================================================
-- Education — Named Queries
-- Industry: education
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: journal_paper, thesis, dataset, notebook,
--   grant_proposal, course_material
-- =============================================================================

-- Name: Papers by Research Field
-- Description: Inventory of academic papers grouped by research discipline
SELECT
    research_field,
    classification,
    COUNT(*) AS paper_count,
    COUNT(DISTINCT journal) AS unique_journals,
    MIN(publication_year) AS earliest_year,
    MAX(publication_year) AS latest_year
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification IN ('journal_paper', 'thesis')
  AND research_field IS NOT NULL
GROUP BY research_field, classification
ORDER BY paper_count DESC;

-- Name: Datasets by Researcher
-- Description: Find research datasets grouped by principal investigator
SELECT
    funding_source,
    research_field,
    file_id,
    file_name,
    publication_year,
    file_size,
    open_access_status,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'dataset'
ORDER BY funding_source, research_field, modified_at DESC;

-- Name: Open Access Status Summary
-- Description: Analyze open access compliance across research outputs
SELECT
    open_access_status,
    research_field,
    COUNT(*) AS file_count,
    SUM(file_size) AS total_size_bytes,
    MAX(publication_year) AS latest_year
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND open_access_status IS NOT NULL
  AND classification IN ('journal_paper', 'thesis', 'dataset')
GROUP BY open_access_status, research_field
ORDER BY open_access_status, file_count DESC;

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

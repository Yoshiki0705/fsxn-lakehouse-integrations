-- =============================================================================
-- Construction & BIM — Named Queries
-- Industry: construction-bim
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: structural_drawing, architectural_model,
--   mep_design, site_photo, safety_report, as_built
-- =============================================================================

-- Name: Models by Project Phase
-- Description: Inventory of BIM models and drawings grouped by project phase
SELECT
    project_name,
    project_phase,
    discipline,
    classification,
    COUNT(*) AS file_count,
    SUM(file_size) AS total_size_bytes,
    MAX(modified_at) AS latest_update
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND project_name IS NOT NULL
  AND project_phase IS NOT NULL
GROUP BY project_name, project_phase, discipline, classification
ORDER BY project_name, project_phase, discipline;

-- Name: Safety Reports
-- Description: Find all safety reports across projects for compliance tracking
SELECT
    file_id,
    file_name,
    project_name,
    project_phase,
    revision,
    modified_at,
    confidence_score
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'safety_report'
ORDER BY project_name, modified_at DESC;

-- Name: Revision History by Project
-- Description: Track document revisions for audit trail and version control
SELECT
    project_name,
    file_name,
    revision,
    discipline,
    classification,
    ifc_schema_version,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND revision IS NOT NULL
ORDER BY project_name, file_name, modified_at DESC;

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

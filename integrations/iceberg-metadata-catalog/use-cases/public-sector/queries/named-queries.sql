-- =============================================================================
-- Public Sector — Named Queries
-- Industry: public-sector
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: permit_application, council_minutes, gis_map,
--   public_comment, budget_proposal, emergency_plan, foia_response
-- =============================================================================

-- Name: FOIA Pending Requests
-- Description: Find documents with pending FOIA requests requiring action
SELECT
    file_id,
    file_name,
    foia_request_id,
    department,
    disclosure_status,
    redaction_status,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND foia_request_id IS NOT NULL
  AND redaction_status = 'pending'
ORDER BY modified_at ASC;

-- Name: PII Inventory for Government Records
-- Description: Identify government records containing personally identifiable information
SELECT
    file_id,
    file_name,
    department,
    classification,
    sensitivity_level,
    has_pii,
    pii_status,
    disclosure_status,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND has_pii = true
ORDER BY department, sensitivity_level DESC, modified_at DESC;

-- Name: Documents by Retention Schedule
-- Description: Group documents by records retention schedule for lifecycle management
SELECT
    retention_schedule,
    classification,
    COUNT(*) AS document_count,
    SUM(file_size) AS total_size_bytes,
    MIN(created_at) AS oldest_document,
    MAX(modified_at) AS latest_update
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND retention_schedule IS NOT NULL
GROUP BY retention_schedule, classification
ORDER BY retention_schedule, document_count DESC;

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

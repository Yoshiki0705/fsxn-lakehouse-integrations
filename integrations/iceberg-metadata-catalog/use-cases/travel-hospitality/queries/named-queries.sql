-- =============================================================================
-- Travel & Hospitality — Named Queries
-- Industry: travel-hospitality
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: property_photo, room_image, guest_document,
--   maintenance_report, marketing_material, contract
-- =============================================================================

-- Name: Property Photos by Season for Marketing Catalog
-- Description: Find property and room photos filtered by season for OTA/marketing use
SELECT
    property_id,
    room_category,
    season,
    file_name,
    file_size,
    compliance_status,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification IN ('property_photo', 'room_image')
  AND document_type = 'marketing'
ORDER BY property_id, season, room_category;

-- Name: Guest Documents Requiring Retention Review
-- Description: Identify guest documents that may need deletion or archival based on age
SELECT
    file_name,
    property_id,
    document_type,
    compliance_status,
    modified_at,
    CURRENT_DATE - CAST(modified_at AS date) AS days_since_modified
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'guest_document'
  AND compliance_status IN ('review_needed', 'expired')
ORDER BY modified_at ASC;

-- Name: Maintenance Reports by Property and Status
-- Description: Maintenance logs grouped by property for operations planning
SELECT
    property_id,
    compliance_status,
    COUNT(*) AS report_count,
    SUM(file_size) AS total_size_bytes,
    MIN(modified_at) AS oldest_report,
    MAX(modified_at) AS latest_report
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'maintenance_report'
GROUP BY property_id, compliance_status
ORDER BY property_id, compliance_status;

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

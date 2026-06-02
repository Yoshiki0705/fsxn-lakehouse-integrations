-- =============================================================================
-- Telecommunications — Named Queries
-- Industry: telecom
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: network_config, customer_contract,
--   tower_inspection, compliance_filing, capacity_plan, technical_spec
-- =============================================================================

-- Name: Failed Tower Inspections by Region
-- Description: Find tower inspection photos with failed results grouped by region
SELECT
    region_code,
    tower_id,
    file_name,
    equipment_vendor,
    frequency_band,
    inspection_result,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'tower_inspection'
  AND inspection_result = 'fail'
ORDER BY region_code, modified_at DESC;

-- Name: Contracts Expiring in Next 90 Days
-- Description: Customer contracts approaching expiration for renewal planning
SELECT
    file_name,
    tower_id,
    region_code,
    equipment_vendor,
    modified_at,
    file_size
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'customer_contract'
  AND CAST(modified_at AS date) >= CURRENT_DATE - INTERVAL '90' DAY
ORDER BY modified_at ASC;

-- Name: Technical Docs by Equipment Vendor
-- Description: Technical specifications and configs grouped by vendor for maintenance planning
SELECT
    equipment_vendor,
    classification,
    COUNT(*) AS doc_count,
    SUM(file_size) AS total_size_bytes,
    MAX(modified_at) AS latest_update
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification IN ('network_config', 'technical_spec', 'capacity_plan')
  AND equipment_vendor IS NOT NULL
GROUP BY equipment_vendor, classification
ORDER BY equipment_vendor, doc_count DESC;

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

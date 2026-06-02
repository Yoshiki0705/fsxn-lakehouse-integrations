-- =============================================================================
-- Defense & Satellite — Named Queries
-- Industry: defense-satellite
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: optical_imagery, sar_imagery, multispectral,
--   change_detection, object_detection, terrain_model
-- =============================================================================

-- Name: Imagery by Geographic Area and Date
-- Description: Find satellite imagery for a specific area of interest and time range
SELECT
    file_id,
    file_name,
    geographic_area,
    acquisition_date,
    sensor_type,
    cloud_cover_pct,
    ground_resolution_m,
    classification_level,
    file_size
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND geographic_area IS NOT NULL
  AND acquisition_date IS NOT NULL
ORDER BY geographic_area, acquisition_date DESC;

-- Name: Low Cloud Cover Imagery
-- Description: Find imagery with minimal cloud cover for analysis suitability
SELECT
    file_id,
    file_name,
    geographic_area,
    acquisition_date,
    sensor_type,
    cloud_cover_pct,
    ground_resolution_m,
    classification,
    file_size
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification IN ('optical_imagery', 'multispectral')
  AND cloud_cover_pct <= 10.0
ORDER BY cloud_cover_pct ASC, ground_resolution_m ASC;

-- Name: Change Detection Candidates
-- Description: Find imagery pairs suitable for temporal change detection analysis
SELECT
    geographic_area,
    sensor_type,
    COUNT(*) AS image_count,
    MIN(acquisition_date) AS earliest_capture,
    MAX(acquisition_date) AS latest_capture,
    AVG(cloud_cover_pct) AS avg_cloud_cover,
    MIN(ground_resolution_m) AS best_resolution
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification IN ('optical_imagery', 'sar_imagery', 'multispectral')
  AND cloud_cover_pct <= 20.0
GROUP BY geographic_area, sensor_type
HAVING COUNT(*) >= 2
ORDER BY image_count DESC;

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

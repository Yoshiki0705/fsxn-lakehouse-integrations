-- =============================================================================
-- Energy — Named Queries
-- Industry: energy
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: seismic_survey, well_log, pipeline_inspection,
--   scada_data, environmental_report, thermal_image
-- =============================================================================

-- Name: Surveys by Geographic Area
-- Description: Inventory of seismic survey data grouped by survey area
SELECT
    survey_area,
    processing_stage,
    COUNT(*) AS file_count,
    SUM(file_size) AS total_size_bytes,
    ROUND(SUM(file_size) / 1073741824.0, 2) AS total_size_gb,
    MAX(acquisition_date) AS latest_acquisition
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'seismic_survey'
  AND survey_area IS NOT NULL
GROUP BY survey_area, processing_stage
ORDER BY survey_area, processing_stage;

-- Name: Well Logs by Depth Range
-- Description: Find well log data filtered by well and depth range
SELECT
    file_id,
    file_name,
    well_id,
    depth_range,
    processing_stage,
    acquisition_date,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'well_log'
  AND well_id IS NOT NULL
ORDER BY well_id, depth_range, acquisition_date DESC;

-- Name: Overdue Pipeline Inspection Reports
-- Description: Find pipeline inspection reports older than 12 months requiring re-inspection
SELECT
    file_id,
    file_name,
    survey_area,
    acquisition_date,
    processing_stage,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'pipeline_inspection'
  AND CAST(acquisition_date AS date) < CURRENT_DATE - INTERVAL '365' DAY
ORDER BY acquisition_date ASC;

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

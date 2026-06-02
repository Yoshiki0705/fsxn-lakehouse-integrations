-- =============================================================================
-- Autonomous Driving — Named Queries
-- Industry: autonomous-driving
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: camera_frame, lidar_pointcloud, radar_data,
--   gps_trajectory, can_bus_log, annotation_file
-- =============================================================================

-- Name: Scenes by Type and Weather Condition
-- Description: Find driving data filtered by scene type and weather for training sets
SELECT
    scene_type,
    weather,
    time_of_day,
    classification,
    COUNT(*) AS file_count,
    SUM(file_size) AS total_size_bytes,
    ROUND(SUM(file_size) / 1073741824.0, 2) AS total_size_gb
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND scene_type IS NOT NULL
  AND weather IS NOT NULL
GROUP BY scene_type, weather, time_of_day, classification
ORDER BY scene_type, weather, file_count DESC;

-- Name: Unannotated Data Backlog
-- Description: Find raw sensor data that has not yet been annotated
SELECT
    file_id,
    file_name,
    sensor_type,
    scene_type,
    weather,
    vehicle_id,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND annotation_status = 'raw'
  AND classification IN ('camera_frame', 'lidar_pointcloud', 'radar_data')
ORDER BY modified_at ASC;

-- Name: Sensor Coverage Summary
-- Description: Analyze sensor type distribution across vehicles and scenes
SELECT
    vehicle_id,
    sensor_type,
    scene_type,
    COUNT(*) AS capture_count,
    SUM(file_size) AS total_size_bytes,
    MIN(modified_at) AS first_capture,
    MAX(modified_at) AS last_capture
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND sensor_type IS NOT NULL
  AND vehicle_id IS NOT NULL
GROUP BY vehicle_id, sensor_type, scene_type
ORDER BY vehicle_id, sensor_type;

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

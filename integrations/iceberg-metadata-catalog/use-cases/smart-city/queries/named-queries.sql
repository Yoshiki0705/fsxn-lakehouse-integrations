-- =============================================================================
-- Smart City — Named Queries
-- Industry: smart-city
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: zoning_map, utility_network, elevation_model,
--   land_use, disaster_risk, traffic_flow
-- =============================================================================

-- Name: GIS Layers by District
-- Description: Inventory of GIS data layers grouped by city district
SELECT
    district,
    data_layer,
    classification,
    coordinate_system,
    COUNT(*) AS layer_count,
    SUM(file_size) AS total_size_bytes,
    MAX(last_updated) AS latest_update
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND district IS NOT NULL
  AND data_layer IS NOT NULL
GROUP BY district, data_layer, classification, coordinate_system
ORDER BY district, data_layer;

-- Name: Disaster Risk Areas
-- Description: Find disaster risk assessment data for emergency planning
SELECT
    file_id,
    file_name,
    district,
    data_layer,
    spatial_resolution,
    last_updated,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'disaster_risk'
ORDER BY district, last_updated DESC;

-- Name: Outdated Maps
-- Description: Find GIS data that has not been updated in over 12 months
SELECT
    file_id,
    file_name,
    district,
    data_layer,
    classification,
    last_updated,
    spatial_resolution,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification IN ('zoning_map', 'utility_network', 'land_use', 'elevation_model')
  AND CAST(last_updated AS date) < CURRENT_DATE - INTERVAL '365' DAY
ORDER BY last_updated ASC;

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

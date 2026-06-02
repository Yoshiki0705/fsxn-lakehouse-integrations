-- =============================================================================
-- Media & VFX — Named Queries
-- Industry: media-vfx
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: raw_footage, edited_video, vfx_composite,
--   color_grade, audio_mix, storyboard, subtitle
-- =============================================================================

-- Name: Assets by Project and Scene
-- Description: Find media assets organized by production project and scene
SELECT
    project_name,
    scene,
    take,
    file_id,
    file_name,
    classification,
    resolution,
    color_space,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND project_name IS NOT NULL
  AND scene IS NOT NULL
ORDER BY project_name, scene, take, modified_at DESC;

-- Name: Raw Footage Storage Summary
-- Description: Calculate total raw footage storage by project for capacity planning
SELECT
    project_name,
    resolution,
    COUNT(*) AS file_count,
    SUM(file_size) AS total_size_bytes,
    ROUND(SUM(file_size) / 1073741824.0, 2) AS total_size_gb,
    MAX(modified_at) AS latest_ingest
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'raw_footage'
GROUP BY project_name, resolution
ORDER BY total_size_bytes DESC;

-- Name: License Expiring Assets
-- Description: Find assets with rights-managed licenses approaching expiration
SELECT
    file_id,
    file_name,
    project_name,
    license_type,
    classification,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND license_type = 'rights_managed'
ORDER BY modified_at ASC;

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

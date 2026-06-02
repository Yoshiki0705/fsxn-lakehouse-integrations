-- =============================================================================
-- Gaming — Named Queries
-- Industry: gaming
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: 3d_model, texture, animation, audio_clip,
--   shader, level_design, ui_element
-- =============================================================================

-- Name: Assets by Target Platform
-- Description: Inventory of game assets grouped by target platform
SELECT
    target_platform,
    classification,
    asset_type,
    COUNT(*) AS asset_count,
    SUM(file_size) AS total_size_bytes,
    ROUND(SUM(file_size) / 1073741824.0, 2) AS total_size_gb,
    MAX(modified_at) AS latest_update
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND target_platform IS NOT NULL
GROUP BY target_platform, classification, asset_type
ORDER BY target_platform, total_size_bytes DESC;

-- Name: Large Textures Requiring Optimization
-- Description: Find oversized texture files that may need LOD optimization
SELECT
    file_id,
    file_name,
    asset_type,
    target_platform,
    texture_resolution,
    lod_level,
    file_size,
    build_version,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'texture'
  AND file_size > 10485760  -- > 10 MB
ORDER BY file_size DESC;

-- Name: Build Artifacts by Version
-- Description: Track game build artifacts across versions for release management
SELECT
    build_version,
    target_platform,
    classification,
    COUNT(*) AS file_count,
    SUM(file_size) AS total_size_bytes,
    MIN(modified_at) AS build_start,
    MAX(modified_at) AS build_end
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND build_version IS NOT NULL
GROUP BY build_version, target_platform, classification
ORDER BY build_version DESC, target_platform;

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

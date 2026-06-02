-- =============================================================================
-- Retail — Named Queries
-- Industry: retail
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: product_photo, lifestyle_image, design_file,
--   brand_asset, user_generated_content
-- =============================================================================

-- Name: Products Missing Images
-- Description: Find products with SKUs that lack associated product photos
SELECT
    product_id,
    sku,
    category,
    brand,
    season,
    COUNT(CASE WHEN classification = 'product_photo' THEN 1 END) AS photo_count,
    COUNT(*) AS total_assets
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND product_id IS NOT NULL
GROUP BY product_id, sku, category, brand, season
HAVING COUNT(CASE WHEN classification = 'product_photo' THEN 1 END) = 0
ORDER BY season DESC, category;

-- Name: Assets by Season
-- Description: Inventory of retail assets grouped by retail season
SELECT
    season,
    classification,
    COUNT(*) AS asset_count,
    SUM(file_size) AS total_size_bytes,
    COUNT(DISTINCT product_id) AS unique_products,
    MAX(modified_at) AS latest_upload
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND season IS NOT NULL
GROUP BY season, classification
ORDER BY season DESC, asset_count DESC;

-- Name: Brand Assets by Category
-- Description: Find brand assets organized by product category for marketing
SELECT
    brand,
    category,
    file_id,
    file_name,
    classification,
    color,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'brand_asset'
  AND brand IS NOT NULL
ORDER BY brand, category, modified_at DESC;

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

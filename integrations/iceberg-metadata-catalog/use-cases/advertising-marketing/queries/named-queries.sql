-- =============================================================================
-- Advertising & Marketing — Named Queries
-- Industry: advertising-marketing
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: hero_image, banner, video_ad, brand_guideline,
--   creative_brief, campaign_report
-- =============================================================================

-- Name: Expired Rights Tracking
-- Description: Find creative assets with expired or soon-to-expire usage rights
SELECT
    file_name,
    campaign_id,
    brand,
    channel,
    asset_type,
    rights_expiry,
    CASE
        WHEN rights_expiry < CURRENT_DATE THEN 'EXPIRED'
        WHEN rights_expiry < CURRENT_DATE + INTERVAL '30' DAY THEN 'EXPIRING_SOON'
        ELSE 'VALID'
    END AS rights_status
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND rights_expiry IS NOT NULL
  AND rights_expiry <= CURRENT_DATE + INTERVAL '30' DAY
ORDER BY rights_expiry ASC;

-- Name: Assets by Campaign and Channel
-- Description: Inventory of creative assets grouped by campaign and distribution channel
SELECT
    campaign_id,
    channel,
    classification,
    COUNT(*) AS asset_count,
    SUM(file_size) AS total_size_bytes,
    COUNT(CASE WHEN approval_status = 'approved' THEN 1 END) AS approved_count,
    COUNT(CASE WHEN approval_status = 'pending' THEN 1 END) AS pending_count
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND campaign_id IS NOT NULL
GROUP BY campaign_id, channel, classification
ORDER BY campaign_id, channel;

-- Name: Brand Consistency Check
-- Description: Find campaigns that have creative assets but no associated brand guidelines
SELECT
    campaign_id,
    brand,
    COUNT(*) AS creative_assets,
    COUNT(CASE WHEN classification = 'brand_guideline' THEN 1 END) AS guideline_count
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND campaign_id IS NOT NULL
GROUP BY campaign_id, brand
HAVING COUNT(CASE WHEN classification = 'brand_guideline' THEN 1 END) = 0
ORDER BY creative_assets DESC;

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

-- =============================================================================
-- latest_records.sql — Curated latest-record view
-- =============================================================================
-- Iceberg does not enforce primary-key uniqueness. This view deduplicates
-- append-only records and returns only the latest version of each file.
-- Consumers should query this view instead of the base table.
-- =============================================================================

CREATE OR REPLACE VIEW metadata.latest_unstructured_files AS
WITH ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY file_id
      ORDER BY modified_at DESC, enriched_at DESC
    ) AS rn
  FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
)
SELECT *
FROM ranked
WHERE rn = 1
  AND is_deleted = false;

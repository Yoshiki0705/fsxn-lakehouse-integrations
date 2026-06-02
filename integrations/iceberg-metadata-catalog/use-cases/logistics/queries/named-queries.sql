-- =============================================================================
-- Logistics — Named Queries
-- Industry: logistics
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: bill_of_lading, customs_declaration, delivery_proof,
--   packing_list, invoice, tracking_update
-- =============================================================================

-- Name: Shipments by Origin Country
-- Description: Inventory of shipping documents grouped by country of origin
SELECT
    origin_country,
    destination_country,
    classification,
    COUNT(*) AS document_count,
    COUNT(DISTINCT shipment_id) AS unique_shipments,
    MAX(modified_at) AS latest_document
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND origin_country IS NOT NULL
GROUP BY origin_country, destination_country, classification
ORDER BY origin_country, document_count DESC;

-- Name: Customs Documents Pending
-- Description: Find customs declarations that may need processing attention
SELECT
    file_id,
    file_name,
    shipment_id,
    origin_country,
    destination_country,
    carrier,
    enrichment_status,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'customs_declaration'
  AND enrichment_status = 'pending'
ORDER BY modified_at ASC;

-- Name: Delivery Proofs by Date
-- Description: Find proof of delivery documents within a date range
SELECT
    file_id,
    file_name,
    shipment_id,
    carrier,
    origin_country,
    destination_country,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'delivery_proof'
ORDER BY modified_at DESC;

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

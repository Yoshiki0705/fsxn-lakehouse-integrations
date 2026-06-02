-- =============================================================================
-- Legal — Named Queries
-- Industry: legal
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: nda, service_agreement, employment_contract,
--   lease, litigation_document, privilege_log, regulatory_response
-- =============================================================================

-- Name: Contracts by Counterparty
-- Description: List all contracts grouped by counterparty for relationship management
SELECT
    counterparty,
    file_id,
    file_name,
    contract_type,
    matter_id,
    jurisdiction,
    expiration_date,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification IN ('nda', 'service_agreement', 'employment_contract', 'lease')
  AND counterparty IS NOT NULL
ORDER BY counterparty, expiration_date ASC;

-- Name: Expiring Contracts
-- Description: Find contracts expiring within the next 90 days for renewal action
SELECT
    file_id,
    file_name,
    counterparty,
    contract_type,
    expiration_date,
    jurisdiction,
    matter_id
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND expiration_date IS NOT NULL
  AND CAST(expiration_date AS date) BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '90' DAY
ORDER BY expiration_date ASC;

-- Name: Privileged Documents
-- Description: Identify attorney-client privileged documents for litigation hold
SELECT
    file_id,
    file_name,
    matter_id,
    privilege_status,
    counterparty,
    sensitivity_level,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND privilege_status IN ('privileged', 'work_product')
ORDER BY matter_id, modified_at DESC;

-- Name: Documents by Matter
-- Description: Retrieve all documents associated with a specific legal matter
SELECT
    matter_id,
    file_id,
    file_name,
    classification,
    contract_type,
    counterparty,
    privilege_status,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND matter_id IS NOT NULL
ORDER BY matter_id, classification, modified_at DESC;

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

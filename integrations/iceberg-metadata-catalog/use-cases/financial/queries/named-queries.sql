-- =============================================================================
-- Financial Services — Named Queries
-- Industry: financial
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: invoice, contract, audit_report, kyc_document,
--   regulatory_filing, board_minutes, tax_filing
-- =============================================================================

-- Name: Contracts Expiring Within 90 Days
-- Description: Find financial contracts approaching expiration for renewal review
SELECT
    file_id,
    file_name,
    client_name,
    contract_type,
    regulatory_body,
    retention_years,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'contract'
  AND CAST(modified_at AS date) >= CURRENT_DATE - INTERVAL '90' DAY
ORDER BY modified_at ASC;

-- Name: KYC Documents by Client
-- Description: Retrieve all KYC documents grouped by client for compliance review
SELECT
    client_name,
    file_id,
    file_name,
    document_category,
    confidence_score,
    sensitivity_level,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'kyc_document'
  AND confidence_score >= 0.8
ORDER BY client_name, modified_at DESC;

-- Name: Audit Reports by Year
-- Description: List audit reports organized by fiscal year for internal review
SELECT
    file_id,
    file_name,
    client_name,
    regulatory_body,
    YEAR(modified_at) AS report_year,
    file_size,
    confidence_score
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'audit_report'
ORDER BY report_year DESC, modified_at DESC;

-- Name: Regulatory Filings by Body
-- Description: Inventory of regulatory filings grouped by governing authority
SELECT
    regulatory_body,
    COUNT(*) AS filing_count,
    SUM(file_size) AS total_size_bytes,
    MAX(modified_at) AS latest_filing,
    MIN(modified_at) AS earliest_filing
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'regulatory_filing'
GROUP BY regulatory_body
ORDER BY filing_count DESC;

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

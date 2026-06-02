-- =============================================================================
-- SAP ERP — Named Queries
-- Industry: sap-erp
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: sap_invoice, delivery_note, material_document,
--   purchase_order, production_order, idoc_message
-- =============================================================================

-- Name: Documents by Transaction Code
-- Description: Inventory of SAP documents grouped by transaction code
SELECT
    transaction_code,
    classification,
    company_code,
    COUNT(*) AS document_count,
    SUM(file_size) AS total_size_bytes,
    MAX(modified_at) AS latest_document
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND transaction_code IS NOT NULL
GROUP BY transaction_code, classification, company_code
ORDER BY transaction_code, document_count DESC;

-- Name: Invoices by Fiscal Year
-- Description: Find SAP invoices organized by fiscal year for audit
SELECT
    fiscal_year,
    company_code,
    file_id,
    file_name,
    sap_document_number,
    document_type_sap,
    transaction_code,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'sap_invoice'
  AND fiscal_year IS NOT NULL
ORDER BY fiscal_year DESC, company_code, modified_at DESC;

-- Name: Archive Search by Document Number
-- Description: Search archived SAP documents by document number or type
SELECT
    file_id,
    file_name,
    sap_document_number,
    document_type_sap,
    transaction_code,
    company_code,
    fiscal_year,
    classification,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND sap_document_number IS NOT NULL
ORDER BY fiscal_year DESC, sap_document_number;

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

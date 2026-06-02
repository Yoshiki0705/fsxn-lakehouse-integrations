-- =============================================================================
-- Insurance — Named Queries
-- Industry: insurance
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: vehicle_damage, property_damage, medical_report,
--   policy_document, claim_form, surveillance_video
-- =============================================================================

-- Name: Claims by Severity
-- Description: Find claim documents ranked by damage severity score
SELECT
    file_id,
    file_name,
    claim_id,
    policy_number,
    damage_type,
    severity_score,
    classification,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND claim_id IS NOT NULL
  AND severity_score IS NOT NULL
ORDER BY severity_score DESC, modified_at DESC;

-- Name: High Fraud Risk Claims
-- Description: Identify claims flagged with high fraud risk for investigation
SELECT
    file_id,
    file_name,
    claim_id,
    policy_number,
    damage_type,
    fraud_risk_score,
    severity_score,
    classification,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND fraud_risk_score >= 0.7
ORDER BY fraud_risk_score DESC, modified_at DESC;

-- Name: Policy Documents Expiring
-- Description: Find policy documents approaching renewal date
SELECT
    file_id,
    file_name,
    policy_number,
    classification,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification = 'policy_document'
  AND policy_number IS NOT NULL
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

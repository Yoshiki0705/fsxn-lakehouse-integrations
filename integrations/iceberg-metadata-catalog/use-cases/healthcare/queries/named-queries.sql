-- =============================================================================
-- Healthcare — Named Queries
-- Industry: healthcare
-- Table: s3tablescatalog/fsxn-metadata-catalog."metadata"."unstructured_files"
-- Classification categories: mri_scan, ct_scan, pathology_slide,
--   clinical_protocol, consent_form, lab_report, surgical_video
-- =============================================================================

-- Name: DICOM Images by Modality and Body Part
-- Description: Find medical imaging files filtered by modality and anatomical region
SELECT
    file_id,
    file_name,
    modality,
    body_part,
    study_id,
    patient_id_hash,
    anonymization_status,
    file_size,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND classification IN ('mri_scan', 'ct_scan')
  AND modality IS NOT NULL
  AND body_part IS NOT NULL
ORDER BY modality, body_part, modified_at DESC;

-- Name: Files Containing PHI
-- Description: Identify files flagged as containing Protected Health Information
SELECT
    file_id,
    file_name,
    file_path,
    classification,
    sensitivity_level,
    has_pii,
    pii_status,
    anonymization_status,
    modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND has_pii = true
  AND pii_status != 'redacted'
ORDER BY sensitivity_level DESC, modified_at DESC;

-- Name: Studies by IRB Approval Status
-- Description: Group clinical study files by Institutional Review Board status
SELECT
    irb_status,
    study_id,
    COUNT(*) AS file_count,
    SUM(file_size) AS total_size_bytes,
    MAX(modified_at) AS latest_update
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
  AND study_id IS NOT NULL
GROUP BY irb_status, study_id
ORDER BY irb_status, file_count DESC;

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

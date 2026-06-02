# Healthcare — Iceberg Metadata Catalog

🌐 [日本語](README-ja.md) | English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Clinical trial document retrieval is manual | Delays in regulatory submissions | SQL search across all study documents < 2 sec |
| DICOM images searchable only by study ID | Missed research opportunities | AI classification by modality, body part, finding |
| Unknown PHI/PII in research data | HIPAA / 個人情報保護法 violation risk | Automatic PHI detection + de-identification |

## Key File Types

`.dcm` (DICOM), `.pdf` (clinical docs, protocols), `.hl7`, `.fhir.json`, `.csv` (lab results), `.tiff` (pathology)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `study_id` — Clinical trial or research study identifier
- `modality` — MRI, CT, X-ray, Ultrasound, Pathology
- `body_part` — Anatomical region
- `patient_hash` — De-identified patient reference
- `irb_approved` — Whether access requires IRB approval
- `phi_detected` — Boolean flag for PHI presence

## Quick Start

```bash
# Generate healthcare sample data
python use-cases/_shared/sample-data/generate.py --industry healthcare --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry healthcare

# Or use the main demo with healthcare profile
./demo/scripts/run-demo.sh --profile healthcare
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find DICOM images by modality without PHI exposure
SELECT file_id, file_name, study_id, modality, body_part
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'dicom_image'
  AND modality = 'MRI'
  AND phi_detected = false
ORDER BY modified_at DESC;
```

## Compliance

| Regulation | How addressed |
|-----------|---------------|
| HIPAA Privacy Rule | PHI detection + de-identification + Lake Formation access control |
| 3省2ガイドライン | Encryption + access control + audit trail |
| GxP (FDA 21 CFR Part 11) | Immutable audit trail via Iceberg snapshots |

## Related

- [Industry Use Cases — Healthcare](../../docs/industry-use-cases.md#healthcare--life-sciences)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC5](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC5-healthcare-dicom)

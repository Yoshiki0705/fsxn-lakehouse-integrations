# Anonymization Pipeline (Phase 6)

🌐 [日本語](README-ja.md) | English

## Overview

Processes files flagged with `has_pii=true` by the AI enrichment pipeline (Phase 3) and creates anonymized versions. Implements the **Data Clean Room** pattern: original files remain restricted, anonymized versions are accessible to broader audiences.

## Architecture

```
S3 Tables (has_pii=true, anonymization_status='pending')
  → EventBridge Schedule (hourly)
    → Step Functions: AnonymizationWorkflow
      → DetermineFileType
        → Document: anonymize-document Lambda (PII redaction)
        → Image: anonymize-image Lambda (face blur via Rekognition)
        → DICOM: anonymize-dicom Lambda (Safe Harbor de-id)
      → Write anonymized file to S3 output bucket
      → Update metadata: anonymized_path, anonymization_status='completed'
      → Update "clean" metadata table (broader access)
```

## Lambda Functions

| Function | Input | Processing | Output |
|----------|-------|-----------|--------|
| `anonymize-document` | Text/PDF from FSx for ONTAP S3 AP | Regex + Comprehend PII redaction | Redacted text to S3 |
| `anonymize-image` | Image from FSx for ONTAP S3 AP | Rekognition face detection + Pillow blur | Blurred image to S3 |

## Data Clean Room Pattern

```
┌─────────────────────────────────────────────────────────┐
│ Original Metadata Table (RESTRICTED)                     │
│   - All files, including PII-containing                  │
│   - Access: METADATA_ADMIN_ROLE, COMPLIANCE_ROLE only    │
│   - file_path points to FSx for ONTAP (original)        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ Clean Metadata Table (BROAD ACCESS)                      │
│   - Only files with anonymization_status='completed'     │
│     OR has_pii=false                                     │
│   - Access: All authorized analysts                      │
│   - file_path points to anonymized S3 copy               │
│   - Lake Formation: LF-Tag sensitivity != 'restricted'   │
└─────────────────────────────────────────────────────────┘
```

## Quality Assurance

| Stage | Automation | Human Review |
|-------|-----------|-------------|
| PII Detection | Comprehend + Bedrock (95-98% accuracy) | — |
| Anonymization | Regex + Comprehend redaction / Rekognition blur | — |
| Validation | Automated re-scan of anonymized file | Weekly 5% sample |
| Escalation | If miss rate > 2% → pipeline pause | Compliance team review |

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OUTPUT_BUCKET` | (required) | S3 bucket for anonymized files |
| `OUTPUT_PREFIX` | `anonymized/` | S3 prefix for output |
| `BLUR_FACTOR` | 30 | Gaussian blur radius for face anonymization |
| `LANGUAGE_CODE` | `en` | Comprehend language for PII detection |

## Cost Estimate (1000 PII files/month)

| Component | Monthly Cost |
|-----------|-------------|
| Comprehend PII detection | ~$5 (already in Phase 3) |
| Rekognition face detection | ~$10 (1000 images × $0.01) |
| Lambda compute | ~$5 |
| S3 storage (anonymized copies) | ~$2 |
| **Total** | **~$22/month** |

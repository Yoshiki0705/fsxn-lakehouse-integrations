# Public Sector — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| FOIA/information disclosure takes weeks | Citizen trust erosion, legal risk | Instant document discovery + PII auto-redaction |
| Unknown PII across file shares | Compliance violations | Automatic PII detection (EN + JA, 14 types) |
| Document retention tracked manually | Accidental deletion or over-retention | Retention metadata + lifecycle enforcement |

## Key File Types

`.pdf` (administrative docs), `.docx` (reports, memos), `.xlsx` (data tables), `.msg`/`.eml` (correspondence), `.tiff` (scanned records)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `disclosure_status` — public / restricted / classified
- `retention_period` — Required retention in years
- `pii_types_detected` — Array of PII categories found
- `department` — Originating government department
- `request_id` — FOIA/disclosure request reference
- `redaction_applied` — Whether auto-redaction was performed

## Quick Start

```bash
# Generate public sector sample data
python use-cases/_shared/sample-data/generate.py --industry public-sector --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry public-sector

# Or use the main demo with public-sector profile
./demo/scripts/run-demo.sh --profile public-sector
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- FOIA request: find disclosable documents without PII
SELECT file_id, file_name, department, disclosure_status, modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification LIKE '%infrastructure%'
  AND disclosure_status = 'public'
  AND has_pii = false
ORDER BY modified_at DESC;
```

## Compliance

| Regulation | How addressed |
|-----------|---------------|
| Freedom of Information Act / 情報公開法 | Instant discovery + PII auto-redaction |
| Personal Information Protection Act / 個人情報保護法 | PII detection (14 types) + anonymization |
| Administrative Document Management Guidelines | Classification + retention + audit trail |

## Related

- [Industry Use Cases — Public Sector](../../docs/industry-use-cases.md#public-sector)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC16](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC16-government-foia)

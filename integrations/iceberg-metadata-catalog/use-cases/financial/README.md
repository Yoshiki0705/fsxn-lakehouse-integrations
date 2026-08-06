# Financial Services — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Regulatory document retrieval takes days | Fines, audit findings | SQL search < 2 sec with full audit trail |
| KYC/AML documents scattered across systems | Compliance gaps, regulatory risk | AI classification + PII detection + access control |
| Contract clause search requires manual review | Missed obligations, legal exposure | Automated classification with confidence scoring |

## Key File Types

`.pdf` (contracts, audit reports, KYC), `.docx`, `.xlsx` (regulatory filings), `.msg`/`.eml` (correspondence)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `client_name` — Client or counterparty name
- `contract_type` — Loan, derivative, deposit, etc.
- `regulatory_body` — SEC, FSA, FCA, etc.
- `retention_years` — Required retention period
- `document_category` — kyc / audit / contract / regulatory / tax

## Quick Start

```bash
# Generate financial sample data
python use-cases/_shared/sample-data/generate.py --industry financial --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry financial

# Or use the main demo with financial profile
./demo/scripts/run-demo.sh --profile financial
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Contracts expiring within 90 days
SELECT file_id, file_name, client_name, contract_type, modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'contract'
  AND CAST(modified_at AS date) >= CURRENT_DATE - INTERVAL '90' DAY
ORDER BY modified_at ASC;
```

## Compliance

| Regulation | How addressed |
|-----------|---------------|
| FSA / 金融庁 inspection | Instant retrieval + immutable audit trail |
| FISC Security Guidelines | Encryption at rest + access control + audit logging |
| AML/KYC retention (7 years) | Iceberg time travel + retention metadata |
| SOX compliance | CloudTrail + Iceberg snapshots for immutable records |

## Related

- [Industry Use Cases — Financial Services](../../docs/industry-use-cases.md#financial-services)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC2](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC2-financial-idp)

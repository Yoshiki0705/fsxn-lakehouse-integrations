# Legal / Compliance — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Contract review across matters is manual | Missed deadlines, renewal surprises | AI classification + expiration tracking |
| Privilege log creation takes weeks | Discovery cost overruns | Automated privilege detection + log generation |
| Obligation tracking scattered in emails | Compliance failures | Clause extraction + obligation metadata |

## Key File Types

`.pdf`, `.docx` (contracts, briefs), `.msg`/`.eml` (emails), `.xlsx` (privilege logs, trackers)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `contract_type` — NDA, MSA, SLA, employment, lease
- `counterparty` — Other party to the agreement
- `matter_id` — Legal matter or case reference
- `expiration_date` — Contract expiration date
- `has_auto_renewal` — Boolean for auto-renewal clause
- `privilege_status` — attorney-client / work-product / none

## Quick Start

```bash
# Generate legal sample data
python use-cases/_shared/sample-data/generate.py --industry legal --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry legal

# Or use the main demo with legal profile
./demo/scripts/run-demo.sh --profile legal
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Contracts expiring this year with auto-renewal
SELECT file_name, contract_type, counterparty, expiration_date
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'service_agreement'
  AND expiration_date < '2026-12-31'
  AND has_auto_renewal = true
ORDER BY expiration_date ASC;
```

## Related

- [Industry Use Cases — Legal](../../docs/industry-use-cases.md#legal--compliance-law-firms)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC1](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC1-legal-compliance)

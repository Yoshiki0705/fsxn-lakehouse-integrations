# Telecommunications — Iceberg Metadata Catalog

🌐 [日本語](README-ja.md) | English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Network config docs scattered across teams | Outage resolution delays, knowledge silos | Centralized zero-copy storage with SQL search |
| Tower inspection photos untagged and unsearchable | Missed maintenance, compliance gaps | AI classification + inspection metadata |
| Customer contract archive search takes hours | SLA breaches, regulatory risk | Instant retrieval with contract metadata |

## Key File Types

`.pdf` (contracts, compliance filings), `.docx`, `.xlsx` (capacity plans), `.png`, `.jpg` (tower inspection photos), config files (`.cfg`, `.xml`)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `tower_id` — Cell tower or site identifier
- `region_code` — Network region code
- `document_type` — Document category (config, contract, inspection, compliance)
- `equipment_vendor` — Equipment manufacturer (Ericsson, Nokia, etc.)
- `frequency_band` — Spectrum band (700MHz, 3.5GHz, mmWave, etc.)
- `inspection_result` — Inspection outcome (pass, fail, requires_followup)

## Quick Start

```bash
# Generate telecom sample data
python use-cases/_shared/sample-data/generate.py --industry telecom --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry telecom

# Or use the main demo with telecom profile
./demo/scripts/run-demo.sh --profile telecom
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Tower inspection photos with failed status
SELECT file_name, tower_id, region_code, inspection_result, equipment_vendor, modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'tower_inspection'
  AND inspection_result = 'fail'
ORDER BY modified_at DESC;
```

## Limitations

- This solution provides metadata cataloging for zero-copy storage; it does not replace network management systems (NMS)
- Inspection result classification is AI-assisted — final pass/fail decisions require qualified engineer review
- Telecommunications regulatory compliance (FCC, 総務省) requires separate audit trail systems

## Related

- [Industry Use Cases — Telecommunications](../../docs/industry-use-cases.md)
- [Demo Scenario](../../demo/scenarios/industry-telecom.md)
- [Base Schema](../_shared/base-schema.yaml)

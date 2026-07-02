# Manufacturing — Iceberg Metadata Catalog

🌐 [日本語](README-ja.md) | English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Finding design documents takes hours | Missed deadlines, duplicated work | SQL search in < 2 seconds |
| ISO audit preparation takes weeks | Audit findings risk | Instant document retrieval with audit trail |
| No traceability from part to QC report | Recall risk | file_id → part_number → inspection_lot linkage |
| Unknown duplicate files | Wasted storage, version confusion | Content hash + similarity search |

## Solution Architecture

```
FSx for ONTAP (CAD, QC reports, maintenance logs)
       │
       │ S3 Access Point (read-only)
       ▼
┌─────────────────────────────────────────┐
│  AI Classification (Bedrock)            │
│  • "engineering_drawing" (0.95)         │
│  • "quality_report" (0.92)             │
│  • "maintenance_record" (0.88)         │
└──────────────────┬──────────────────────┘
                   ▼
┌─────────────────────────────────────────┐
│  S3 Tables (Iceberg) — Extended Schema  │
│  Base fields + part_number, revision,   │
│  plant, machine_id, inspection_lot      │
└──────────────────┬──────────────────────┘
                   ▼
         Athena: "Find all QC reports for
                  part P-2000 from last 6 months"
         → 1.8 seconds
```

## Quick Start

```bash
# 1. Generate sample manufacturing data
python sample-data/generate.py --count 100 --output /tmp/mfg-demo

# 2. Run demo (requires FSx for ONTAP S3 AP)
./demo/run-demo.sh --ap-alias <your-alias>

# 3. Or use the main demo with manufacturing data
cd ../../demo/scripts
./run-demo.sh --ap-alias <alias> --industry manufacturing
```

## Schema Extension

See [schema-extension.yaml](schema-extension.yaml) for manufacturing-specific fields:
- `part_number`, `revision`, `plant`, `machine_id`
- `inspection_lot`, `production_order`
- `document_category` (engineering / quality / maintenance / safety / compliance)

## Demo Talking Points

See [demo/talking-points.md](demo/talking-points.md)

## Athena Queries

See [queries/named-queries.sql](queries/named-queries.sql) for:
- Find drawings by part number
- QC reports with temperature deviation
- Files modified since last audit
- Duplicate detection (same content hash)

## Compliance

| Standard | Coverage |
|----------|----------|
| ISO 9001 §7.5 | Document control via metadata + time travel |
| ISO 9001 §8.5.2 | Traceability via part_number linkage |
| IATF 16949 | Automotive quality record classification |

## Related

- [Industry Use Cases Overview](../../docs/industry-use-cases.md#manufacturing)
- [Base Schema](_shared/base-schema.yaml)
- [Manufacturing Schema Extension](../../schema/extensions/manufacturing_metadata.yaml)
- [Serverless Patterns: UC3](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/manufacturing-analytics)

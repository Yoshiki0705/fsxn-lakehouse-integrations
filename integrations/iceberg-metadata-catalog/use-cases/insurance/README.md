# Insurance — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Claims photo assessment is manual | Slow settlement, adjuster bottleneck | AI damage severity scoring + classification |
| Fraud detection across claims is reactive | Losses from duplicate/staged claims | Duplicate image detection + cross-claim analysis |
| Policy document search for underwriting | Slow quoting, missed exclusions | AI clause extraction + classification |

## Key File Types

`.jpg` (damage photos), `.pdf` (policies, claims forms), `.xlsx` (actuarial data), `.mp4` (surveillance), `.docx` (reports)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `claim_id` — Insurance claim reference number
- `policy_number` — Associated policy number
- `damage_severity` — AI-scored severity (0.0–1.0)
- `fraud_risk_score` — AI-scored fraud probability (0.0–1.0)
- `incident_type` — vehicle, property, health, liability
- `adjuster_assigned` — Whether claim has assigned adjuster

## Quick Start

```bash
# Generate insurance sample data
python use-cases/_shared/sample-data/generate.py --industry insurance --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry insurance

# Or use the main demo with insurance profile
./demo/scripts/run-demo.sh --profile insurance
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find high-severity vehicle damage claims for priority review
SELECT file_name, claim_id, damage_severity, fraud_risk_score, incident_type
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'vehicle_damage'
  AND damage_severity >= 0.7
  AND fraud_risk_score < 0.3
ORDER BY damage_severity DESC;
```

## Compliance

| Regulation | How addressed |
|-----------|---------------|
| Insurance Business Act / 保険業法 | Document retention + audit trail |
| PII in claims (personal injury) | PHI/PII detection + access control |

## Related

- [Industry Use Cases — Insurance](../../docs/industry-use-cases.md#insurance)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC14](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC14-insurance)

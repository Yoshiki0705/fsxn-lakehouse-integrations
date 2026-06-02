# Energy / Seismic — Iceberg Metadata Catalog

🌐 [日本語](README-ja.md) | English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Seismic survey discovery across decades of data | Weeks to locate relevant surveys | SQL search by area, vintage, processing stage |
| Well log cross-referencing is manual | Missed correlations, exploration delays | Automated metadata extraction + linking |
| Environmental compliance docs hard to find | Regulatory fines, permit delays | AI classification + retention tracking |

## Key File Types

`.segy` (SEG-Y seismic), `.las` (well logs), `.csv` (SCADA), `.pdf` (inspection reports), `.tiff` (thermal imaging)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `survey_area` — Geographic block or survey area name
- `acquisition_date` — Date of data acquisition
- `processing_stage` — raw / processed / migrated / interpreted
- `well_id` — Well identifier for log data
- `sensor_type` — Seismic source type or sensor
- `regulatory_permit` — Associated permit number

## Quick Start

```bash
# Generate energy sample data
python use-cases/_shared/sample-data/generate.py --industry energy --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry energy

# Or use the main demo with energy profile
./demo/scripts/run-demo.sh --profile energy
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find processed seismic surveys for a specific block
SELECT file_name, survey_area, acquisition_date, processing_stage
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'seismic_survey'
  AND survey_area = 'Block-A'
  AND processing_stage = 'migrated'
ORDER BY acquisition_date DESC;
```

## Related

- [Industry Use Cases — Energy](../../docs/industry-use-cases.md#energy--seismic)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC8](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC8-energy-seismic)

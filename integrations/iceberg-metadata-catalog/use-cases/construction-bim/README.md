# Construction / BIM — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| BIM model version tracking across phases | Wrong revision used on-site | Version lineage + project phase metadata |
| Drawing specification extraction is manual | Missed requirements, rework | OCR + AI classification of drawings |
| As-built vs design comparison undocumented | Compliance gaps, disputes | Metadata linking design ↔ as-built files |

## Key File Types

`.ifc` (IFC/BIM), `.rvt` (Revit), `.dwg` (AutoCAD), `.pdf` (drawings, specs), `.jpg`/`.png` (site photos)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `project` — Construction project name
- `project_phase` — design, construction, handover, operation
- `discipline` — structural, mechanical, electrical, architectural
- `revision` — Drawing or model revision number
- `building_code` — Applicable building code reference
- `inspection_status` — passed / failed / pending

## Quick Start

```bash
# Generate construction/BIM sample data
python use-cases/_shared/sample-data/generate.py --industry construction-bim --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry construction-bim

# Or use the main demo with construction-bim profile
./demo/scripts/run-demo.sh --profile construction-bim
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find latest structural drawings for a project
SELECT file_name, project_phase, discipline, revision, modified_at
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'structural_drawing'
  AND project = 'Tower-A'
  AND discipline = 'structural'
ORDER BY revision DESC;
```

## Related

- [Industry Use Cases — Construction / BIM](../../docs/industry-use-cases.md#construction--bim)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC10](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC10-construction-bim)

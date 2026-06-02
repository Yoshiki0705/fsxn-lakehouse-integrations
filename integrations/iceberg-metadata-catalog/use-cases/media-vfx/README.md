# Media & VFX — Iceberg Metadata Catalog

🌐 [日本語](README-ja.md) | English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Finding specific footage across TB of media | Hours of manual browsing | AI scene classification + similarity search |
| Asset version tracking across projects | Wrong version used in final cut | Project → scene → take → version lineage |
| License/rights tracking for stock assets | Legal exposure from expired licenses | Rights metadata + expiration alerts |

## Key File Types

`.mov`, `.exr`, `.dpx`, `.wav`, `.psd`, `.raw`, `.srt`, `.mp4`, `.aaf`

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `project` — Production or project name
- `scene` — Scene identifier
- `take` — Take number
- `resolution` — Frame resolution (e.g., 4K, 8K)
- `color_space` — ACES, Rec.709, DCI-P3
- `duration_seconds` — Clip duration
- `rights_holder` — License owner

## Quick Start

```bash
# Generate media/VFX sample data
python use-cases/_shared/sample-data/generate.py --industry media-vfx --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry media-vfx

# Or use the main demo with media-vfx profile
./demo/scripts/run-demo.sh --profile media-vfx
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find raw footage for a project, sorted by size
SELECT file_name, classification, project, scene, file_size
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'raw_footage'
  AND project = 'Tokyo_Nights'
ORDER BY file_size DESC;
```

## Related

- [Industry Use Cases — Media & VFX](../../docs/industry-use-cases.md#media--vfx)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC4](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC4-media-vfx)

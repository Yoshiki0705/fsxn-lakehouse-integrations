# Gaming / Build Pipeline — Iceberg Metadata Catalog

🌐 [日本語](README-ja.md) | English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Game asset discovery across TB of content | Artists re-create existing assets | AI classification + similarity search |
| Build artifact tracking across platforms | Wrong assets in release builds | Platform + version metadata per artifact |
| Localization completeness unknown | Missed markets, launch delays | Completeness tracking by locale + asset type |

## Key File Types

`.fbx`, `.png`/`.dds` (textures), `.wav`/`.ogg` (audio), `.unity`/`.uasset`, `.zip` (builds), `.json` (configs)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `asset_type` — texture, model, animation, audio, shader, ui
- `target_platform` — pc, ps5, xbox, switch, mobile
- `build_version` — Build or release version string
- `lod_level` — Level of detail (0 = highest)
- `locale` — Localization language code
- `bundle_name` — Asset bundle or package name

## Quick Start

```bash
# Generate gaming sample data
python use-cases/_shared/sample-data/generate.py --industry gaming --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry gaming

# Or use the main demo with gaming profile
./demo/scripts/run-demo.sh --profile gaming
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find oversized textures that may need optimization
SELECT file_name, asset_type, target_platform, build_version, file_size
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE asset_type = 'texture'
  AND file_size > 10000000
  AND target_platform = 'mobile'
ORDER BY file_size DESC;
```

## Related

- [Industry Use Cases — Gaming](../../docs/industry-use-cases.md#gaming--build-pipeline)
- [Base Schema](../_shared/base-schema.yaml)

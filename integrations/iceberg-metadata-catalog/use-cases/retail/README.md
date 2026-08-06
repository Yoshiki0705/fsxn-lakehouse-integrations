# Retail / E-Commerce — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Product images lack consistent tagging | Poor search, missed cross-sell | AI auto-tagging (color, category, style, season) |
| Catalog completeness unknown | Lost revenue from missing assets | Completeness tracking queries |
| Brand asset license tracking is manual | Legal exposure from expired licenses | Rights metadata + expiration monitoring |

## Key File Types

`.jpg`, `.png`, `.tiff` (product photos), `.psd`, `.ai` (design files), `.mp4` (product videos)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `product_category` — Apparel, electronics, home, beauty, etc.
- `color` — Dominant color detected by AI
- `season` — Collection season (e.g., 2026-SS, 2026-AW)
- `sku` — Product SKU reference
- `has_model` — Whether image includes a human model
- `channel` — web, mobile, print, social

## Quick Start

```bash
# Generate retail sample data
python use-cases/_shared/sample-data/generate.py --industry retail --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry retail

# Or use the main demo with retail profile
./demo/scripts/run-demo.sh --profile retail
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find product photos for upcoming season catalog
SELECT file_name, product_category, color, season, has_model
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'product_photo'
  AND season = '2026-SS'
  AND channel = 'web'
ORDER BY product_category, color;
```

## Related

- [Industry Use Cases — Retail](../../docs/industry-use-cases.md#retail--e-commerce)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC11](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC11-retail-ecommerce)

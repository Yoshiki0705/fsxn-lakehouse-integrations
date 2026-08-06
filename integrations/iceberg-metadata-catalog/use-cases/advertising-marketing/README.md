# Advertising & Marketing — Iceberg Metadata Catalog

🌐 [日本語](README-ja.md) | English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Creative asset tracking across campaigns is fragmented | Missed deadlines, duplicate work | AI classification + campaign metadata linking |
| Campaign compliance verification is manual | Brand risk, regulatory fines | Automated approval status + rights expiry tracking |
| Brand consistency hard to enforce across channels | Diluted brand identity | Cross-channel asset search with brand guidelines linking |

## Key File Types

`.ai`, `.psd`, `.png`, `.jpg` (creative assets), `.mp4` (video ads), `.pdf` (brand guidelines, creative briefs)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `campaign_id` — Campaign identifier
- `brand` — Brand or sub-brand name
- `channel` — Distribution channel (web, social, print, tv)
- `asset_type` — Creative type (hero, banner, thumbnail, video)
- `rights_expiry` — License/rights expiration date
- `approval_status` — Workflow status (draft, pending, approved, rejected)

## Quick Start

```bash
# Generate advertising sample data
python use-cases/_shared/sample-data/generate.py --industry advertising-marketing --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry advertising-marketing

# Or use the main demo with advertising profile
./demo/scripts/run-demo.sh --profile advertising-marketing
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Creative assets by campaign pending approval
SELECT file_name, campaign_id, brand, channel, asset_type, approval_status
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification IN ('hero_image', 'banner', 'video_ad')
  AND approval_status = 'pending'
  AND campaign_id IS NOT NULL
ORDER BY campaign_id, channel;
```

## Limitations

- This solution provides metadata cataloging only; it does not enforce ad platform compliance (GDPR consent, COPPA)
- Rights expiry tracking is informational — integrate with your legal/procurement workflow for enforcement
- Industry-specific advertising regulations (FTC disclosure, ASA rules) require separate compliance validation

## Related

- [Industry Use Cases — Advertising & Marketing](../../docs/industry-use-cases.md)
- [Demo Scenario](../../demo/scenarios/industry-advertising-marketing.md)
- [Base Schema](../_shared/base-schema.yaml)

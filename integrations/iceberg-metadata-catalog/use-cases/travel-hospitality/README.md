# Travel & Hospitality — Iceberg Metadata Catalog

🌐 [日本語](README-ja.md) | English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Property photos unorganized across seasons/rooms | Poor OTA listings, lost bookings | AI classification + property/season metadata |
| Guest documents scattered with no retention policy | Privacy violations, GDPR risk | Document type tagging + retention tracking |
| Maintenance log search requires manual dig | Delayed repairs, guest complaints | Instant search by property, status, priority |

## Key File Types

`.jpg`, `.png` (property photos, room images), `.pdf` (contracts, guest agreements), `.docx` (maintenance logs, inspection reports)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `property_id` — Property or hotel identifier
- `room_category` — Room type (standard, deluxe, suite, penthouse)
- `document_type` — Document category (booking, contract, inspection, marketing)
- `season` — Travel season (peak, off, shoulder)
- `compliance_status` — Regulatory status (compliant, review_needed, expired)

## Quick Start

```bash
# Generate travel-hospitality sample data
python use-cases/_shared/sample-data/generate.py --industry travel-hospitality --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry travel-hospitality

# Or use the main demo with travel-hospitality profile
./demo/scripts/run-demo.sh --profile travel-hospitality
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Marketing photos by property and season
SELECT file_name, property_id, room_category, season, compliance_status
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'property_photo'
  AND document_type = 'marketing'
  AND season = 'peak'
ORDER BY property_id, room_category;
```

## Limitations

- This solution provides metadata cataloging for zero-copy storage; it does not replace property management systems (PMS)
- Guest document handling is metadata-only — data residency and GDPR/APPI deletion requests require integration with your privacy workflow
- Hospitality-specific regulatory compliance (旅館業法, fire safety codes) requires separate inspection systems

## Related

- [Industry Use Cases — Travel & Hospitality](../../docs/industry-use-cases.md)
- [Demo Scenario](../../demo/scenarios/industry-travel-hospitality.md)
- [Base Schema](../_shared/base-schema.yaml)

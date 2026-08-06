# Logistics / Supply Chain — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Shipping document search across carriers | Hours per customs inquiry | OCR + AI classification of BOL, invoices, customs |
| Delivery proof photos unorganized | Dispute resolution delays | Auto-indexed by shipment ID + timestamp |
| Cross-border compliance docs scattered | Customs holds, fines | Document type classification + origin tracking |

## Key File Types

`.pdf` (BOL, invoices, customs), `.jpg` (delivery proof), `.csv` (tracking data), `.xlsx` (manifests), `.xml` (EDI)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `shipment_id` — Shipment or tracking identifier
- `document_type` — bol, invoice, customs_declaration, packing_list
- `origin_country` — Country of origin (ISO 3166)
- `destination_country` — Destination country
- `carrier` — Shipping carrier name
- `customs_status` — cleared / pending / held

## Quick Start

```bash
# Generate logistics sample data
python use-cases/_shared/sample-data/generate.py --industry logistics --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry logistics

# Or use the main demo with logistics profile
./demo/scripts/run-demo.sh --profile logistics
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find customs declarations from China pending clearance
SELECT file_name, document_type, shipment_id, origin_country, customs_status
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'customs_declaration'
  AND origin_country = 'CN'
  AND customs_status = 'pending'
ORDER BY modified_at ASC;
```

## Related

- [Industry Use Cases — Logistics](../../docs/industry-use-cases.md#logistics--supply-chain)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC12](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC12-logistics-supply-chain)

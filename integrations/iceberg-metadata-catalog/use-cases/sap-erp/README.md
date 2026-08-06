# SAP / ERP Adjacent — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| SAP spool output discovery for audits | Days of manual search | AI classification + SAP document number linking |
| Archive file retrieval (IDoc, BAPI logs) | Slow incident resolution | Indexed by document type + creation date |
| Retention policy enforcement is manual | Over-retention costs, compliance risk | Retention metadata + lifecycle automation |

## Key File Types

`.pdf` (spool output, invoices), `.xml` (IDoc), `.csv` (exports), `.xlsx` (reports), `.txt` (BAPI logs)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `sap_document_number` — SAP document reference
- `sap_module` — FI, CO, MM, SD, PP, HR
- `document_type` — invoice, delivery_note, purchase_order, report
- `company_code` — SAP company code
- `fiscal_year` — SAP fiscal year
- `archiving_status` — active / archived / pending_deletion

## Quick Start

```bash
# Generate SAP/ERP sample data
python use-cases/_shared/sample-data/generate.py --industry sap-erp --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry sap-erp

# Or use the main demo with sap-erp profile
./demo/scripts/run-demo.sh --profile sap-erp
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find SAP invoices created this fiscal year
SELECT file_name, sap_document_number, document_type, sap_module, creation_date
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'sap_invoice'
  AND fiscal_year = '2026'
  AND company_code = '1000'
ORDER BY creation_date DESC;
```

## Related

- [Industry Use Cases — SAP / ERP](../../docs/industry-use-cases.md#sap--erp-adjacent)
- [Base Schema](../_shared/base-schema.yaml)

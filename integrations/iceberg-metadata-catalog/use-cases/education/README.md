# Education / Research — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Research datasets siloed across departments | Duplicate effort, missed collaborations | Cross-department dataset discovery via SQL |
| Open access compliance tracking is manual | Funder mandate violations | Publication status + access metadata |
| Thesis/paper version management ad-hoc | Wrong version submitted | Version tracking + classification by stage |

## Key File Types

`.pdf` (papers, theses), `.docx` (manuscripts), `.csv`/`.parquet` (datasets), `.ipynb` (notebooks), `.zip` (supplementary)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `research_field` — Academic discipline or field
- `publication_year` — Year of publication
- `open_access_status` — gold, green, closed, embargo
- `funding_source` — Grant or funding body
- `doi` — Digital Object Identifier (if published)
- `dataset_format` — csv, parquet, hdf5, netcdf

## Quick Start

```bash
# Generate education sample data
python use-cases/_shared/sample-data/generate.py --industry education --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry education

# Or use the main demo with education profile
./demo/scripts/run-demo.sh --profile education
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find open access genomics papers for literature review
SELECT file_name, research_field, publication_year, open_access_status, doi
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'journal_paper'
  AND research_field = 'genomics'
  AND open_access_status IN ('gold', 'green')
ORDER BY publication_year DESC;
```

## Related

- [Industry Use Cases — Education](../../docs/industry-use-cases.md#education--research)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC13](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC13-education-research)

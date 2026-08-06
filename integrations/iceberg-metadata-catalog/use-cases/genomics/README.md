# Genomics — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Finding samples across studies for meta-analysis | Weeks of manual inventory | SQL search by study, sample type, platform |
| Quality metrics scattered in run logs | Bad data enters pipelines | Automated QC extraction + quality scoring |
| Data sharing compliance is manual | Consent violations, collaboration delays | Consent status + de-identification metadata |

## Key File Types

`.fastq`, `.vcf`, `.bam`, `.cram`, `.bed`, `.gtf`, `.fasta`

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `study_id` — Research study or project identifier
- `sample_type` — whole_genome, exome, rna_seq, chip_seq
- `sequencing_platform` — Illumina, PacBio, ONT
- `read_depth` — Average sequencing depth
- `quality_score` — Phred quality score
- `consent_status` — broad / restricted / withdrawn

## Quick Start

```bash
# Generate genomics sample data
python use-cases/_shared/sample-data/generate.py --industry genomics --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry genomics

# Or use the main demo with genomics profile
./demo/scripts/run-demo.sh --profile genomics
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find high-quality whole genome samples for meta-analysis
SELECT file_name, study_id, sample_type, sequencing_platform, quality_score
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'whole_genome'
  AND quality_score > 30
  AND consent_status = 'broad'
ORDER BY quality_score DESC;
```

## Related

- [Industry Use Cases — Genomics](../../docs/industry-use-cases.md#genomics--life-sciences-research)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC7](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC7-genomics)

# Life Sciences Research — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Clinical trial document retrieval across studies | Regulatory submission delays | SQL search by study, phase, document type |
| Lab instrument output scattered across shares | Reproducibility challenges | Automated classification + instrument metadata |
| Data sharing for collaboration requires manual de-ID | Weeks of delay per request | PHI detection + de-identification metadata |

## Key File Types

`.pdf` (protocols, reports), `.csv`/`.xlsx` (lab results), `.raw`/`.mzML` (mass spec), `.fcs` (flow cytometry), `.nd2` (microscopy)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `study_id` — Clinical trial or research study identifier
- `study_phase` — Phase I, II, III, IV, preclinical
- `compound_id` — Drug compound or molecule identifier
- `instrument` — Lab instrument name/model
- `assay_type` — ELISA, PCR, mass_spec, flow_cytometry
- `gxp_compliant` — Whether data was generated under GxP

## Quick Start

```bash
# Generate life sciences sample data
python use-cases/_shared/sample-data/generate.py --industry life-sciences --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry life-sciences

# Or use the main demo with life-sciences profile
./demo/scripts/run-demo.sh --profile life-sciences
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find Phase III study documents for regulatory submission
SELECT file_name, study_id, study_phase, compound_id, classification
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE study_phase = 'Phase III'
  AND gxp_compliant = true
  AND classification IN ('protocol', 'clinical_study_report', 'statistical_analysis')
ORDER BY study_id, modified_at DESC;
```

## Compliance

| Regulation | How addressed |
|-----------|---------------|
| GxP (FDA 21 CFR Part 11) | Immutable audit trail + electronic record integrity |
| ICH E6 (GCP) | Document traceability + version control via Iceberg |

## Related

- [Industry Use Cases — Life Sciences](../../docs/industry-use-cases.md#healthcare--life-sciences)
- [Base Schema](../_shared/base-schema.yaml)

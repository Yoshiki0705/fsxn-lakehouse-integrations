# Semiconductor / EDA — Iceberg Metadata Catalog

🌐 English

## Business Problem

| Pain point | Impact | This solution |
|-----------|--------|---------------|
| Finding design files across tape-out revisions | Weeks of manual search, re-work | AI classification + version lineage tracking |
| IP block reuse discovery is ad-hoc | Redundant design effort, license waste | Similarity search across design libraries |
| DRC report aggregation across projects | Missed violations, tape-out delays | Automated classification + cross-project queries |

## Key File Types

`.gds`, `.oasis`, `.lef`, `.def`, `.spice`, `.lib`, `.v` (Verilog), `.vhd` (VHDL)

## Schema Extension

📄 [schema-extension.yaml](schema-extension.yaml)

Additional fields:
- `technology_node` — Process node (e.g., 5nm, 7nm, 14nm)
- `design_stage` — RTL, synthesis, place_route, tape_out
- `ip_block_name` — Reusable IP block identifier
- `foundry` — Target foundry (TSMC, Samsung, Intel)
- `tape_out_date` — Scheduled or actual tape-out date
- `drc_status` — clean / violations_found / pending

## Quick Start

```bash
# Generate semiconductor sample data
python use-cases/_shared/sample-data/generate.py --industry semiconductor --count 200

# Run industry demo
./use-cases/_shared/demo/run-demo.sh --industry semiconductor

# Or use the main demo with semiconductor profile
./demo/scripts/run-demo.sh --profile semiconductor
```

## Sample Queries

📄 [queries/named-queries.sql](queries/named-queries.sql)

```sql
-- Find tape-out ready GDS files by technology node
SELECT file_name, technology_node, design_stage, foundry, tape_out_date
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE file_type = '.gds'
  AND classification = 'tape_out_ready'
  AND technology_node = '5nm'
ORDER BY tape_out_date DESC;
```

## Related

- [Industry Use Cases — Semiconductor](../../docs/industry-use-cases.md#semiconductor--eda)
- [Base Schema](../_shared/base-schema.yaml)
- [Serverless Patterns — UC6](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/UC6-semiconductor-eda)

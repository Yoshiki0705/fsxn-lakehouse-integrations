# Iceberg Metadata Adoption Validation Checklist

🌐 English | [日本語](iceberg-adoption-validation-checklist-ja.md)

## Purpose

- What business problem does Iceberg solve here? → Unstructured data discovery, governance, and AI-readiness without raw-file copy
- Why metadata-only rather than raw-file migration? → Raw files remain on FSx for ONTAP (NFS/SMB/S3 AP access preserved); only structured metadata is cataloged

## Scope

| Category | In scope | Out of scope |
|----------|----------|-------------|
| Raw data | FSx for ONTAP files (read via S3 AP) | Files are NOT migrated to S3 |
| Metadata | File inventory + AI enrichment in S3 Tables Iceberg | Raw file content storage |
| Consumers | Athena, EMR Spark, Snowflake, Databricks (via activation) | Direct file processing in Snowflake/Databricks |
| Out-of-scope paths | — | Iceberg write to FSx S3 AP, Databricks UC direct S3 Tables access |

## Validation Checklist

### Data Completeness
- [ ] Row count by scan_run_id matches expected file count
- [ ] Duplicate detection by file_id / path_hash (ratio < 2x)
- [ ] Latest-record view correctness (matches unique file count)
- [ ] Delete marker behavior (is_deleted files excluded from latest view)
- [ ] All target volumes/prefixes scanned

### Iceberg Behavior
- [ ] Snapshot / time-travel behavior verified
- [ ] S3 Tables auto-compaction observed
- [ ] Append-only write semantics understood
- [ ] Naming convention (lowercase) applied

### Cross-Platform Compatibility
- [ ] Athena query compatibility (SELECT, COUNT, time travel)
- [ ] EMR Spark compatibility (7.13.0+ required)
- [ ] Snowflake compatibility (VENDED_CREDENTIALS, AUTO_REFRESH, time travel)
- [ ] Databricks compatibility status documented (Foreign Iceberg GA revalidation)

### Cost
- [ ] Metadata storage cost (S3 Tables)
- [ ] Scan/enrichment compute cost (Lambda/ECS)
- [ ] AI enrichment cost (Bedrock)
- [ ] Query cost (Athena/Snowflake warehouse)
- [ ] Search index cost (OpenSearch)
- [ ] Backfill vs steady-state cost separated

### Consumer Activation
- [ ] Athena named queries created
- [ ] BI views (latest-record, PII coverage) published
- [ ] Snowflake activation (VENDED_CREDENTIALS or metadata sync)
- [ ] Databricks activation (metadata sync to UC Delta or Foreign Iceberg when available)

## References

- [Production Maturity Model](../genai/production-maturity-model.md)
- [PoC Results Summary](poc-results-summary.md)
- [Cost Assumptions](../verification-evidence/cost-assumptions.yaml)

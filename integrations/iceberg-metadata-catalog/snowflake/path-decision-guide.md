# Snowflake Integration Path Decision Guide

🌐 [日本語](path-decision-guide-ja.md) | English

## Purpose

Help Snowflake users and partners choose the right integration path for accessing FSx for ONTAP metadata catalog from Snowflake.

## Path Decision

| Requirement | Recommended path | Status |
|---|---|---|
| Snowflake dashboards only | Sync redacted metadata to Snowflake table | ✅ Available now |
| Cortex Search / Intelligence | Sync summary + redacted metadata | ✅ Available now |
| Zero-copy Iceberg query | Validate Glue REST + vended credentials | 🔄 In progress |
| Snowflake-first Iceberg governance | Open Catalog / Polaris | Strategic alternative |
| Raw file processing in Snowflake | External stage (FSx S3 AP) | ✅ Verified (TO_FILE limitation) |
| Cross-platform Iceberg interop | Glue REST + vended credentials | 🔄 In progress |

## Governance Policy Mapping

When metadata is synced to Snowflake, map AWS governance fields to Snowflake objects:

| AWS metadata field | Snowflake governance object | Purpose |
|---|---|---|
| `sensitivity_level` | Tag + Masking Policy | Control column visibility by sensitivity |
| `tenant_id` | Row Access Policy | Restrict rows by tenant |
| `has_pii` | Tag + Masking Policy | Mask PII-containing fields |
| `path_classification` | Row Access Policy or restricted view | Control path visibility |
| `raw_path` | Restricted table only (not synced to general view) | Prevent path exposure |

## Metadata Sync Pattern

### What to Sync

```sql
-- Sync curated latest-record view, not append-only base table
-- From AWS side (PyIceberg or Athena export):
SELECT file_id, file_name, file_type, classification, confidence_score,
       summary, sensitivity_level, tenant_id, has_pii, pii_status,
       path_classification, scan_run_id, change_type, is_deleted,
       created_at, modified_at
FROM latest_records_view
WHERE is_deleted = false;
-- Do NOT sync: raw_path, embedding_vector, anonymized_path (unless needed)
```

### Sync Frequency

| Pattern | Frequency | Best for |
|---|---|---|
| Scheduled task | Hourly / daily | Low-frequency dashboards |
| Event-driven (SNS → Snowpipe) | Near real-time | Active discovery use cases |
| Manual refresh | On-demand | Development / testing |

### Idempotency

Use `MERGE INTO` with `file_id` as the merge key to handle re-syncs without duplicates:

```sql
MERGE INTO metadata_catalog t
USING staged_metadata s
ON t.file_id = s.file_id
WHEN MATCHED AND s.modified_at > t.modified_at THEN UPDATE SET ...
WHEN NOT MATCHED THEN INSERT ...;
```

## Snowflake Cost Model

| Component | Driver | Estimate |
|---|---|---|
| Warehouse compute (sync job) | X-SMALL, hourly | ~$2-5/month |
| Warehouse compute (dashboards) | X-SMALL, on-demand | ~$5-15/month |
| Cortex Search service | Per-query + index refresh | ~$10-30/month |
| Storage (synced metadata) | ~1 GB for 100K files | ~$0.02/month |
| Tasks / Streams | Execution frequency | ~$1-3/month |
| **Total (metadata activation)** | | **~$20-55/month** |

> Raw file copy is NOT required. Only curated metadata (~MB scale) is synced.

## References

- [Snowflake: Cortex Search overview](https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)
- [Snowflake: Iceberg REST catalog integration](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-rest)
- [Snowflake: Vended credentials](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-vended-credentials)
- [Snowflake: External stages](https://docs.snowflake.com/en/sql-reference/sql/create-stage)
- [Glue REST validation](glue-rest-vended-credentials-validation.md)
- [External Stage validation](external-stage-fsx-s3ap-validation.md)

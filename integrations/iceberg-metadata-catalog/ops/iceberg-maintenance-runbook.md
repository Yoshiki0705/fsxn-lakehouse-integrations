# Iceberg Table Maintenance Runbook

🌐 English | [日本語](iceberg-maintenance-runbook-ja.md)

## Purpose

Maintain the `metadata.unstructured_files` Iceberg table on S3 Tables for optimal query performance and storage efficiency.

## Recommended Maintenance Order

1. **Validate latest-record view** — Ensure `latest_unstructured_files` view returns correct deduplicated results
2. **Expire snapshots** — Remove snapshots older than retention policy (S3 Tables may auto-manage; verify)
3. **Remove orphan files** — Clean up data files not referenced by any snapshot (if supported by engine)
4. **Rewrite manifests** — If manifest count grows beyond ~100, rewrite for faster scan planning
5. **Re-run benchmark query** — Verify Athena query latency hasn't degraded
6. **Record evidence** — Log maintenance actions in `verification-evidence/`

## S3 Tables Managed Maintenance

S3 Tables provides service-managed compaction. Verify:
- Auto-compaction frequency and behavior
- Whether snapshot expiration is automatic or requires explicit configuration
- Orphan file cleanup responsibility (service vs user)

## Manual Maintenance (if needed)

```python
# Via PyIceberg (if S3 Tables exposes maintenance APIs)
from pyiceberg.catalog import load_catalog

catalog = load_catalog('glue_s3tables', **{...})
table = catalog.load_table('metadata.unstructured_files')

# Check current snapshots
for snapshot in table.metadata.snapshots:
    print(f"{snapshot.snapshot_id} | {snapshot.timestamp_ms}")
```

## Monitoring

| Metric | Check | Alert threshold |
|--------|-------|----------------|
| Snapshot count | `SELECT COUNT(*) FROM ...unstructured_files$history` | > 100 |
| Record count vs unique file_id count | Compare base table vs latest view | Ratio > 2x |
| Athena query latency (p95) | CloudWatch | > 5 seconds |
| Manifest file count | Iceberg metadata inspection | > 100 |

## Schedule

| Action | Frequency | Owner |
|--------|-----------|-------|
| Validate latest-record view | Daily (automated) | Platform team |
| Check snapshot count | Weekly | Platform team |
| Full maintenance cycle | Monthly | Platform team |
| Re-benchmark after maintenance | After each maintenance | Platform team |

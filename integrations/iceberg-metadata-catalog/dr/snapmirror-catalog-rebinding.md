# DR and Catalog Rebinding

🌐 [日本語](snapmirror-catalog-rebinding-ja.md) | English

## Problem

When DR failover occurs (SnapMirror), the metadata catalog contains references to the primary volume's S3 Access Point alias and volume ID. After failover, these references become stale.

## What Changes After Failover

| Item | Primary | DR Secondary |
|------|---------|-------------|
| Volume ID | Original | New (destination volume) |
| S3 Access Point alias | Primary AP alias | New AP alias (must be created on DR volume) |
| Junction path | May differ | Verify mount point |
| SVM | Primary SVM | DR SVM |

## Recommended Catalog Columns for DR

```yaml
columns:
  - source_volume_id        # Original volume where file was discovered
  - current_volume_id       # Active volume (updated after failover)
  - source_s3ap_alias       # Original S3 AP alias
  - current_s3ap_alias      # Active S3 AP alias (updated after failover)
  - catalog_environment     # primary / dr / test
```

## Failover Procedure

1. Activate SnapMirror destination volume
2. Create S3 Access Point on destination volume
3. Update `current_volume_id` and `current_s3ap_alias` in metadata table
4. Verify Athena queries resolve to new AP
5. Update Lambda environment variables (AP alias)
6. Validate AI enrichment pipeline connectivity

## FSx for ONTAP SnapMirror Notes

- Volume-level SnapMirror is supported
- SVM-DR is not supported on FSx for ONTAP
- Synchronous SnapMirror is not supported
- Minimum replication interval: 5 minutes
- RPO depends on replication schedule and change rate

## References

- [FSx for ONTAP Data Protection](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapmirror-ontap.html)

🌐 **English** | [日本語](../ja/datasync-to-s3-guide.md)

# AWS DataSync: FSx for ONTAP → S3 Sync Guide

> **Status**: Reference architecture — DataSync is the only validated sync mechanism from FSx for ONTAP to standard S3 buckets (SnapMirror S3 is [not available on FSx for ONTAP](../../verification-pack/snapmirror-s3/evidence/2026-05-26/evidence-record.yaml)).

## When You Need This

DataSync is the **bridge from enterprise file data to AI-ready data products** when the consuming platform requires standard S3 storage:

- Databricks Unity Catalog requires data in standard S3 buckets (FSx for ONTAP S3 AP not supported by UC)
- Delta Lake / Iceberg / Hudi table format writes require standard S3 (conditional writes not supported on FSx for ONTAP S3 AP)
- You need AUTO_REFRESH / Snowpipe (S3 Event Notifications not available on FSx for ONTAP S3 AP)
- You need a governed copy of FSx for ONTAP data in S3 for downstream AI/ML consumption

> **Design principle**: DataSync is not a "workaround" — it's a managed, incremental sync mechanism that turns NAS file data into platform-consumable datasets. The goal is not to copy everything, but to sync the **curated subset** that downstream platforms need for AI-ready data products.

## Architecture

```
FSx for ONTAP (NFS)
  ↓ DataSync Task (scheduled)
Amazon S3 bucket (standard)
  ↓
Analytics engines (Databricks UC, Delta Lake, Iceberg, etc.)
```

## Prerequisites

- FSx for ONTAP file system with NFS-accessible volumes
- Target S3 bucket in the same region
- IAM role for DataSync with permissions to read from FSx for ONTAP NFS and write to S3
- VPC with connectivity to FSx for ONTAP management/data LIFs

## Step-by-Step Setup

### Step 1: Create DataSync Source Location (FSx for ONTAP NFS)

```bash
aws datasync create-location-fsx-ontap \
  --storage-virtual-machine-arn arn:aws:fsx:ap-northeast-1:<ACCOUNT>:storage-virtual-machine/<SVM_ID> \
  --protocol NFS={} \
  --subdirectory /vol1/data/ \
  --security-group-arns arn:aws:ec2:ap-northeast-1:<ACCOUNT>:security-group/<SG_ID>
```

Reference: [Configuring transfers with FSx for ONTAP](https://docs.aws.amazon.com/datasync/latest/userguide/create-ontap-location.html)

### Step 2: Create DataSync Destination Location (S3)

```bash
aws datasync create-location-s3 \
  --s3-bucket-arn arn:aws:s3:::<BUCKET_NAME> \
  --s3-config BucketAccessRoleArn=arn:aws:iam::<ACCOUNT>:role/DataSyncS3Role \
  --subdirectory /fsxn-sync/
```

### Step 3: Create DataSync Task

```bash
aws datasync create-task \
  --source-location-arn <SOURCE_LOCATION_ARN> \
  --destination-location-arn <DESTINATION_LOCATION_ARN> \
  --name fsxn-to-s3-sync \
  --options '{
    "VerifyMode": "ONLY_FILES_TRANSFERRED",
    "OverwriteMode": "ALWAYS",
    "Atime": "BEST_EFFORT",
    "Mtime": "PRESERVE",
    "PreserveDeletedFiles": "REMOVE",
    "TransferMode": "CHANGED"
  }'
```

Key options:
- `TransferMode: CHANGED` — Only transfer files that have changed (incremental)
- `PreserveDeletedFiles: REMOVE` — Delete files in S3 that were deleted on FSx for ONTAP
- `Mtime: PRESERVE` — Preserve modification timestamps for change detection

### Step 4: Schedule the Task

```bash
aws datasync update-task \
  --task-arn <TASK_ARN> \
  --schedule ScheduleExpression="rate(5 minutes)"
```

Schedule options:
- `rate(5 minutes)` — Every 5 minutes (near real-time)
- `rate(1 hour)` — Hourly (batch)
- `cron(0 */6 * * ? *)` — Every 6 hours

### Step 5: Execute and Monitor

```bash
# Manual execution
aws datasync start-task-execution --task-arn <TASK_ARN>

# Check status
aws datasync describe-task-execution --task-execution-arn <EXECUTION_ARN>
```

## Cost Model

| Component | Cost | Notes |
|-----------|------|-------|
| DataSync transfer | $0.0125/GB (same region) | Only changed bytes transferred after first sync |
| S3 storage | $0.023/GB/month (Standard) | Destination storage |
| S3 requests | $0.005/1000 PUT | During sync |

**Example**: 1 TB initial sync + 10 GB/day incremental changes
- Initial: 1000 GB × $0.0125 = $12.50 (one-time)
- Daily incremental: 10 GB × $0.0125 = $0.125/day
- Monthly incremental: ~$3.75/month
- S3 storage: 1 TB × $0.023 = $23/month
- **Total monthly (after initial sync): ~$27/month for 1 TB**

## End-to-End Latency Model

| DataSync Schedule | Transfer Time (10 GB) | Auto Loader Detection | Total Lag |
|---|---|---|---|
| Every 5 minutes | ~1-2 min | 5 min poll | **~7-12 min** |
| Every 1 hour | ~1-2 min | 5 min poll | **~65 min** |
| Every 6 hours | ~1-2 min | 5 min poll | **~6 hours** |

> For near-real-time requirements (<1 min), use FPolicy → Lambda → S3 instead of DataSync.

## Best Practices

1. **Use `TransferMode: CHANGED`** — Avoids re-transferring unchanged files
2. **Set `PreserveDeletedFiles: REMOVE`** — Keeps S3 in sync with deletions on FSx for ONTAP
3. **Use Snapshot for consistency** — Schedule DataSync to run after a Snapshot is taken for point-in-time consistent transfers
4. **Filter with includes/excludes** — Only sync relevant prefixes (e.g., `/bronze/sensor-data/`)
5. **Monitor with CloudWatch** — Set alarms on `BytesTransferred`, `FilesTransferred`, `TaskExecutionStatus`
6. **Use S3 lifecycle rules** — Tier old synced data to S3-IA or Glacier after N days

## Integration with Databricks UC

After DataSync syncs data to S3:

```sql
-- Register S3 bucket as UC External Location
CREATE EXTERNAL LOCATION fsxn_synced
  URL 's3://<BUCKET>/fsxn-sync/'
  WITH (STORAGE CREDENTIAL <credential_name>);

-- Create UC Managed Table from synced data
CREATE TABLE catalog.schema.sensor_data
USING DELTA
AS SELECT * FROM parquet.`s3://<BUCKET>/fsxn-sync/sensor-data/`;
```

## Integration with Delta Lake / Iceberg

After DataSync syncs data to S3, table format writes work normally:

```python
# EMR Spark — write Delta table on synced S3 data
df = spark.read.parquet("s3://<BUCKET>/fsxn-sync/sensor-data/")
df.write.format("delta").mode("overwrite").save("s3://<BUCKET>/delta-tables/sensors/")
```

## Integration with Snowflake

DataSync → S3 also enables Snowflake patterns that require standard S3 buckets:

```sql
-- Option 1: Snowflake External Table on synced S3 bucket (zero-copy from S3)
CREATE OR REPLACE EXTERNAL TABLE sensor_data_ext
  WITH LOCATION = @s3_synced_stage/sensor-data/
  FILE_FORMAT = (TYPE = PARQUET)
  AUTO_REFRESH = TRUE;  -- S3 Event Notifications work on standard S3

-- Option 2: COPY INTO for full Snowflake features (Cortex Search, Time Travel, DML)
COPY INTO sensor_data
  FROM @s3_synced_stage/sensor-data/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;
```

**When to use DataSync → S3 → Snowflake vs FSx for ONTAP S3 AP → Snowflake directly:**

| Scenario | Recommended path | Reason |
|----------|-----------------|--------|
| Read-only analytics, Cortex AI text functions | FSx for ONTAP S3 AP → External Table (direct) | Zero-copy, no sync needed |
| AUTO_REFRESH / Snowpipe needed | DataSync → S3 → External Table | S3 Event Notifications required |
| Cortex Search / RAG | DataSync → S3 → COPY INTO → Cortex Search | Internal table required |
| Multimodal AI (vision) | DataSync → S3 → COPY FILES → internal stage | TO_FILE requires internal stage |

> **Key insight**: For most Snowflake analytics use cases, the **direct FSx for ONTAP S3 AP path** (with `AWS_ACCESS_POINT_ARN`) is sufficient and eliminates sync cost entirely. Use DataSync → S3 only when you need features that require S3 Event Notifications or internal tables.

## Why Not SnapMirror S3?

SnapMirror S3 (ONTAP S3 bucket → AWS S3 replication) is documented in NetApp ONTAP 9.10.1+ but is **not available on FSx for ONTAP** (verified May 2026):
- `snapmirror object-store` CLI commands: "not a recognized command"
- `/api/cloud/targets` REST API: "not authorized for that command"
- Feature request submitted to AWS

See: [SnapMirror S3 verification evidence](../../verification-pack/snapmirror-s3/evidence/2026-05-26/evidence-record.yaml)

## References

- [AWS DataSync + FSx for ONTAP](https://docs.aws.amazon.com/datasync/latest/userguide/create-ontap-location.html)
- [DataSync pricing](https://aws.amazon.com/datasync/pricing/)
- [DataSync task options](https://docs.aws.amazon.com/datasync/latest/userguide/API_Options.html)
- [FSx for ONTAP S3 Access Points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-access-points.html)

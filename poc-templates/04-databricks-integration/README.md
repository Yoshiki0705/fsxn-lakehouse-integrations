🌐 **English** | [日本語](README-ja.md)

# Module 04: Databricks Integration (DataSync → S3 → Unity Catalog)

## Overview

Databricks Unity Catalog cannot directly access FSx for ONTAP S3 Access Points (session policy limitation). The recommended production path is:

```
FSx for ONTAP (NFS) → DataSync → S3 bucket → Auto Loader → UC Managed Table
```

## Prerequisites

- FSx for ONTAP with NFS-accessible volume
- S3 bucket in same region (destination for DataSync)
- Databricks workspace with Unity Catalog enabled
- IAM role for DataSync (read FSx NFS, write S3)

## Steps

### 1. Create DataSync Task

```bash
# See datasync-task.yaml for CloudFormation template
aws cloudformation deploy \
  --template-file datasync-task.yaml \
  --stack-name fsxn-databricks-sync \
  --parameter-overrides \
    SvmArn=<SVM_ARN> \
    TargetBucket=<BUCKET_NAME> \
  --capabilities CAPABILITY_IAM
```

### 2. Create UC External Location + Table

```sql
-- See uc-setup.sql
CREATE EXTERNAL LOCATION fsxn_synced
  URL 's3://<BUCKET>/fsxn-sync/'
  WITH (STORAGE CREDENTIAL <credential_name>);

CREATE TABLE catalog.schema.sensor_data
USING DELTA
AS SELECT * FROM parquet.`s3://<BUCKET>/fsxn-sync/sensor-data/`;
```

### 3. Configure Auto Loader (Incremental)

For incremental ingestion of the synced S3 data, use Databricks Auto Loader
(`cloudFiles`) against the destination S3 prefix:

```python
(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "parquet")
    .option("cloudFiles.schemaLocation", "s3://<BUCKET>/_schema/sensor-data/")
    .load("s3://<BUCKET>/fsxn-sync/sensor-data/")
    .writeStream
    .option("checkpointLocation", "s3://<BUCKET>/_checkpoint/sensor-data/")
    .toTable("main.default.sensor_data"))
```

Auto Loader's file notification mode is not available here because FSx for ONTAP
S3 Access Points do not emit S3 Event Notifications. Run it against the standard S3
bucket that DataSync writes to, in directory listing mode.

## Cost

| Component | Estimate |
|-----------|----------|
| DataSync (1 TB initial) | ~$12.50 |
| DataSync (10 GB/day incremental) | ~$0.125/day |
| S3 storage (synced copy) | ~$23/TB/month |
| Databricks compute | Per DBU |

## Governance

After data is in UC:
- ✅ Table/Column Grants
- ✅ Row Filters + Column Masks
- ✅ Automatic Lineage
- ✅ Delta Sharing (open protocol)
- ✅ Mosaic AI (ML training, Feature Store)

🌐 **English** | [日本語](README-ja.md)

# Module 05: EMR Serverless Spark ETL (Read + Write-back)

## Overview

EMR Serverless Spark reads, transforms, and writes-back Parquet to FSx for ONTAP via S3 Access Points. No cluster management, no data copy for reads.

```
FSx for ONTAP ──S3 AP──▶ EMR Serverless Spark ──S3 AP──▶ FSx for ONTAP (gold/)
                         (read + transform + write)
```

## Prerequisites

- FSx for ONTAP with S3 Access Point (read-write file system user)
- S3 bucket for script storage (regular S3, not S3 AP)
- IAM execution role with S3 AP + S3 bucket permissions

## Quick Start

```bash
# 1. Upload PySpark script to S3
aws s3 cp spark-job.py s3://<SCRIPTS_BUCKET>/emr-scripts/

# 2. Create EMR Serverless application
aws emr-serverless create-application \
  --name "fsxn-poc-spark" \
  --release-label "emr-7.1.0" \
  --type "SPARK"

# 3. Submit job
aws emr-serverless start-job-run \
  --application-id <APP_ID> \
  --execution-role-arn <ROLE_ARN> \
  --job-driver '{
    "sparkSubmit": {
      "entryPoint": "s3://<SCRIPTS_BUCKET>/emr-scripts/spark-job.py",
      "sparkSubmitParameters": "--conf spark.hadoop.fs.s3.impl=com.amazon.ws.emr.hadoop.fs.EmrFileSystem"
    }
  }'
```

## Critical Notes

- **Use `s3://` (EMRFS)**, NOT `s3a://` — S3A cannot parse AP aliases
- **Parquet timestamps must be microsecond** — nanosecond (pandas default) causes Spark errors
- **Script must be on regular S3** — not on FSx for ONTAP S3 AP

## Benchmark

| Operation | Duration |
|-----------|----------|
| Read 10K rows | 6.78s |
| GROUP BY aggregation | 2.52s |
| Window function | 1.19s |
| Write-back to FSx for ONTAP | 3.61s |
| **Total Spark execution** | **16.35s** |
| Job total (with cold start) | 37s |
| **Cost per job** | **~$0.05** |

## Cost

- Zero idle cost (application stopped between jobs)
- ~$0.05/job (37s execution)
- 10 jobs/day = ~$15/month

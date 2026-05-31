# Iceberg Metadata Catalog for Unstructured Data

🌐 [日本語](README-ja.md) | English

## Overview

This module implements the **Iceberg Metadata Catalog** pattern — using Apache Iceberg tables (on Amazon S3 Tables) as a metadata catalog for unstructured data stored on FSx for ONTAP.

**Architecture**: See [docs/en/iceberg-metadata-catalog.md](../../docs/en/iceberg-metadata-catalog.md) for the full architecture document.

## Quick Start (1 week PoC)

### Prerequisites

- AWS CLI v2
- Python 3.12+
- FSx for ONTAP with S3 Access Point configured
- IAM permissions: `s3tables:*`, `s3:GetObject`, `s3:ListBucket` on AP ARN

### Step 1: Create S3 Tables Table Bucket

```bash
chmod +x scripts/create-table-bucket.sh
./scripts/create-table-bucket.sh create
```

### Step 2: Run Initial Metadata Scan

```bash
pip install boto3 pyarrow 'pyiceberg[s3tables]'

python scripts/initial-metadata-scan.py \
  --access-point-arn arn:aws:s3:ap-northeast-1:178625946981:accesspoint/your-ap-name \
  --table-bucket-arn arn:aws:s3tables:ap-northeast-1:178625946981:bucket/fsxn-metadata-catalog \
  --max-files 1000
```

### Step 3: Query with Athena

```sql
-- Find all PDF files created in 2025
SELECT file_name, file_path, file_size, created_at
FROM "metadata"."unstructured_files"
WHERE file_type = 'application/pdf'
  AND created_at >= TIMESTAMP '2025-01-01'
ORDER BY created_at DESC;

-- File type distribution
SELECT file_type, COUNT(*) as count, SUM(file_size) as total_bytes
FROM "metadata"."unstructured_files"
WHERE is_deleted = false
GROUP BY file_type
ORDER BY count DESC;

-- Files pending AI enrichment
SELECT COUNT(*) as pending_count
FROM "metadata"."unstructured_files"
WHERE enrichment_status = 'pending';
```

## Directory Structure

```
integrations/iceberg-metadata-catalog/
├── README.md                          # This file
├── README-ja.md                       # Japanese version
├── scripts/
│   ├── create-table-bucket.sh         # S3 Tables setup script
│   └── initial-metadata-scan.py       # Initial metadata population
├── lambda/                            # FPolicy → metadata sync
│   └── metadata-sync-handler/
│       ├── handler.py                 # Lambda handler (SQS → Iceberg)
│       ├── requirements.txt           # Python dependencies
│       └── build-layer.sh             # Lambda layer build script
├── cloudformation/
│   └── metadata-sync-pipeline.yaml    # SQS + Lambda + IAM + Alarms
├── step-functions/                    # (Phase 3) AI enrichment workflow
│   └── enrichment-workflow.asl.json
└── queries/                           # (Phase 5) Athena named queries
    └── common-searches.sql
```

## Phases

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 1** | ✅ Implemented | S3 Tables setup + initial scan script |
| **Phase 2** | ✅ Implemented | FPolicy → SQS → Lambda metadata sync |
| Phase 3 | 🔲 Planned | AI enrichment (Step Functions + Bedrock) |
| Phase 4 | 🔲 Planned | Cross-platform access (Databricks, Snowflake) |
| Phase 5 | 🔲 Planned | Search & discovery (SQL + vector) |
| Phase 6 | 🔲 Planned | Anonymization pipeline |

## Phase 2: FPolicy → Metadata Sync Pipeline

### Deploy

```bash
# 1. Build Lambda layer
cd lambda/metadata-sync-handler
./build-layer.sh
# Upload layer to S3 (for CloudFormation reference)
aws s3 cp pyiceberg-s3tables-layer.zip \
  s3://<ACCOUNT_ID>-lambda-layers-ap-northeast-1/pyiceberg-s3tables-layer.zip

# 2. Deploy CloudFormation stack
aws cloudformation deploy \
  --template-file cloudformation/metadata-sync-pipeline.yaml \
  --stack-name fsxn-metadata-sync-pipeline \
  --parameter-overrides \
    TableBucketArn=arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog \
    AccessPointArn=arn:aws:s3:ap-northeast-1:<ACCOUNT_ID>:accesspoint/your-ap-name \
  --capabilities CAPABILITY_NAMED_IAM

# 3. Configure FPolicy Server to send events to the SQS queue
# Get queue URL from stack outputs:
aws cloudformation describe-stacks \
  --stack-name fsxn-metadata-sync-pipeline \
  --query 'Stacks[0].Outputs[?OutputKey==`QueueUrl`].OutputValue' \
  --output text
```

### Test

```bash
# Send a test event to the SQS queue
aws sqs send-message \
  --queue-url <QUEUE_URL> \
  --message-body '{
    "event_type": "create",
    "file_path": "/vol1/test/sample.pdf",
    "file_size": 1024,
    "timestamp": "2026-06-01T10:00:00Z",
    "svm_name": "svm1",
    "volume_name": "vol1",
    "access_point_arn": "arn:aws:s3:ap-northeast-1:<ACCOUNT_ID>:accesspoint/your-ap-name"
  }'

# Verify record in Athena
# SELECT * FROM "metadata"."unstructured_files" WHERE file_name = 'sample.pdf';
```

### Monitor

- **DLQ Alarm**: Messages in DLQ indicate processing failures
- **Error Alarm**: >5 Lambda errors in 5 minutes
- **Stopped Alarm**: No invocations for 10+ minutes (FPolicy may be down)

## Related Documents

- [Architecture Document (EN)](../../docs/en/iceberg-metadata-catalog.md)
- [Architecture Document (JA)](../../docs/ja/iceberg-metadata-catalog.md)
- [Compatibility Matrix](../../docs/en/compatibility-matrix.md)
- [Spec: Requirements](../../.kiro/specs/iceberg-unstructured-metadata-catalog/requirements.md)
- [Spec: Tasks](../../.kiro/specs/iceberg-unstructured-metadata-catalog/tasks.md)

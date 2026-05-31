# Quick Start: S3-Only Mode (No FSx Required)

🌐 [日本語](quickstart-s3-only-ja.md) | English

## Overview

This guide lets you try the Iceberg Metadata Catalog **without FSx for ONTAP**. Instead of an S3 Access Point on FSx, you'll use a regular S3 bucket with sample files.

**What you'll experience**: The same metadata catalog, AI classification, vector search, and governance — just with S3 as the file source instead of FSx.

**Time**: ~10 minutes | **Cost**: < $0.10 | **Prerequisites**: AWS CLI + Python 3.12+

## Step 1: Create S3 Bucket with Sample Files

```bash
# Set variables
export BUCKET_NAME="iceberg-metadata-demo-$(aws sts get-caller-identity --query Account --output text)"
export REGION="ap-northeast-1"  # or your preferred region

# Create bucket
aws s3 mb s3://${BUCKET_NAME} --region ${REGION}

# Upload sample files (from this repo)
aws s3 cp integrations/iceberg-metadata-catalog/demo/sample-data/ \
  s3://${BUCKET_NAME}/demo-files/ --recursive

# Or create your own sample files:
echo "CONFIDENTIAL - Employee Record
Name: Jane Smith
Email: jane.smith@example.com
Phone: 555-0123
SSN: 123-45-6789" > /tmp/pii-sample.txt

aws s3 cp /tmp/pii-sample.txt s3://${BUCKET_NAME}/demo-files/documents/
```

## Step 2: Create S3 Tables Metadata Catalog

```bash
# Install dependencies
pip install -r requirements.txt

# Create the Iceberg table
python3 scripts/initial-metadata-scan.py \
  --access-point-arn ${BUCKET_NAME} \
  --table-bucket-arn arn:aws:s3tables:${REGION}:$(aws sts get-caller-identity --query Account --output text):bucket/fsxn-metadata-catalog \
  --max-files 100 \
  --region ${REGION}
```

> **Note**: The `--access-point-arn` parameter accepts both S3 AP aliases and regular bucket names. The script uses `s3.list_objects_v2(Bucket=...)` which works with both.

## Step 3: Run AI Enrichment

```bash
python3 demo/scripts/demo-enrich.py \
  --table-bucket-arn arn:aws:s3tables:${REGION}:$(aws sts get-caller-identity --query Account --output text):bucket/fsxn-metadata-catalog \
  --ap-alias ${BUCKET_NAME} \
  --region ${REGION} \
  --max-files 10
```

## Step 4: Query with Athena

```sql
-- Register Glue catalog first (one-time):
-- See demo-guide.md Step 2

SELECT file_name, classification, confidence_score
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE enrichment_status = 'completed'
ORDER BY confidence_score DESC;
```

## Step 5: Vector Search

```bash
python3 demo/scripts/demo-search.py \
  --query "find documents with personal information" \
  --region ${REGION}
```

## Step 6: PII Detection

```bash
python3 demo/scripts/demo-anonymize.py \
  --ap-alias ${BUCKET_NAME} \
  --region ${REGION} \
  --file-key demo-files/documents/pii-sample.txt
```

## Cleanup

```bash
# Delete S3 bucket contents and bucket
aws s3 rb s3://${BUCKET_NAME} --force

# Delete S3 Tables (if created)
aws s3tables delete-table \
  --table-bucket-arn arn:aws:s3tables:${REGION}:$(aws sts get-caller-identity --query Account --output text):bucket/fsxn-metadata-catalog \
  --namespace metadata --name unstructured_files --region ${REGION}
```

## What's Different from the Full Demo?

| Feature | S3-Only Mode | Full Mode (FSx for ONTAP) |
|---------|:---:|:---:|
| Metadata scan | ✅ | ✅ |
| AI classification | ✅ | ✅ |
| Vector search | ✅ | ✅ |
| PII detection | ✅ | ✅ |
| Athena queries | ✅ | ✅ |
| Lake Formation governance | ✅ | ✅ |
| **Zero-copy (no data movement)** | ❌ (data is in S3) | ✅ |
| **NFS/SMB access** | ❌ | ✅ |
| **Deduplication** | ❌ | ✅ (50-70% savings) |
| **FPolicy real-time sync** | ❌ | ✅ |
| **Snapshot/FlexClone** | ❌ | ✅ |

The key value of FSx for ONTAP is **zero-copy**: existing NFS/SMB files become AI-searchable without moving data. In S3-only mode, you still need to upload files to S3 first.

## Next Steps

- **Want the full experience?** Deploy FSx for ONTAP with S3 Access Points: [PoC Guide](../../docs/poc-guide.md)
- **Want to add your own files?** Just upload to the S3 bucket and re-run the scan
- **Want real-time sync?** FSx for ONTAP FPolicy detects file changes automatically

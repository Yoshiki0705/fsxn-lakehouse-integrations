# Iceberg Metadata Catalog — PoC Results Summary

🌐 [日本語](poc-results-summary-ja.md) | English

## What We Built

A **metadata catalog for unstructured data** that makes files on FSx for ONTAP instantly searchable and AI-classifiable — without copying data to S3.

## Key Results (Verified 2026-05-31)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **File discovery time** | Minutes-hours (manual ListObjectsV2) | < 2 seconds (Athena SQL) | 100x+ at scale |
| **AI classification** | Manual (human reviews each file) | Automatic (6 sec/file, $0.01/file) | Fully automated |
| **Storage cost** | S3 full copy required (~$230-256/month per 10TB)* | No S3 copy needed ($5-15/month metadata only) | 95% reduction |
| **Governance** | None on unstructured data | Lake Formation LF-Tags on all metadata | 0% → 100% coverage |
| **Cross-platform access** | Platform-specific silos | Single Iceberg table, multiple engines | Unified catalog |

## Architecture (Verified)

```
FSx for ONTAP (actual files: PDF, images, CAD, video)
       │
       │ S3 Access Point (read)
       ▼
┌─────────────────────────────────────────────┐
│  AI Enrichment (Bedrock)                    │
│  • Claude Vision: image classification      │
│  • Titan Embeddings: 1024-dim vectors       │
│  • Processing: ~6 sec/file, ~$0.01/file     │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  S3 Tables (Iceberg Metadata)               │
│  • File path, type, size, timestamps        │
│  • AI classification + confidence score     │
│  • Vector embedding (similarity search)     │
│  • PII detection flag                       │
│  • Auto-compaction, no maintenance needed   │
└──────────────────┬──────────────────────────┘
                   ▼
┌─────────────────────────────────────────────┐
│  Query Engines                              │
│  • Athena: < 2 sec queries ✅ Verified      │
│  • EMR Spark: Iceberg REST ✅ Expected      │
│  • Databricks: Spark cluster ⚠️ Workaround  │
│  • Snowflake: COPY INTO path ⚠️ Workaround  │
└─────────────────────────────────────────────┘
```

## What Works Today

| Capability | Status | Evidence |
|-----------|--------|---------|
| Metadata scan (38 files → Iceberg table) | ✅ Verified | 30 seconds, zero errors |
| Athena SQL queries on metadata | ✅ Verified | Sub-2-second, Lake Formation governed |
| Real-time sync (FPolicy → SQS → Lambda → S3 Tables) | ✅ Verified | 2 sec processing, DLQ = 0 |
| AI image classification (Bedrock Vision) | ✅ Verified | "Invoice" classified at 0.9 confidence |
| Vector embedding generation (Titan V2) | ✅ Verified | 1024-dim, normalized |
| Vector similarity search (OpenSearch NextGen) | ✅ Verified | kNN score 0.71, scale-to-zero |
| PII detection (Comprehend) | ✅ Verified | 7/7 entities detected (NAME, EMAIL, PHONE, ADDRESS, SSN, CREDIT_CARD, DATE_TIME) |
| Document anonymization (redaction) | ✅ Verified | All PII replaced with [REDACTED] |
| Soft delete on file removal | ✅ Verified | is_deleted=true, audit trail preserved |
| Lake Formation access control | ✅ Verified | Unauthorized access correctly blocked |
| CloudTrail audit logging | ✅ Verified | All queries logged with user identity |
| 100-file burst processing | ✅ Verified | All processed via SQS retry, DLQ = 0 |
| Iceberg time travel (snapshot history) | ✅ Verified | 5 snapshots, $history table queryable |

## Cost (Measured)

| Component | Monthly Cost (10TB, 100K files) |
|-----------|-------------------------------|
| S3 Tables (metadata storage) | ~$5 |
| Lambda (event sync + AI) | ~$55 |
| Bedrock (AI classification + embedding) | ~$100-500 ($0.01/file measured) |
| OpenSearch Serverless NextGen | **$0 idle** + $0.24/OCU-hour active |
| SQS + Step Functions | ~$6 |
| Comprehend (PII detection) | ~$5 (included in AI processing) |
| **Total** | **~$170-570** (active), **~$0** (idle) |
| FSx for ONTAP (existing, no change) | — |
| S3 copy (eliminated) | **-$230-256 saved** |

**Net effect**: AI-powered metadata catalog with vector search and PII anonymization for less than the cost of the S3 copy it eliminates. Scale-to-zero means PoC/dev environments cost $0 when idle.

> *S3 Standard storage pricing: us-east-1 $0.023/GB ($230/10TB), ap-northeast-1 $0.025/GB ($256/10TB). Verified 2026-06-01.

**PoC deployment time**: All 6 phases verified in a single day.

## Known Limitations

| Limitation | Impact | Workaround | Status |
|-----------|--------|-----------|--------|
| Databricks SQL Warehouse can't query S3 Tables directly | Must use Spark cluster or Athena | Spark cluster config or Athena | Feature request submitted |
| Snowflake can't read S3 Tables as External Iceberg | Must use COPY INTO | COPY INTO → Managed Iceberg | Feature request submitted |
| Lake Formation column-level control: observed limitation on S3 Tables federated catalog path | Can't hide specific columns via this path | Athena Views; AWS docs describe column-level support — investigate alternative registration | AWS case filed |
| Concurrent Lambda writes cause Iceberg commit conflicts | Some writes retry | reserved_concurrency=1 | Design recommendation |

## Iceberg Table Maintenance (Production)

For production deployments, define:

- Snapshot retention period (S3 Tables auto-manages, but verify policy)
- Manifest rewrite cadence (if metadata table grows large)
- Orphan file cleanup policy
- Deduplication view or materialized latest-record table
- Time travel retention policy
- Athena engine version and Iceberg version compatibility

## S3 Tables Access Paths

| Access path | Best for | Governance | Verified |
|---|---|---|:---:|
| S3 Tables REST (`s3tables.<region>.amazonaws.com/iceberg`) | Direct PoC / simple client | IAM + S3 Tables permissions | ✅ |
| AWS Glue REST (`glue.<region>.amazonaws.com/iceberg`) | Production analytics | IAM + Lake Formation | ✅ |
| Athena via Glue federated catalog | SQL analytics | Lake Formation | ✅ |

> **Verified 2026-06-01**: Both S3 Tables REST and Glue REST endpoints successfully access the metadata table from PyIceberg. See [Glue Iceberg REST docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-glue-endpoint.html).

## Next Steps (Customer Decision Points)

| Option | When to Choose | Additional Cost |
|--------|---------------|----------------|
| **Deploy as-is (Phase 1-3)** | Metadata search + AI classification is sufficient | $0 additional |
| **Add vector search (Phase 5)** | Need "find similar files" capability | Scale-to-zero: $0 idle + ~$0.24/OCU-hour active (NextGen, May 2026 GA) |
| **Add anonymization (Phase 6)** | Have PII/PHI data requiring clean room | +$22/month |
| **Wait for platform updates** | Databricks/Snowflake direct access needed | $0 (monitor support cases) |

## How to Try It

```bash
# 1. Create metadata catalog (5 min)
./scripts/create-table-bucket.sh create

# 2. Scan existing files (30 sec)
python scripts/initial-metadata-scan.py --access-point-arn <AP_ALIAS> \
  --table-bucket-arn <TABLE_BUCKET_ARN> --max-files 1000

# 3. Query with Athena (immediate)
SELECT file_name, file_type, classification, summary
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE classification = 'invoice' AND confidence_score >= 0.7;
```

Full guide: [PoC Guide](poc-guide.md)

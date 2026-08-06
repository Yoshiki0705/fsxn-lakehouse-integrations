# Iceberg Metadata Catalog — PoC Guide

🌐 [日本語](poc-guide-ja.md) | English

## Overview

This guide walks through a complete PoC deployment of the Iceberg Metadata Catalog, from S3 Tables creation to Athena query verification. Based on actual deployment evidence from 2026-05-31.

**Time to complete**: ~1 hour  
**Cost**: < $1 (S3 Tables storage + Athena queries)  
**Prerequisites**: FSx for ONTAP with S3 Access Point configured

### Choose Your Method

| Method | Audience | Time | Difficulty |
|--------|----------|------|-----------|
| **Method A: AWS Console (GUI)** | Data analysts, non-infrastructure engineers | 1 hour | ★☆☆ |
| **Method B: CloudFormation** | Infrastructure admins, reproducibility-focused | 30 min | ★★☆ |
| **Method C: CLI + Scripts** | Developers, automation-oriented | 20 min | ★★★ |

---

## Method A: AWS Management Console (GUI)

### A-1: Create S3 Tables Table Bucket

1. Sign in to the AWS Management Console
2. Open the **S3** service
3. In the left menu, select **"Table buckets"**
4. Click **"Create table bucket"**
5. Enter:
   - Bucket name: `fsxn-metadata-catalog`
   - Region: Asia Pacific (Tokyo) `ap-northeast-1`
6. Click **"Create table bucket"**

```
┌─────────────────────────────────────────────────────────────┐
│ Amazon S3 > Table buckets > Create table bucket             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Table bucket name: [fsxn-metadata-catalog          ]       │
│                                                             │
│  AWS Region:        [Asia Pacific (Tokyo) ▼         ]       │
│                                                             │
│                    [Create table bucket]                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### A-2: Query with Athena

> **Prerequisite**: After Step A-1, run Namespace/Table creation and initial scan via CLI (see Method C Steps 1-2). GUI-only table creation is not currently supported (PyIceberg required).

1. Open the **Athena** service
2. In the left menu, select **"Query editor"**
3. Workgroup: Select `primary` or `fsxn-metadata-catalog`
4. **Data source**: Select `AwsDataCatalog`
5. Enter the following query and click **"Run"**:

```sql
SELECT file_name, file_type, file_size, enrichment_status
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
LIMIT 10;
```

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Amazon Athena > Query editor                                            │
├─────────────────────────────────────────────────────────────────────────┤
│ Workgroup: [primary ▼]  Data source: [AwsDataCatalog ▼]                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1 │ SELECT file_name, file_type, file_size, enrichment_status          │
│  2 │ FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"            │
│  3 │      ."unstructured_files"                                         │
│  4 │ LIMIT 10;                                                          │
│                                                                         │
│                              [▶ Run]                                    │
├─────────────────────────────────────────────────────────────────────────┤
│ Results (10 rows, Run time: 1.35 sec, Data scanned: 1.19 KB)            │
├──────────────────────────────┬──────────────────────┬──────────┬────────┤
│ file_name                    │ file_type            │file_size │status  │
├──────────────────────────────┼──────────────────────┼──────────┼────────┤
│ sensor_data_large.parquet    │ application/x-parquet│108002572 │pending │
│ sensor_data.parquet          │ application/x-parquet│  250880  │pending │
│ customers.csv                │ text/csv             │   58132  │pending │
│ invoice_sample.png           │ image/png            │   11338  │pending │
│ product_inspection.png       │ image/png            │    7180  │pending │
└──────────────────────────────┴──────────────────────┴──────────┴────────┘
```

### A-3: Lake Formation Permission Grant (GUI)

1. Open the **Lake Formation** service
2. In the left menu, select **"Data permissions"**
3. Click **"Grant"**
4. Configure:
   - Principal: Select your IAM user or role
   - Catalog: `s3tablescatalog/fsxn-metadata-catalog`
   - Database: `metadata`
   - Table: `unstructured_files`
   - Table permissions: ✅ Select, ✅ Describe
5. Click **"Grant"**

```
┌─────────────────────────────────────────────────────────────────────────┐
│ AWS Lake Formation > Data permissions > Grant                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Principals                                                             │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │ IAM users and roles: [your-user-name ▼]                         │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  LF-Tags or catalog resources                                           │
│  ○ Resources matched by LF-Tags                                         │
│  ● Named Data Catalog resources                                         │
│                                                                         │
│  Catalog:  [s3tablescatalog/fsxn-metadata-catalog ▼]                    │
│  Database: [metadata ▼]                                                 │
│  Table:    [unstructured_files ▼]                                       │
│                                                                         │
│  Table permissions                                                      │
│  ☑ Select    ☑ Describe    ☐ Alter    ☐ Drop    ☐ Insert                │
│                                                                         │
│                              [Grant]                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Method B: CloudFormation Template

### B-1: Deploy CloudFormation Stack

1. Open the **CloudFormation** service
2. Click **"Create stack"** > **"With new resources"**
3. Template source: **"Upload a template file"**
4. File: Upload `cloudformation/s3-tables-setup.yaml`
5. Enter parameters:

| Parameter | Value | Description |
|-----------|-------|-------------|
| TableBucketName | `fsxn-metadata-catalog` | Table bucket name |
| AthenaResultsBucket | `your-athena-results-bucket` | Athena output bucket |
| QueryUserArn | `arn:aws:iam::<ACCOUNT>:user/<USER>` | Query user ARN |

6. **"Next"** → **"Next"** → Check IAM acknowledgment → **"Submit"**

### B-2: Post-Deployment Steps

After CloudFormation stack creation, these additional steps are required:

1. **Register Glue Federated Catalog** (CLI — GUI not yet supported):
```bash
aws glue create-catalog --name "s3tablescatalog" --catalog-input '{
  "FederatedCatalog": {
    "Identifier": "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/*",
    "ConnectionName": "aws:s3tables"
  },
  "CreateDatabaseDefaultPermissions": [],
  "CreateTableDefaultPermissions": []
}' --region ap-northeast-1
```

2. **Create Iceberg table with schema** (PyIceberg — see Method C Step 1)

3. **Run initial metadata scan** (see Method C Step 2)

4. **Grant Lake Formation permissions** (can use GUI — see Method A Step A-3)

---

## Method C: CLI + Scripts

> For developers and automation-oriented users. Fastest path (~20 minutes).

### Step 1: Create S3 Tables Table Bucket (2 minutes)

```bash
# Create the table bucket
aws s3tables create-table-bucket \
  --name fsxn-metadata-catalog \
  --region ap-northeast-1

# Expected output:
# {
#     "arn": "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog"
# }
```

### Create Namespace

```bash
aws s3tables create-namespace \
  --table-bucket-arn "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog" \
  --namespace metadata \
  --region ap-northeast-1
```

### Create Iceberg Table with Schema (via PyIceberg)

```bash
pip install boto3 pyarrow 'pyiceberg[s3tables]'
```

```python
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import *
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform

catalog = load_catalog('s3tables', **{
    'type': 'rest',
    'uri': 'https://s3tables.ap-northeast-1.amazonaws.com/iceberg',
    'warehouse': 'arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog',
    'rest.sigv4-enabled': 'true',
    'rest.signing-region': 'ap-northeast-1',
    'rest.signing-name': 's3tables',
})

schema = Schema(
    NestedField(1, 'file_id', StringType(), required=True),
    NestedField(2, 'file_path', StringType(), required=True),
    NestedField(3, 'file_name', StringType(), required=True),
    NestedField(4, 'file_type', StringType(), required=False),
    NestedField(5, 'file_size', LongType(), required=False),
    NestedField(6, 'created_at', TimestamptzType(), required=False),
    NestedField(7, 'modified_at', TimestamptzType(), required=False),
    # ... (full schema in scripts/initial-metadata-scan.py)
    NestedField(19, 'enrichment_status', StringType(), required=False),
    NestedField(21, 'is_deleted', BooleanType(), required=True),
)

table = catalog.create_table(
    identifier='metadata.unstructured_files',
    schema=schema,
    partition_spec=PartitionSpec(
        PartitionField(source_id=4, field_id=1000,
                       transform=IdentityTransform(), name='file_type_partition')
    ),
)
print(f'✅ Table created: {table.name()}')
```

> **Note**: `aws s3tables create-table --format ICEBERG` creates an empty table without schema. Use PyIceberg `create_table()` for schema-defined tables.

---

## Step 2: Run Initial Metadata Scan (30 seconds)

```bash
python scripts/initial-metadata-scan.py \
  --access-point-arn "<YOUR-AP-ALIAS-ext-s3alias>" \
  --table-bucket-arn "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog" \
  --max-files 1000
```

### Expected Output

```
============================================================
FSx for ONTAP → Iceberg Metadata Catalog: Initial Scan
============================================================
  Access Point: verification-tes-...-ext-s3alias
  Max files:    1000
  Region:       ap-northeast-1
============================================================

[1/3] Listing objects from FSx S3 Access Point...
  Found 38 objects
[2/3] Building metadata records...
  Built 38 metadata records (skipped 0 directory markers)

  Sample record:
    file_id:   ce9b8af6-f50a-56ab-9e58-2de973d4f425
    file_name: athena-s3cp-test.txt
    file_type: text/plain
    file_size: 24 bytes
    enrichment_status: pending

[3/3] Writing to Iceberg metadata table...
  ✅ Wrote 38 records to metadata.unstructured_files

============================================================
  Total files scanned:    38
  Metadata records:       38
  Enrichment pending:     38
============================================================
```

### Verify with PyIceberg (optional)

```python
table = catalog.load_table('metadata.unstructured_files')
scan = table.scan(limit=5)
arrow_table = scan.to_arrow()
print(f'Records: {arrow_table.num_rows}')
for i in range(arrow_table.num_rows):
    print(f'  {arrow_table.column("file_name")[i].as_py()}')
```

---

## Step 3: Register Glue Federated Catalog (1 minute)

S3 Tables requires a Glue Federated Catalog for Athena access:

```bash
aws glue create-catalog \
  --name "s3tablescatalog" \
  --catalog-input '{
    "FederatedCatalog": {
      "Identifier": "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/*",
      "ConnectionName": "aws:s3tables"
    },
    "CreateDatabaseDefaultPermissions": [],
    "CreateTableDefaultPermissions": []
  }' \
  --region ap-northeast-1
```

> **Important**: The catalog name `s3tablescatalog` is a reserved name for S3 Tables federation. Use exactly this name.

---

## Step 4: Grant Lake Formation Permissions (1 minute)

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT_ID>:user/<YOUR_USER>"}' \
  --resource '{"Table": {"CatalogId": "s3tablescatalog/fsxn-metadata-catalog", "DatabaseName": "metadata", "Name": "unstructured_files"}}' \
  --permissions '["SELECT", "DESCRIBE"]' \
  --region ap-northeast-1
```

> **Note**: Without this step, Athena returns `COLUMN_NOT_FOUND: Relation contains no accessible columns`. This is a Lake Formation permission issue, not a schema issue.

---

## Step 5: Query with Athena (immediate)

### Query Syntax

```sql
-- S3 Tables catalog syntax:
-- "s3tablescatalog/<table-bucket-name>"."<namespace>"."<table-name>"

SELECT file_name, file_type, file_size, enrichment_status
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
LIMIT 10;
```

### Verified Query Results (2026-05-31)

**Query 1: Basic metadata retrieval** (799ms, 4.6KB scanned)

| file_name | file_type | file_size | enrichment_status | source_volume |
|-----------|-----------|-----------|-------------------|---------------|
| sensor_data_large.parquet | application/x-parquet | 108,002,572 | pending | benchmark |
| sensor_data_large.parquet | application/x-parquet | 108,002,572 | pending | bronze |
| sensor_data.parquet | application/x-parquet | 250,880 | pending | sensor-data |
| write-test.parquet | application/x-parquet | 250,880 | pending | neg-test |
| sensor_data.parquet | application/x-parquet | 250,880 | pending | bronze |

**Query 2: File type distribution** (GROUP BY aggregation)

| file_type | file_count | total_bytes |
|-----------|-----------|-------------|
| application/x-parquet | 26 | 217,777,490 |
| text/csv | 2 | 58,143 |
| image/png | 3 | 27,898 |
| application/json | 2 | 3,471 |
| application/octet-stream | 4 | 1,455 |
| text/plain | 1 | 24 |

### More Query Examples

```sql
-- Files by source volume
SELECT source_volume, COUNT(*) AS count, SUM(file_size) AS total_bytes
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
GROUP BY source_volume
ORDER BY total_bytes DESC;

-- Find image files (candidates for AI Vision processing)
SELECT file_name, file_path, file_size
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE file_type LIKE 'image/%'
  AND is_deleted = false;

-- Files pending AI enrichment (input for Phase 3)
SELECT COUNT(*) AS pending_count
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE enrichment_status = 'pending'
  AND is_deleted = false;
```

---

## Performance Characteristics (Observed)

| Metric | Value | Notes |
|--------|-------|-------|
| Table creation | < 1 second | PyIceberg REST API |
| Initial scan (38 files) | < 30 seconds | ListObjectsV2 + PyIceberg append |
| Athena query latency | 799-1351 ms | Sub-2-second for all tested queries |
| Data scanned per query | 1-5 KB | Metadata only (very efficient) |
| Athena engine | Version 3 | Iceberg native support |

---

## Troubleshooting

| Symptom | Cause | Solution |
|---------|-------|----------|
| `CATALOG_NOT_FOUND: Catalog 's3tablescatalog' does not exist` | Glue Federated Catalog not registered | Run Step 3 (create-catalog) |
| `COLUMN_NOT_FOUND: Relation contains no accessible columns` | Lake Formation permissions missing | Run Step 4 (grant-permissions) |
| `invalid_metadata_location` when writing via PyIceberg | Table created via CLI without schema | Delete and recreate via PyIceberg `create_table()` |
| `Mismatch in fields: value: required string vs optional string` | PyArrow map type has nullable values | Use `pa.field('value', pa.string(), nullable=False)` |
| `ModuleNotFoundError: pyiceberg` | PyIceberg not installed | `pip install 'pyiceberg[s3tables]'` |

---

## Cleanup

```bash
# Delete table
aws s3tables delete-table \
  --table-bucket-arn "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog" \
  --namespace metadata --name unstructured_files --region ap-northeast-1

# Delete namespace
aws s3tables delete-namespace \
  --table-bucket-arn "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog" \
  --namespace metadata --region ap-northeast-1

# Delete table bucket
aws s3tables delete-table-bucket \
  --table-bucket-arn "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog" \
  --region ap-northeast-1

# Remove Glue catalog (optional — shared across all S3 Tables)
aws glue delete-catalog --name s3tablescatalog --region ap-northeast-1
```

---

## Next Steps After PoC

### Production Recommended Settings (Derived from Test Results)

The following settings are derived from Phase 1+2 test results for production environments:

```yaml
# Lambda configuration
reserved_concurrency: 1       # Prevents Iceberg commit conflicts (critical)
memory_size: 512              # Required for PyIceberg + PyArrow
timeout: 120                  # Sufficient for S3 Tables writes

# SQS configuration
batch_size: 10                # Process 10 messages per Lambda invocation
max_batching_window: 30       # Accumulate messages for 30s before batch
visibility_timeout: 300       # 5x Lambda timeout
max_receive_count: 3          # Retries before DLQ

# Athena query (with deduplication — always use in production)
# Iceberg append-only may create duplicate records for same file_id
# Use ROW_NUMBER() to get latest record only
SELECT * FROM (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY file_id ORDER BY modified_at DESC) as rn
  FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
) WHERE rn = 1 AND is_deleted = false;
```

**Key constraints**:
| Constraint | Impact | Workaround |
|-----------|--------|-----------|
| Concurrent Lambda = commit conflict | Some writes fail during bursts → retry | `reserved_concurrency: 1` |
| Append-only = duplicate records | Query results may contain duplicates | `ROW_NUMBER()` dedup |
| Lake Formation column-level not supported | Federated catalog doesn't support column exclusion | Use Athena Views for column filtering |

### Quick Runbook: Incident Response

#### DLQ Message Check → Redrive

```bash
# 1. Check DLQ message count
aws sqs get-queue-attributes \
  --queue-url "https://sqs.ap-northeast-1.amazonaws.com/<ACCOUNT_ID>/fsxn-metadata-sync-dlq" \
  --attribute-names All \
  --query 'Attributes.ApproximateNumberOfMessages' \
  --region ap-northeast-1

# 2. Inspect DLQ messages (identify root cause)
aws sqs receive-message \
  --queue-url "https://sqs.ap-northeast-1.amazonaws.com/<ACCOUNT_ID>/fsxn-metadata-sync-dlq" \
  --max-number-of-messages 5 \
  --region ap-northeast-1

# 3. After fixing root cause, redrive DLQ → main queue
aws sqs start-message-move-task \
  --source-arn "arn:aws:sqs:ap-northeast-1:<ACCOUNT_ID>:fsxn-metadata-sync-dlq" \
  --destination-arn "arn:aws:sqs:ap-northeast-1:<ACCOUNT_ID>:fsxn-metadata-sync" \
  --region ap-northeast-1
```

#### Lambda Error Investigation

```bash
# Check recent error logs
aws logs filter-log-events \
  --log-group-name /aws/lambda/fsxn-metadata-sync \
  --filter-pattern "ERROR" \
  --start-time $(date -v-1H +%s000) \
  --region ap-northeast-1 \
  --query 'events[*].message' --output text
```

#### Metadata Reconciliation

```bash
# Compare FSx for ONTAP S3 AP file count with metadata table record count
# Re-run initial scan if gap detected
python scripts/initial-metadata-scan.py \
  --access-point-arn "<AP_ALIAS>" \
  --table-bucket-arn "<TABLE_BUCKET_ARN>" \
  --max-files 10000
```

---

### Full Deployment Roadmap

1. **Phase 2**: Deploy FPolicy → SQS → Lambda pipeline for real-time metadata sync
2. **Phase 3**: Enable AI enrichment (Bedrock classification + embedding generation)
3. **Phase 4**: Configure cross-platform access (Databricks, Snowflake)
4. **Phase 5**: Add vector similarity search (OpenSearch Serverless)
5. **Phase 6**: Implement anonymization pipeline for PII-containing files

See [Architecture Document](../../../docs/en/iceberg-metadata-catalog.md) for full design details.

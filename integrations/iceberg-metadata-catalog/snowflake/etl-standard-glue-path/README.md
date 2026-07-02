# ETL Path: S3 Tables → Standard Glue Iceberg → Snowflake

🌐 [日本語](README-ja.md) | English

## Purpose

> **This is a workaround for a limitation as of 2026-06-03**: S3 Tables internal buckets cannot be accessed by Snowflake due to (1) Glue Iceberg REST not implementing the standard Iceberg REST `/credentials` endpoint, and (2) S3 Tables internal buckets rejecting `ListObjectsV2` required by Snowflake's storage access pattern. AWS has accepted a feature request for `/credentials` endpoint implementation. When this is resolved, this ETL path becomes unnecessary and direct Snowflake → S3 Tables access will be possible.

This workaround replicates **metadata only** (not source files) from S3 Tables to a standard Glue-managed Iceberg table on a regular S3 bucket. From there, Snowflake's `VENDED_CREDENTIALS` + Lake Formation integration (public preview) can provide governed Iceberg access.

**What this does NOT change**:
- Source files remain on FSx for ONTAP (zero-copy storage principle preserved)
- S3 Tables remains the authoritative metadata catalog (Athena, EMR Spark access unchanged)
- Only the Iceberg metadata table data files (~MB scale) are duplicated to standard S3

**Why standard S3 and not FSx S3 Access Point**:
- FSx for ONTAP S3 AP does support PutObject, DeleteObject, and ListObjectsV2 — it is NOT read-only
- However, whether PyIceberg/Spark Iceberg libraries support FSx for ONTAP S3 AP alias URI format as a table location has not been validated
- Whether Glue Data Catalog can register FSx for ONTAP S3 AP paths as Iceberg table locations is unconfirmed
- Standard S3 is chosen as the reliable path because compatibility with Glue + Lake Formation + Snowflake is fully confirmed
- Using FSx for ONTAP S3 AP as Iceberg metadata table storage is a future validation candidate
- The mirrored metadata is small (~1KB per file record × number of files) — storage cost is negligible either way

## Architecture

```
S3 Tables (source of truth)
    │
    │ PyIceberg read
    ▼
ETL Lambda / Script
    │
    │ PyIceberg write
    ▼
Standard S3 Bucket (Iceberg format)
    │
    │ Registered in Glue Data Catalog
    ▼
Lake Formation (governance)
    │
    │ VENDED_CREDENTIALS
    ▼
Snowflake (CATALOG INTEGRATION)
```

## Prerequisites

- S3 Tables metadata table exists and has data (verified)
- Standard S3 bucket for Iceberg target (e.g., `s3://<bucket>/iceberg-mirror/`)
- Glue database for the mirrored table
- Lake Formation configured with appropriate permissions
- Snowflake account with Iceberg catalog integration capability

## Steps

### Step 1: Create target S3 bucket and Glue database

```bash
# Create S3 bucket for mirrored Iceberg table
aws s3 mb s3://fsxn-metadata-mirror-<ACCOUNT_ID> --region ap-northeast-1

# Create Glue database
aws glue create-database \
  --database-input '{"Name":"metadata_mirror","Description":"Mirrored metadata from S3 Tables for Snowflake access"}' \
  --region ap-northeast-1
```

### Step 2: ETL script — read from S3 Tables, write to standard Iceberg

```bash
python etl-s3tables-to-standard-iceberg.py
```

See [etl-s3tables-to-standard-iceberg.py](etl-s3tables-to-standard-iceberg.py) for the full script.

### Step 3: Register with Lake Formation

```bash
# Register S3 location with Lake Formation
aws lakeformation register-resource \
  --resource-arn 'arn:aws:s3:::fsxn-metadata-mirror-<ACCOUNT_ID>' \
  --use-service-linked-role \
  --region ap-northeast-1

# Grant permissions to Snowflake IAM role
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipal":{"DataLakePrincipalIdentifier":"arn:aws:iam::<ACCOUNT_ID>:role/fsxn-snowflake-verification-role"}}' \
  --resource '{"Table":{"DatabaseName":"metadata_mirror","Name":"unstructured_files","CatalogId":"<ACCOUNT_ID>"}}' \
  --permissions '["SELECT","DESCRIBE"]' \
  --region ap-northeast-1
```

### Step 4: Validate via Athena

```sql
SELECT * FROM metadata_mirror.unstructured_files LIMIT 10;
```

### Step 5: Snowflake CATALOG INTEGRATION (standard Glue, not s3tablescatalog)

```sql
CREATE OR REPLACE CATALOG INTEGRATION glue_standard_mirror_int
  CATALOG_SOURCE = ICEBERG_REST
  TABLE_FORMAT = ICEBERG
  CATALOG_NAMESPACE = 'metadata_mirror'
  REST_CONFIG = (
    CATALOG_URI = 'https://glue.ap-northeast-1.amazonaws.com/iceberg'
    CATALOG_API_TYPE = AWS_GLUE
    CATALOG_NAME = '<ACCOUNT_ID>'
    ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS
  )
  REST_AUTHENTICATION = (
    TYPE = SIGV4
    SIGV4_IAM_ROLE = 'arn:aws:iam::<ACCOUNT_ID>:role/fsxn-snowflake-verification-role'
    SIGV4_SIGNING_REGION = 'ap-northeast-1'
  )
  ENABLED = TRUE;

-- Update IAM trust policy with new External ID from DESCRIBE
DESCRIBE CATALOG INTEGRATION glue_standard_mirror_int;

-- Create Iceberg table
CREATE OR REPLACE ICEBERG TABLE FSXN_LAKEHOUSE.PUBLIC.metadata_mirror_test
  CATALOG = 'glue_standard_mirror_int'
  CATALOG_TABLE_NAME = 'unstructured_files'
  AUTO_REFRESH = TRUE;

-- Query
SELECT * FROM FSXN_LAKEHOUSE.PUBLIC.metadata_mirror_test LIMIT 10;
```

### Step 6: Validate Lake Formation governance

```sql
-- Should work: table-level access
SELECT ai_classification, COUNT(*) FROM metadata_mirror_test GROUP BY 1;

-- Test: Does Lake Formation row/column filtering propagate to Snowflake?
-- (This is the key question for the public preview)
```

## Expected Outcomes

| Test | Expected |
|------|----------|
| PyIceberg ETL (read S3 Tables → write standard S3) | ✅ Should work |
| Athena query on mirrored table | ✅ Should work |
| Snowflake CATALOG INTEGRATION (standard Glue) | ✅ Should work (public preview) |
| Snowflake CREATE ICEBERG TABLE | ✅ Should work (credential vending via standard Glue) |
| Snowflake SELECT | ✅ Should work |
| Lake Formation governance via Snowflake | ⚠️ To be validated |

## Limitations

- **Not zero-copy**: Metadata is duplicated from S3 Tables to standard S3
- **Sync lag**: ETL must be scheduled (not real-time)
- **Dual table management**: Schema changes must be applied to both S3 Tables and mirror
- **Public preview**: Snowflake + Lake Formation integration may have limitations
- **Cost**: Additional S3 storage (minimal — metadata only) + ETL compute

## When This Becomes Unnecessary

This ETL path is a medium-term workaround. It becomes unnecessary when either:
1. AWS implements standard Iceberg REST `/credentials` on Glue Iceberg REST endpoint (feature request submitted)
2. Snowflake adds native S3 Tables support (no public timeline)
3. S3 Tables internal buckets become accessible to external engines (no public timeline)

## Files

| File | Purpose |
|------|---------|
| `etl-s3tables-to-standard-iceberg.py` | ETL script |
| `snowflake-setup.sql` | Snowflake DDL for catalog integration |
| `lakeformation-setup.sh` | Lake Formation registration and grants |
| `README.md` | This file |
| `README-ja.md` | Japanese version |

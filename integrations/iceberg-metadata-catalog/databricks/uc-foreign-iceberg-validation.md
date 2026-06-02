# UC Foreign Iceberg Validation Plan

🌐 [日本語](uc-foreign-iceberg-validation-ja.md) | English

## Purpose

Validate whether Unity Catalog Foreign Iceberg can access S3 Tables metadata via the AWS Glue Iceberg REST endpoint, providing governed metadata access without DataSync or format conversion.

## Background

- Databricks [Foreign Iceberg is GA](https://www.databricks.com/blog/unity-catalog-and-next-era-apache-icebergtm) (Jun 2026)
- AWS published [guidance on accessing S3 Iceberg tables from Databricks using Glue Iceberg REST](https://aws.amazon.com/blogs/big-data/access-amazon-s3-iceberg-tables-from-databricks-using-aws-glue-iceberg-rest-catalog-in-amazon-sagemaker-lakehouse)
- Databricks [catalog federation supports AWS Glue](https://docs.databricks.com/aws/en/query-federation/hms-federation-glue)

## Known Limitations (from Databricks docs)

| Limitation | Impact | Source |
|---|---|---|
| Credential vending on Foreign Iceberg tables is not supported | External storage credentials must be configured separately | [docs](https://docs.databricks.com/aws/external-access/iceberg) |
| Foreign Iceberg tables are not automatically refreshed | `REFRESH FOREIGN TABLE` required to see latest snapshot | [docs](https://docs.databricks.com/aws/external-access/iceberg) |
| Read-only access | Cannot write to Foreign Iceberg tables from Databricks | [docs](https://docs.databricks.com/aws/iceberg/) |

## Validation Steps

### B-4: UC Foreign Iceberg via S3 Tables Direct REST

```sql
-- Step 1: Create service credential for S3 Tables access
CREATE SERVICE CREDENTIAL s3tables_cred
WITH (
  -- IAM role with s3tables:* permissions
);

-- Step 2: Create connection to S3 Tables REST endpoint
CREATE CONNECTION s3tables_rest TYPE iceberg_rest
OPTIONS (
  uri = 'https://s3tables.ap-northeast-1.amazonaws.com/iceberg',
  warehouse = 'arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog',
  credential_name = 's3tables_cred'
  -- SigV4 signing configuration TBD
);

-- Step 3: Create foreign catalog
CREATE FOREIGN CATALOG s3tables_metadata
USING CONNECTION s3tables_rest;

-- Step 4: Query
SELECT * FROM s3tables_metadata.metadata.unstructured_files LIMIT 10;
```

### B-5: UC Foreign Iceberg via Glue Iceberg REST

```sql
-- Step 1: Create service credential for Glue access
CREATE SERVICE CREDENTIAL glue_cred
WITH (
  -- IAM role with glue:* permissions
);

-- Step 2: Create connection to Glue Iceberg REST endpoint
CREATE CONNECTION glue_iceberg_rest TYPE iceberg_rest
OPTIONS (
  uri = 'https://glue.ap-northeast-1.amazonaws.com/iceberg',
  warehouse = '<ACCOUNT_ID>:s3tablescatalog/fsxn-metadata-catalog',
  credential_name = 'glue_cred'
  -- SigV4 signing configuration TBD
);

-- Step 3: Create foreign catalog
CREATE FOREIGN CATALOG glue_metadata
USING CONNECTION glue_iceberg_rest;

-- Step 4: Query
SELECT * FROM glue_metadata.metadata.unstructured_files LIMIT 10;
```

### Alternative: Hive Metastore Federation with AWS Glue

```sql
-- If iceberg_rest connection type is not available for foreign catalogs,
-- try Hive Metastore federation (confirmed supported for AWS Glue)
CREATE CONNECTION glue_hms TYPE hive_metastore
OPTIONS (
  -- AWS Glue Hive Metastore connection
  -- See: https://docs.databricks.com/aws/en/query-federation/hms-federation-glue
);

CREATE FOREIGN CATALOG glue_hms_catalog
USING CONNECTION glue_hms
OPTIONS (authorized_paths = 's3://...');
```

## Success Criteria

| Criterion | Expected |
|---|---|
| Foreign catalog created | No errors |
| Namespaces visible | `metadata` namespace listed |
| Tables visible | `unstructured_files` table listed |
| SELECT query works | Returns rows with file metadata |
| Time travel works | `SELECT * ... FOR SYSTEM_TIME AS OF` returns historical data |
| REFRESH FOREIGN TABLE works | Latest snapshot visible after refresh |
| UC governance applies | UC grants control access to foreign table |
| UC lineage recorded | Query appears in UC lineage graph |

## Refresh Semantics Validation

```sql
-- 1. Query current state
SELECT COUNT(*) FROM glue_metadata.metadata.unstructured_files;

-- 2. Add new records via PyIceberg (from Lambda or local)
-- (append new file metadata)

-- 3. Query again WITHOUT refresh — expect stale count
SELECT COUNT(*) FROM glue_metadata.metadata.unstructured_files;

-- 4. Refresh
REFRESH FOREIGN TABLE glue_metadata.metadata.unstructured_files;

-- 5. Query again — expect updated count
SELECT COUNT(*) FROM glue_metadata.metadata.unstructured_files;
```

### Detailed Snapshot Freshness Test

```sql
-- Record snapshot_id before append
SELECT snapshot_id FROM glue_metadata.metadata.unstructured_files.history LIMIT 1;

-- After PyIceberg append from AWS side:
-- 1. Query Databricks — does it see the new snapshot?
SELECT snapshot_id FROM glue_metadata.metadata.unstructured_files.history LIMIT 1;
-- Expected: SAME as before (no auto-refresh)

-- 2. Run REFRESH
REFRESH FOREIGN TABLE glue_metadata.metadata.unstructured_files;

-- 3. Query again
SELECT snapshot_id FROM glue_metadata.metadata.unstructured_files.history LIMIT 1;
-- Expected: NEW snapshot_id (after refresh)

-- 4. Compare with Athena
-- Run same query in Athena — should always show latest snapshot
-- Document the delta between Athena (always fresh) and Databricks (refresh-dependent)
```

## Status

- B-4 (S3 Tables direct REST): Follow-up submitted to Databricks support (2026-06-01)
- B-5 (Glue Iceberg REST): Follow-up submitted to Databricks support (2026-06-01)
- Awaiting support guidance on connection type and credential configuration

## References

- [Databricks Foreign Iceberg docs](https://docs.databricks.com/aws/external-access/iceberg)
- [AWS Glue Iceberg REST → Databricks blog](https://aws.amazon.com/blogs/big-data/access-amazon-s3-iceberg-tables-from-databricks-using-aws-glue-iceberg-rest-catalog-in-amazon-sagemaker-lakehouse)
- [Databricks Catalog Federation](https://docs.databricks.com/aws/en/query-federation/catalog-federation)
- [AWS Glue → UC federation](https://docs.aws.amazon.com/lake-formation/latest/dg/catalog-federation-databricks.html)

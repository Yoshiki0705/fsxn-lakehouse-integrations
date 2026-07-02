# Snowflake + FSx for ONTAP S3 Access Point: Troubleshooting Guide

🌐 [日本語](troubleshooting-guide-ja.md) | English

> Common errors and solutions when integrating Snowflake with Amazon FSx for ONTAP via S3 Access Points and AWS Glue Iceberg REST catalog.
>
> Last verified: 2026-06-02 | Region: ap-northeast-1

---

## TO_FILE Issues

### Error: "SQL compilation error: invalid argument for function [TO_FILE]"

**Symptoms:**

```
SQL compilation error: invalid argument for function [TO_FILE]
```

**Root Cause:** The stage reference is passed as a SQL identifier instead of a string literal.

**Fix:** Wrap the stage path in single quotes (string literal syntax).

```sql
-- ❌ WRONG: Stage as identifier (causes SQL compilation error)
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'claude-sonnet-4-5',
  'Describe this file',
  TO_FILE(@DB.SCHEMA.STAGE, 'path/to/file.txt')
);

-- ✅ CORRECT: Stage as string literal
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'claude-sonnet-4-5',
  'Describe this file',
  TO_FILE('@DB.SCHEMA.STAGE', 'path/to/file.txt')
);
```

**Key point:** `TO_FILE` requires its first argument as a **string literal** (`'@...'`), not an identifier (`@...`). This is different from `LIST @stage` or `SELECT ... FROM @stage` which use identifiers.

---

### Error: "Remote file was not found"

**Symptoms:**

```
Remote file was not found. Please check the file path and try again.
```

**Root Cause:** The file path specified in `TO_FILE` does not exist on the stage.

**Diagnostic Steps:**

```sql
-- Step 1: List all files on the stage to verify what exists
LIST @DB.SCHEMA.STAGE;

-- Step 2: Check the exact file path (case-sensitive, no leading slash)
LIST @DB.SCHEMA.STAGE PATTERN = '.*your-file.*';

-- Step 3: Verify database and schema in the stage reference
SHOW STAGES IN SCHEMA DB.SCHEMA;
```

**Common Mistakes:**

| Mistake | Example | Fix |
|---------|---------|-----|
| Wrong file name | `'_sample.png'` (doesn't exist) | Use exact name from `LIST` output |
| Leading slash | `'/path/to/file.txt'` | Remove leading slash: `'path/to/file.txt'` |
| Wrong DB/schema | `'@WRONG_DB.PUBLIC.STAGE'` | Verify with `SHOW STAGES` |
| Path includes stage prefix | `'@STAGE/folder/file.txt'` duplicated | Path is relative to stage root |

**Verified Working Example:**

```sql
-- 1. Confirm file exists
LIST @FSXN_LAKEHOUSE.PUBLIC.FSXN_AP_ARN_TEST_STAGE;
-- Returns: athena-results/athena-s3cp-test.txt

-- 2. Use exact path from LIST output
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'claude-sonnet-4-5',
  'What is in this file?',
  TO_FILE('@FSXN_LAKEHOUSE.PUBLIC.FSXN_AP_ARN_TEST_STAGE', 'athena-results/athena-s3cp-test.txt')
) AS result;
-- ✅ SUCCESS
```

---

## Iceberg Catalog Integration Issues

### Error: "Failed to retrieve credentials from the Catalog" (004174)

**Symptoms:**

```
004174 (S1009): Failed to retrieve credentials from the Catalog.
Please verify that the catalog supports VENDED_CREDENTIALS and has been configured properly.
```

**Root Cause:** AWS Glue Iceberg REST endpoint does **not** implement credential vending. Snowflake's `VENDED_CREDENTIALS` authentication type requires the catalog's `loadTable` response to include:

- `s3.access-key-id`
- `s3.secret-access-key`
- `s3.session-token`

AWS Glue REST returns `UnknownOperationException` for the `/credentials` operation — this is a service limitation, not a configuration error.

**Verification:**

```sql
-- Connectivity itself is healthy:
SELECT SYSTEM$VERIFY_CATALOG_INTEGRATION('S3TABLES_GLUE_REST_INT');
-- Returns: "Statement executed successfully"

-- But table creation fails:
CREATE ICEBERG TABLE test_table
  EXTERNAL_VOLUME = 'my_volume'
  CATALOG = 's3tables_glue_rest_int'
  CATALOG_TABLE_NAME = 'metadata';
-- Error 004174
```

**Why SYSTEM$VERIFY_CATALOG_INTEGRATION passes:** This command only checks network connectivity and IAM authentication to the Glue endpoint. It does **not** test credential vending (loadTable with credentials).

**Workarounds:**

| Approach | Description | Trade-off |
|----------|-------------|-----------|
| **Metadata sync** | Sync curated metadata to Snowflake table via scheduled task | No zero-copy; requires sync pipeline |
| **Object Store catalog** | Point to Iceberg metadata files directly on S3 | Manual metadata path management; no auto-refresh |
| **Snowflake Open Catalog (Polaris)** | Use Snowflake-managed catalog | Separate catalog from AWS Glue |
| **Wait for AWS support** | Glue REST credential vending may be added in the future | Timeline unknown |

**Recommended path:** Metadata sync pattern. See [path-decision-guide.md](path-decision-guide.md) for details.

---

### Error: "Insufficient Lake Formation permission(s)" (004139)

**Symptoms:**

```
004139: Insufficient Lake Formation permission(s) on <table_arn>
```

**Root Cause:** The Snowflake IAM role does not have Lake Formation permissions on the target table.

**Fix:**

1. Grant Lake Formation permissions to the Snowflake external function role:

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipal": {"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT_ID>:role/<snowflake-role>"}}' \
  --resource '{"Table": {"DatabaseName": "<db>", "Name": "<table>", "CatalogId": "<ACCOUNT_ID>"}}' \
  --permissions "SELECT" "DESCRIBE" \
  --region ap-northeast-1
```

2. Also ensure the role has `lakeformation:GetDataAccess` in its IAM policy:

```json
{
  "Effect": "Allow",
  "Action": [
    "lakeformation:GetDataAccess"
  ],
  "Resource": "*"
}
```

3. If using S3 Tables federated catalog, verify the catalog is registered with Lake Formation:

```bash
aws glue get-database --name <catalog_database_name> --region ap-northeast-1
```

---

## Diagnostic Commands

### SYSTEM$VERIFY_CATALOG_INTEGRATION

Tests network connectivity and IAM authentication to the catalog endpoint.

```sql
SELECT SYSTEM$VERIFY_CATALOG_INTEGRATION('<integration_name>');
-- Success: "Statement executed successfully"
-- Failure: Returns error details (network, IAM, etc.)
```

**Important:** A successful result does NOT mean credential vending works. It only verifies the catalog endpoint is reachable.

### SYSTEM$LIST_NAMESPACES_FROM_CATALOG

Lists namespaces visible through the catalog integration.

```sql
SELECT SYSTEM$LIST_NAMESPACES_FROM_CATALOG('<integration_name>');
```

### LIST @stage

Verify files accessible through an external stage.

```sql
-- List all files
LIST @DB.SCHEMA.STAGE_NAME;

-- Filter by pattern
LIST @DB.SCHEMA.STAGE_NAME PATTERN = '.*\.txt';
```

### DESCRIBE CATALOG INTEGRATION

Shows configuration details including IAM user ARN and external ID (needed for trust policy).

```sql
DESCRIBE CATALOG INTEGRATION <integration_name>;
-- Key fields:
-- API_AWS_IAM_USER_ARN: The Snowflake-managed IAM user
-- API_AWS_EXTERNAL_ID: External ID for IAM trust policy
```

### SHOW STAGES

Verify stage configuration.

```sql
SHOW STAGES IN SCHEMA DB.SCHEMA;
DESCRIBE STAGE DB.SCHEMA.STAGE_NAME;
```

---

## Quick Reference: Error Code Lookup

| Error Code | Message | Section |
|------------|---------|---------|
| — | SQL compilation error: invalid argument for function [TO_FILE] | [TO_FILE syntax](#error-sql-compilation-error-invalid-argument-for-function-to_file) |
| — | Remote file was not found | [File not found](#error-remote-file-was-not-found) |
| 004174 | Failed to retrieve credentials from the Catalog | [Credential vending](#error-failed-to-retrieve-credentials-from-the-catalog-004174) |
| 004139 | Insufficient Lake Formation permission(s) | [Lake Formation permissions](#error-insufficient-lake-formation-permissions-004139) |

---

## Related Documentation

- [External Stage validation (FSx for ONTAP S3 AP)](external-stage-fsx-s3ap-validation.md)
- [Glue REST credential vending validation](glue-rest-vended-credentials-validation.md)
- [Integration path decision guide](path-decision-guide.md)
- [Snowflake: TO_FILE function](https://docs.snowflake.com/en/sql-reference/functions/to_file)
- [Snowflake: Iceberg REST catalog integration](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-rest)
- [AWS: Glue Iceberg REST endpoint](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-glue-endpoint.html)

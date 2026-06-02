# Snowflake Glue REST + Vended Credentials Validation

🌐 [日本語](glue-rest-vended-credentials-validation-ja.md) | English

## Purpose

Document the validation of Snowflake CATALOG INTEGRATION with AWS Glue Iceberg REST endpoint using vended credentials for S3 Tables access.

## Current Status

| Step | Status | Notes |
|---|---|---|
| CATALOG INTEGRATION created | ✅ | `ICEBERG_REST` + `AWS_GLUE` + `VENDED_CREDENTIALS` |
| DESCRIBE CATALOG INTEGRATION | ✅ | Returns valid IAM credentials |
| CREATE ICEBERG TABLE | ❌ | "Failed to retrieve credentials from the Catalog" |
| Support case active | 🔄 | Snowflake + AWS support engaged |

## Configuration

### Catalog Integration

```sql
CREATE OR REPLACE CATALOG INTEGRATION s3tables_glue_rest_int
  CATALOG_SOURCE = ICEBERG_REST
  TABLE_FORMAT = ICEBERG
  CATALOG_NAMESPACE = 'metadata'
  REST_CONFIG = (
    CATALOG_URI = 'https://glue.ap-northeast-1.amazonaws.com/iceberg'
    WAREHOUSE = '<ACCOUNT_ID>:s3tablescatalog/fsxn-metadata-catalog'
    CATALOG_API_TYPE = AWS_GLUE
  )
  REST_AUTHENTICATION = (
    TYPE = VENDED_CREDENTIALS
    CATALOG_IAM_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/fsxn-snowflake-verification-role'
  )
  ENABLED = TRUE;
```

### DESCRIBE Output

```sql
DESCRIBE CATALOG INTEGRATION s3tables_glue_rest_int;
-- Returns:
-- API_AWS_IAM_USER_ARN: arn:aws:iam::465774455528:user/3u4g1000-s
-- API_AWS_EXTERNAL_ID: VP28055_SFCRole=4_XED90KG9gprirTrHg2DGl26RvB0=
```

### Failed CREATE ICEBERG TABLE

```sql
CREATE OR REPLACE ICEBERG TABLE test_metadata
  EXTERNAL_VOLUME = 'fsxn_s3tables_vol'  -- if needed
  CATALOG = 's3tables_glue_rest_int'
  CATALOG_TABLE_NAME = 'unstructured_files';
-- ERROR: Failed to retrieve credentials from the Catalog
```

## Validation Checklist

| Check | Status | Evidence |
|---|---|---|
| IAM trust policy includes Snowflake user ARN | ✅ | Trust policy updated |
| IAM role has Glue permissions (GetCatalog, GetDatabase, GetTable, etc.) | ✅ | Policy attached |
| IAM role has S3 Tables permissions | ✅ | s3tables:* granted |
| IAM role has Lake Formation permissions | ✅ | lakeformation:GetDataAccess |
| Lake Formation AllowFullTableExternalDataAccess = true | ✅ | Set for testing |
| Glue REST endpoint responds to Snowflake | ✅ | DESCRIBE returns credentials |
| Credential vending returns storage credentials | ❌ | This is the failure point |
| SYSTEM$LIST_NAMESPACES_FROM_CATALOG | TBD | Not yet tested |
| SYSTEM$LIST_ICEBERG_TABLES_FROM_CATALOG | TBD | Not yet tested |

## Debugging Steps

```sql
-- Step 1: Verify catalog integration
DESCRIBE CATALOG INTEGRATION s3tables_glue_rest_int;

-- Step 2: List namespaces (if supported)
SELECT SYSTEM$LIST_NAMESPACES_FROM_CATALOG('s3tables_glue_rest_int');

-- Step 3: List tables
SELECT SYSTEM$LIST_ICEBERG_TABLES_FROM_CATALOG('s3tables_glue_rest_int', 'metadata');

-- Step 4: Attempt table creation with verbose error
CREATE ICEBERG TABLE test_metadata
  CATALOG = 's3tables_glue_rest_int'
  CATALOG_TABLE_NAME = 'unstructured_files';
```

## Hypothesis: Failure Point

**Confirmed 2026-06-01**: The AWS Glue Iceberg REST endpoint does NOT implement the Iceberg REST `/credentials` endpoint. Calling `POST /v1/.../credentials` returns `UnknownOperationException`. The `X-Iceberg-Access-Delegation: vended-credentials` header in `loadTable` also does not return storage credentials in the response config.

**Snowflake's expected credential format (officially confirmed by Snowflake Support 2026-06-02, Case #01364260)**:
When `ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS`, Snowflake expects the Iceberg REST `loadTable` response to include the standard Apache Iceberg credential fields within the response configuration map:
- `s3.access-key-id` (required)
- `s3.secret-access-key` (required)
- `s3.session-token` (required)
- `s3.session-token-expires-at-ms` (optional)

Error 004174 occurs when these fields are absent from the response.

**Snowflake Support's progression analysis (confirmed 2026-06-02)**:
The error progression visible from the account confirms:
1. 004139 (Lake Formation permission errors) → metadata access blocked
2. 004174 (credential retrieval failure) → metadata resolved, but no storage credentials returned

This proves: Glue REST is reachable, catalog and table resolved successfully, request progresses beyond metadata auth, but Snowflake cannot obtain usable credential payload.

This is the root cause of Snowflake's "Failed to retrieve credentials from the Catalog" error:
- Snowflake's `VENDED_CREDENTIALS` mode expects the REST catalog to return short-lived storage credentials
- Glue REST uses SigV4 authentication instead — the caller must have its own IAM credentials to access S3 data
- This is a fundamental incompatibility between Snowflake's vended credentials model and Glue REST's SigV4 model

**Implications**:
1. Snowflake cannot use `VENDED_CREDENTIALS` with Glue REST for S3 Tables (confirmed limitation)
2. Trino/Spark can access Glue REST because they use their own IAM credentials (SigV4)
3. Snowflake may need to use an External Volume (with its own storage credentials) instead of vended credentials
4. This should be reported to both Snowflake and AWS support as a confirmed interoperability gap

**AWS Support clarification (2026-06-02)**:
Lake Formation **does** support credential vending for S3 Tables — but through its proprietary mechanism (`GetTemporaryGlueTableCredentials` / `lakeformation:GetDataAccess`), NOT the standard Iceberg REST `/credentials` API.

- **SigV4 clients (PyIceberg, EMR Spark, Athena, Redshift)**: Lake Formation credential vending works transparently. IAM role needs `lakeformation:GetDataAccess` + Lake Formation Application Integration enabled. No direct S3 permissions needed.
- **Snowflake**: Expects standard Iceberg REST `/credentials` response. Cannot call `lakeformation:GetDataAccess` directly. This proprietary mechanism is invisible to Snowflake.
- **Standard Glue tables (non-S3 Tables)**: Snowflake + Lake Formation works in **public preview** with `ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS` [ref: Snowflake docs]. However, this does NOT extend to S3 Tables accessed via `s3tablescatalog`.
- **Feature request**: Submitted to AWS Glue/Lake Formation team for standard Iceberg REST `/credentials` endpoint implementation.

**Strategic paths for Snowflake + S3 Tables**:
| Timeline | Path | Description |
|---|---|---|
| Now | Metadata sync | PyIceberg export → S3 → Snowflake COPY INTO |
| Now | External Stage + TO_FILE | File AI analysis (confirmed working) |
| Medium-term | ETL to standard Glue table | S3 Tables → standard Glue Iceberg on S3 → Snowflake VENDED_CREDENTIALS (public preview + Lake Formation) |
| Long-term | AWS implements `/credentials` | Feature request submitted; no public ETA |

**Previous hypothesis** (now confirmed):
~~1. Glue REST `/v1/credentials` endpoint not returning expected format for S3 Tables federated catalog~~
→ CONFIRMED: The endpoint does not exist (UnknownOperationException)

## Alternative Paths Identified by Snowflake Support

### 1. Object Store Catalog Integration (Read-only, no credential vending needed)

Snowflake can read the Iceberg table directly from the metadata file using an External Volume, bypassing the REST catalog credential vending entirely.

```sql
-- Create Object Store catalog integration
CREATE OR REPLACE CATALOG INTEGRATION iceberg_object_store_int
  CATALOG_SOURCE = OBJECT_STORE
  TABLE_FORMAT = ICEBERG
  ENABLED = TRUE;

-- Create Iceberg table pointing to metadata file directly
CREATE ICEBERG TABLE FSXN_LAKEHOUSE.PUBLIC.s3tables_metadata
  EXTERNAL_VOLUME = 's3tables_metadata_vol'
  CATALOG = 'iceberg_object_store_int'
  METADATA_FILE_PATH = 'metadata/00001-fcb8fb99-20cb-4b72-84bb-012d2c85891c.metadata.json';
```

**Limitations**:
- Read-only access
- Requires manual refresh when metadata file location changes
- Must know the current metadata file path (changes on each commit)

**Challenge for S3 Tables**: The S3 Tables internal bucket path format may require additional investigation to determine if Snowflake's External Volume can resolve the internal S3 paths correctly.

### 2. Next Steps for Resolution

| Action | Owner | Status |
|---|---|---|
| Provide loadTable response evidence to Snowflake | Customer (us) | ✅ Done (2026-06-02) |
| Run SYSTEM$VERIFY_CATALOG_INTEGRATION | Customer (us) | Pending |
| Evaluate Object Store catalog as workaround | Customer (us) | Pending |
| Determine if credential vending will be added to Glue REST | AWS | Open (case 178031980800349) |
| Snowflake product team tracking | Snowflake | Asked (2026-06-02) |

## References

- [Snowflake: Vended credentials for Iceberg](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-vended-credentials)
- [Snowflake: REST catalog integration](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-rest)
- [Snowflake: How credentials vending works](https://www.snowflake.com/en/engineering-blog/iceberg-catalog-credentials/)
- [AWS: S3 Tables + Glue REST endpoint](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-glue-endpoint.html)

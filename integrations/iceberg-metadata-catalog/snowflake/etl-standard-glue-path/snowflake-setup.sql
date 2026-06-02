-- =============================================================================
-- Snowflake Setup: Standard Glue Iceberg + VENDED_CREDENTIALS (Public Preview)
-- =============================================================================
-- Purpose: Configure Snowflake to access the mirrored Iceberg table via
--          standard Glue Data Catalog with Lake Formation credential vending.
-- =============================================================================

-- Step 1: Create CATALOG INTEGRATION pointing to standard Glue (NOT s3tablescatalog)
-- Key difference: CATALOG_NAME uses just the account ID, not s3tablescatalog path
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

-- Step 2: Get External ID for IAM trust policy update
DESCRIBE CATALOG INTEGRATION glue_standard_mirror_int;
-- Record: API_AWS_EXTERNAL_ID → update IAM trust policy

-- Step 3: Verify catalog connectivity
SELECT SYSTEM$VERIFY_CATALOG_INTEGRATION('GLUE_STANDARD_MIRROR_INT');

-- Step 4: List namespaces (should show metadata_mirror)
SELECT SYSTEM$LIST_NAMESPACES_FROM_CATALOG('GLUE_STANDARD_MIRROR_INT');

-- Step 5: List tables (should show unstructured_files)
SELECT SYSTEM$LIST_ICEBERG_TABLES_FROM_CATALOG('GLUE_STANDARD_MIRROR_INT', 'metadata_mirror');

-- Step 6: Create Iceberg table
CREATE OR REPLACE ICEBERG TABLE FSXN_LAKEHOUSE.PUBLIC.metadata_mirror_test
  CATALOG = 'glue_standard_mirror_int'
  CATALOG_TABLE_NAME = 'unstructured_files'
  AUTO_REFRESH = TRUE;

-- Step 7: Query!
SELECT * FROM FSXN_LAKEHOUSE.PUBLIC.metadata_mirror_test LIMIT 10;

-- Step 8: Validate governance (if Lake Formation permissions are set)
SELECT ai_classification, COUNT(*) as file_count
FROM FSXN_LAKEHOUSE.PUBLIC.metadata_mirror_test
GROUP BY ai_classification
ORDER BY file_count DESC;

-- Step 9: Test time travel (if supported via this path)
SELECT COUNT(*) FROM FSXN_LAKEHOUSE.PUBLIC.metadata_mirror_test
  AT (OFFSET => -3600);

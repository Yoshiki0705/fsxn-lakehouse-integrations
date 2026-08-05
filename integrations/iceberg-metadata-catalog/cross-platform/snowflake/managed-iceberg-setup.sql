-- =============================================================================
-- Snowflake Managed Iceberg Table + Horizon Catalog Setup
-- =============================================================================
-- Creates a Managed Iceberg Table from FSx for ONTAP S3 AP metadata and configures
-- Horizon Catalog for external engine access with governance enforcement.
--
-- Architecture:
--   FSx for ONTAP → S3 AP Stage → COPY INTO → Managed Iceberg Table
--                                                    ↓
--                                          Horizon Iceberg REST Catalog
--                                                    ↓
--                                          External engines (Spark, Databricks)
--                                          with Row Access Policy enforcement
--
-- Prerequisites:
--   - Snowflake account with Iceberg Tables enabled
--   - Storage Integration for FSx for ONTAP S3 AP (existing)
--   - External volume for Managed Iceberg Table output
--   - Snowflake account: MH89262 (CVDRQJT, ap-northeast-1)
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Step 1: Create External Volume for Managed Iceberg Table storage
-- ---------------------------------------------------------------------------
CREATE OR REPLACE EXTERNAL VOLUME fsxn_metadata_iceberg_vol
  STORAGE_LOCATIONS = (
    (
      NAME = 'metadata-iceberg-s3'
      STORAGE_BASE_URL = 's3://fsxn-metadata-iceberg-output/'
      STORAGE_PROVIDER = 'S3'
      STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/snowflake-iceberg-metadata-role'
      STORAGE_AWS_EXTERNAL_ID = 'snowflake_external_id'
    )
  );

-- ---------------------------------------------------------------------------
-- Step 2: Create Managed Iceberg Table (metadata catalog)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE ICEBERG TABLE fsxn_metadata_catalog (
  file_id STRING,
  file_path STRING,
  file_name STRING,
  file_type STRING,
  file_size NUMBER(20,0),
  created_at TIMESTAMP_NTZ,
  modified_at TIMESTAMP_NTZ,
  source_volume STRING,
  access_point_arn STRING,
  tags OBJECT,
  classification STRING,
  confidence_score FLOAT,
  sensitivity_level STRING,
  summary STRING,
  has_pii BOOLEAN,
  enrichment_status STRING,
  enriched_at TIMESTAMP_NTZ,
  is_deleted BOOLEAN,
  department_tag STRING  -- Denormalized for Row Access Policy
)
  CATALOG = 'SNOWFLAKE'
  EXTERNAL_VOLUME = 'fsxn_metadata_iceberg_vol'
  BASE_LOCATION = 'metadata_catalog/'
  CATALOG_SYNC = 'FSXN_METADATA_INTEGRATION';

-- ---------------------------------------------------------------------------
-- Step 3: Load metadata from S3 Tables (via external stage or direct)
-- ---------------------------------------------------------------------------
-- Option A: If S3 Tables data is accessible via Parquet export
-- COPY INTO fsxn_metadata_catalog
--   FROM @s3_tables_export_stage/metadata/
--   FILE_FORMAT = (TYPE = PARQUET)
--   MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

-- Option B: Insert from existing metadata (if already in Snowflake)
-- INSERT INTO fsxn_metadata_catalog
-- SELECT * FROM existing_metadata_view;

-- ---------------------------------------------------------------------------
-- Step 4: Create Row Access Policy (department-based governance)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE ROW ACCESS POLICY metadata_department_policy
  AS (department_tag STRING)
  RETURNS BOOLEAN ->
    -- Admins see everything
    CURRENT_ROLE() IN ('ACCOUNTADMIN', 'METADATA_ADMIN_ROLE')
    -- Users see only their department's files
    OR department_tag = CURRENT_SESSION_CONTEXT('DEPARTMENT')
    -- Public files visible to all
    OR department_tag = 'public';

-- Apply to the Managed Iceberg Table
ALTER ICEBERG TABLE fsxn_metadata_catalog
  ADD ROW ACCESS POLICY metadata_department_policy ON (department_tag);

-- ---------------------------------------------------------------------------
-- Step 5: Create Dynamic Masking Policy (hide file paths for restricted users)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE MASKING POLICY mask_file_path
  AS (val STRING)
  RETURNS STRING ->
    CASE
      WHEN CURRENT_ROLE() IN ('ACCOUNTADMIN', 'METADATA_ADMIN_ROLE', 'DATA_ENGINEER_ROLE')
        THEN val
      ELSE '***RESTRICTED***'
    END;

ALTER ICEBERG TABLE fsxn_metadata_catalog
  MODIFY COLUMN file_path SET MASKING POLICY mask_file_path;

-- ---------------------------------------------------------------------------
-- Step 6: Configure Catalog Integration for External Engine Access
-- ---------------------------------------------------------------------------
-- This enables Databricks/Spark to read the Managed Iceberg Table
-- via Horizon Iceberg REST Catalog with governance enforcement.

CREATE OR REPLACE CATALOG INTEGRATION fsxn_metadata_integration
  CATALOG_SOURCE = OBJECT_STORE
  TABLE_FORMAT = ICEBERG
  ENABLED = TRUE;

-- ---------------------------------------------------------------------------
-- Step 7: Cortex Search Service for Natural Language Discovery
-- ---------------------------------------------------------------------------
CREATE OR REPLACE CORTEX SEARCH SERVICE fsxn_metadata_search
  ON fsxn_metadata_catalog
  WAREHOUSE = 'COMPUTE_WH'
  TARGET_LAG = '1 hour'
  ATTRIBUTES = 'file_type, classification, sensitivity_level, department_tag'
  COLUMNS = 'summary, file_name'
  AS (
    SELECT
      file_id,
      file_path,
      file_name,
      file_type,
      classification,
      sensitivity_level,
      department_tag,
      summary
    FROM fsxn_metadata_catalog
    WHERE is_deleted = FALSE
      AND enrichment_status = 'completed'
  );

-- ---------------------------------------------------------------------------
-- Step 8: Verify Setup
-- ---------------------------------------------------------------------------

-- Check table contents
SELECT COUNT(*) AS total_records,
       COUNT(CASE WHEN enrichment_status = 'completed' THEN 1 END) AS enriched,
       COUNT(CASE WHEN has_pii = TRUE THEN 1 END) AS pii_files
FROM fsxn_metadata_catalog
WHERE is_deleted = FALSE;

-- Test Row Access Policy (switch role to verify)
USE ROLE DATA_ANALYST_ROLE;
SELECT COUNT(*) FROM fsxn_metadata_catalog;  -- Should only see own department

-- Test Cortex Search
SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
  'fsxn_metadata_search',
  '{"query": "engineering drawings for pump design 2025", "columns": ["file_name", "file_path", "classification"], "limit": 5}'
);

-- Check Horizon Catalog external access audit
SELECT *
FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_REQUEST_HISTORY
WHERE TABLE_CATALOG_NAME = 'FSXN_METADATA_CATALOG'
ORDER BY REQUEST_TIMESTAMP DESC
LIMIT 20;

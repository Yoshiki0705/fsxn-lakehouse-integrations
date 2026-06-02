-- =============================================================================
-- Snowflake Metadata Sync Example
-- =============================================================================
-- Syncs curated metadata from S3 (exported from Iceberg) into Snowflake
-- for dashboards, Cortex Search, and governance reporting.
--
-- Prerequisites:
--   1. Storage integration with S3 bucket access
--   2. External stage pointing to exported metadata
--   3. Target Snowflake table
--
-- Placeholders to replace:
--   <ACCOUNT_ID>  → Your AWS account ID (12 digits)
--   <REGION>      → Your AWS region (e.g., ap-northeast-1)
--   COMPUTE_WH    → Your Snowflake warehouse name
--
-- Pattern: PyIceberg export → S3 (Parquet/CSV) → Snowflake Stage → COPY/MERGE
-- =============================================================================

-- =========================================================================
-- Step 1: Create storage integration (one-time, requires ACCOUNTADMIN)
-- =========================================================================
CREATE OR REPLACE STORAGE INTEGRATION metadata_sync_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/snowflake-metadata-sync-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://your-metadata-export-bucket/exports/');

-- Verify and get external ID for IAM trust policy
DESC STORAGE INTEGRATION metadata_sync_integration;

-- =========================================================================
-- Step 2: Create external stage
-- =========================================================================
CREATE OR REPLACE STAGE metadata_export_stage
  STORAGE_INTEGRATION = metadata_sync_integration
  URL = 's3://your-metadata-export-bucket/exports/latest/'
  FILE_FORMAT = (TYPE = 'PARQUET');

-- Verify files are visible
LIST @metadata_export_stage;

-- =========================================================================
-- Step 3: Create target table (curated metadata — no raw paths, no embeddings)
-- =========================================================================
CREATE OR REPLACE TABLE metadata_catalog (
  file_id           VARCHAR(64) NOT NULL,
  file_name         VARCHAR(512),
  file_type         VARCHAR(128),
  file_size         NUMBER(20),
  classification    VARCHAR(256),
  confidence_score  FLOAT,
  summary           VARCHAR(4096),
  sensitivity_level VARCHAR(32),
  tenant_id         VARCHAR(128),
  has_pii           BOOLEAN,
  pii_status        VARCHAR(32),
  path_classification VARCHAR(32),
  enrichment_status VARCHAR(32),
  change_type       VARCHAR(32),
  is_deleted        BOOLEAN,
  scan_run_id       VARCHAR(64),
  created_at        TIMESTAMP_NTZ,
  modified_at       TIMESTAMP_NTZ,
  synced_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- =========================================================================
-- Step 4: Initial load (COPY INTO)
-- =========================================================================
COPY INTO metadata_catalog (
  file_id, file_name, file_type, file_size,
  classification, confidence_score, summary,
  sensitivity_level, tenant_id, has_pii, pii_status,
  path_classification, enrichment_status, change_type,
  is_deleted, scan_run_id, created_at, modified_at
)
FROM @metadata_export_stage
FILE_FORMAT = (TYPE = 'PARQUET')
MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;

-- =========================================================================
-- Step 5: Incremental sync (MERGE INTO — idempotent)
-- =========================================================================
MERGE INTO metadata_catalog t
USING (
  SELECT
    $1:file_id::VARCHAR AS file_id,
    $1:file_name::VARCHAR AS file_name,
    $1:file_type::VARCHAR AS file_type,
    $1:file_size::NUMBER AS file_size,
    $1:classification::VARCHAR AS classification,
    $1:confidence_score::FLOAT AS confidence_score,
    $1:summary::VARCHAR AS summary,
    $1:sensitivity_level::VARCHAR AS sensitivity_level,
    $1:tenant_id::VARCHAR AS tenant_id,
    $1:has_pii::BOOLEAN AS has_pii,
    $1:pii_status::VARCHAR AS pii_status,
    $1:path_classification::VARCHAR AS path_classification,
    $1:enrichment_status::VARCHAR AS enrichment_status,
    $1:change_type::VARCHAR AS change_type,
    $1:is_deleted::BOOLEAN AS is_deleted,
    $1:scan_run_id::VARCHAR AS scan_run_id,
    $1:created_at::TIMESTAMP_NTZ AS created_at,
    $1:modified_at::TIMESTAMP_NTZ AS modified_at
  FROM @metadata_export_stage
) s
ON t.file_id = s.file_id
WHEN MATCHED AND s.modified_at > t.modified_at THEN UPDATE SET
  t.file_name = s.file_name,
  t.file_type = s.file_type,
  t.file_size = s.file_size,
  t.classification = s.classification,
  t.confidence_score = s.confidence_score,
  t.summary = s.summary,
  t.sensitivity_level = s.sensitivity_level,
  t.tenant_id = s.tenant_id,
  t.has_pii = s.has_pii,
  t.pii_status = s.pii_status,
  t.path_classification = s.path_classification,
  t.enrichment_status = s.enrichment_status,
  t.change_type = s.change_type,
  t.is_deleted = s.is_deleted,
  t.scan_run_id = s.scan_run_id,
  t.modified_at = s.modified_at,
  t.synced_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
  file_id, file_name, file_type, file_size,
  classification, confidence_score, summary,
  sensitivity_level, tenant_id, has_pii, pii_status,
  path_classification, enrichment_status, change_type,
  is_deleted, scan_run_id, created_at, modified_at, synced_at
) VALUES (
  s.file_id, s.file_name, s.file_type, s.file_size,
  s.classification, s.confidence_score, s.summary,
  s.sensitivity_level, s.tenant_id, s.has_pii, s.pii_status,
  s.path_classification, s.enrichment_status, s.change_type,
  s.is_deleted, s.scan_run_id, s.created_at, s.modified_at, CURRENT_TIMESTAMP()
);

-- =========================================================================
-- Step 6: Automate with Snowflake Task (hourly sync)
-- =========================================================================
CREATE OR REPLACE TASK metadata_sync_task
  WAREHOUSE = 'COMPUTE_WH'
  SCHEDULE = 'USING CRON 0 * * * * Asia/Tokyo'
  COMMENT = 'Hourly metadata sync from S3 Tables export'
AS
  MERGE INTO metadata_catalog t
  USING (
    SELECT * FROM @metadata_export_stage (FILE_FORMAT => 'PARQUET')
  ) s
  ON t.file_id = s.$1:file_id::VARCHAR
  WHEN MATCHED AND s.$1:modified_at::TIMESTAMP_NTZ > t.modified_at THEN UPDATE SET
    t.classification = s.$1:classification::VARCHAR,
    t.confidence_score = s.$1:confidence_score::FLOAT,
    t.summary = s.$1:summary::VARCHAR,
    t.enrichment_status = s.$1:enrichment_status::VARCHAR,
    t.is_deleted = s.$1:is_deleted::BOOLEAN,
    t.modified_at = s.$1:modified_at::TIMESTAMP_NTZ,
    t.synced_at = CURRENT_TIMESTAMP()
  WHEN NOT MATCHED THEN INSERT (file_id, file_name, file_type, classification, modified_at, synced_at)
    VALUES (s.$1:file_id, s.$1:file_name, s.$1:file_type, s.$1:classification, s.$1:modified_at, CURRENT_TIMESTAMP());

-- Enable the task
ALTER TASK metadata_sync_task RESUME;

-- =========================================================================
-- Step 7: Governance (Row Access Policy + Masking)
-- =========================================================================

-- Row Access Policy: restrict by tenant
CREATE OR REPLACE ROW ACCESS POLICY tenant_filter AS (tenant_id VARCHAR)
  RETURNS BOOLEAN ->
    CURRENT_ROLE() IN ('SYSADMIN', 'SECURITYADMIN')
    OR tenant_id = CURRENT_SESSION()::VARCHAR;

ALTER TABLE metadata_catalog ADD ROW ACCESS POLICY tenant_filter ON (tenant_id);

-- Dynamic Masking: hide summary for PII-containing files
CREATE OR REPLACE MASKING POLICY pii_summary_mask AS (val VARCHAR)
  RETURNS VARCHAR ->
    CASE
      WHEN CURRENT_ROLE() IN ('SYSADMIN', 'SECURITY_TEAM') THEN val
      ELSE '*** REDACTED (contains PII) ***'
    END;

ALTER TABLE metadata_catalog MODIFY COLUMN summary SET MASKING POLICY pii_summary_mask;

-- =========================================================================
-- Step 8: Cortex Search (optional — for natural language search)
-- =========================================================================
CREATE OR REPLACE CORTEX SEARCH SERVICE metadata_search
  ON summary
  ATTRIBUTES file_name, file_type, classification, sensitivity_level
  WAREHOUSE = 'COMPUTE_WH'
  TARGET_LAG = '1 hour'
  AS (
    SELECT file_id, file_name, file_type, classification,
           sensitivity_level, summary, confidence_score
    FROM metadata_catalog
    WHERE is_deleted = FALSE
      AND enrichment_status = 'completed'
      AND summary IS NOT NULL
  );

-- Query Cortex Search
SELECT *
FROM TABLE(
  SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'metadata_search',
    '{"query": "find invoice documents", "columns": ["file_name", "classification", "summary"], "limit": 5}'
  )
);

-- =========================================================================
-- Step 9: Sample queries for dashboards
-- =========================================================================

-- File inventory by classification
SELECT classification, COUNT(*) AS file_count,
       SUM(file_size) / (1024*1024*1024) AS total_gb
FROM metadata_catalog
WHERE is_deleted = FALSE
GROUP BY classification
ORDER BY file_count DESC;

-- PII coverage report
SELECT
  COUNT(*) AS total_files,
  COUNT_IF(has_pii = TRUE) AS pii_files,
  COUNT_IF(pii_status = 'redacted') AS redacted_files,
  ROUND(COUNT_IF(has_pii IS NOT NULL) * 100.0 / COUNT(*), 1) AS scan_coverage_pct
FROM metadata_catalog
WHERE is_deleted = FALSE;

-- Enrichment backlog
SELECT enrichment_status, COUNT(*) AS count
FROM metadata_catalog
WHERE is_deleted = FALSE
GROUP BY enrichment_status;

-- Recent changes
SELECT file_name, change_type, modified_at
FROM metadata_catalog
WHERE modified_at > DATEADD('day', -7, CURRENT_TIMESTAMP())
ORDER BY modified_at DESC
LIMIT 20;

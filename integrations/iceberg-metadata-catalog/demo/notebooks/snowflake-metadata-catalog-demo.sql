-- =============================================================================
-- Iceberg Metadata Catalog — Snowflake Demo Worksheet
-- =============================================================================
-- This worksheet demonstrates the Snowflake path for accessing
-- the FSx for ONTAP metadata catalog.
--
-- Architecture:
--   FSx for ONTAP → S3 AP Stage → COPY INTO → Managed Iceberg Table
--                                                    ↓
--                                          Cortex AI (classification)
--                                                    ↓
--                                          Horizon Catalog (governance)
--
-- Prerequisites:
--   - Snowflake account with Iceberg Tables enabled
--   - Storage Integration for FSx S3 AP (FSXN_VERIFICATION_INTEGRATION)
--   - External Volume (s3tables_metadata_vol) — already created
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 1: Setup — Use existing database and verify access
-- ─────────────────────────────────────────────────────────────────────────────

USE ROLE ACCOUNTADMIN;
USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA PUBLIC;
USE WAREHOUSE COMPUTE_WH;

-- Verify External Volume exists
SHOW EXTERNAL VOLUMES;
-- Expected: s3tables_metadata_vol

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 2: Create Managed Iceberg Table for metadata
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE ICEBERG TABLE metadata_catalog (
    file_id STRING,
    file_name STRING,
    file_path STRING,
    file_type STRING,
    file_size NUMBER,
    classification STRING,
    confidence_score FLOAT,
    summary STRING,
    sensitivity_level STRING,
    has_pii BOOLEAN,
    enrichment_status STRING,
    created_at TIMESTAMP_NTZ,
    department_tag STRING
)
    CATALOG = 'SNOWFLAKE'
    EXTERNAL_VOLUME = 's3tables_metadata_vol'
    BASE_LOCATION = 'snowflake_metadata_demo/';

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 3: Load sample metadata (simulating COPY INTO from S3 Tables export)
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO metadata_catalog VALUES
    ('id-001', 'invoice_sample.png', 's3://ap-alias/media/documents/invoice_sample.png', 'image/png', 11338, 'Invoice', 0.9, 'Invoice #INV-2026-0524, Customer: Acme Corp, Amount: USD 1,234.56, Status: PAID', 'internal', FALSE, 'completed', '2026-05-24 23:17:29', 'finance'),
    ('id-002', 'product_inspection.png', 's3://ap-alias/media/images/product_inspection.png', 'image/png', 7180, 'product_photo', 0.85, 'Product quality inspection image showing manufacturing line output', 'internal', FALSE, 'completed', '2026-05-24 23:17:28', 'manufacturing'),
    ('id-003', 'sensor_dashboard.png', 's3://ap-alias/media/images/sensor_dashboard.png', 'image/png', 9380, 'screenshot', 0.75, 'IoT sensor monitoring dashboard with temperature and pressure readings', 'internal', FALSE, 'completed', '2026-05-24 23:17:18', 'engineering'),
    ('id-004', 'employee_record.txt', 's3://ap-alias/media/documents/pii-test-document.txt', 'text/plain', 255, 'correspondence', 0.6, 'Employee record containing personal information', 'confidential', TRUE, 'completed', '2026-05-31 14:30:00', 'hr'),
    ('id-005', 'sensor_data_large.parquet', 's3://ap-alias/benchmark/sensor_data_large.parquet', 'application/x-parquet', 108002572, 'other', 0.5, 'Large IoT sensor dataset for analytics', 'internal', FALSE, 'completed', '2026-05-22 23:07:51', 'engineering');

SELECT '✅ 5 sample records loaded' AS status;

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 4: Query metadata (same patterns as Athena)
-- ─────────────────────────────────────────────────────────────────────────────

-- File type distribution
SELECT file_type, COUNT(*) AS count, SUM(file_size) AS total_bytes
FROM metadata_catalog
GROUP BY file_type
ORDER BY total_bytes DESC;

-- AI classification results
SELECT file_name, classification, confidence_score, summary
FROM metadata_catalog
WHERE enrichment_status = 'completed'
ORDER BY confidence_score DESC;

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 5: Cortex AI — Classify directly from Snowflake
-- ─────────────────────────────────────────────────────────────────────────────

-- Use Cortex COMPLETE to re-classify based on summary
SELECT
    file_name,
    classification AS original_classification,
    SNOWFLAKE.CORTEX.COMPLETE('mistral-large2',
        'Classify this file into one category (invoice, report, image, data, other): ' || summary
    ) AS cortex_classification
FROM metadata_catalog
WHERE enrichment_status = 'completed'
LIMIT 3;

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 6: Governance — Row Access Policy (Horizon Catalog)
-- ─────────────────────────────────────────────────────────────────────────────

-- Create Row Access Policy (department-based)
CREATE OR REPLACE ROW ACCESS POLICY metadata_dept_policy
    AS (dept STRING) RETURNS BOOLEAN ->
        CURRENT_ROLE() IN ('ACCOUNTADMIN')
        OR dept = 'public'
        OR dept = COALESCE(CURRENT_SESSION_CONTEXT('DEPARTMENT'), 'all');

-- Apply to metadata table
ALTER ICEBERG TABLE metadata_catalog
    ADD ROW ACCESS POLICY metadata_dept_policy ON (department_tag);

-- Test: All rows visible as ACCOUNTADMIN
SELECT file_name, department_tag FROM metadata_catalog;

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 7: PII Detection — Find sensitive files
-- ─────────────────────────────────────────────────────────────────────────────

SELECT
    file_name,
    sensitivity_level,
    has_pii,
    CASE WHEN has_pii THEN '🔒 Requires anonymization' ELSE '✅ Safe' END AS status
FROM metadata_catalog
ORDER BY has_pii DESC, sensitivity_level DESC;

-- ─────────────────────────────────────────────────────────────────────────────
-- Step 8: Cortex Search — Natural Language Discovery (if available)
-- ─────────────────────────────────────────────────────────────────────────────

-- Note: Cortex Search requires a service to be created first.
-- Uncomment below after creating the service:

-- CREATE OR REPLACE CORTEX SEARCH SERVICE metadata_search_demo
--     ON metadata_catalog
--     WAREHOUSE = 'COMPUTE_WH'
--     TARGET_LAG = '1 hour'
--     ATTRIBUTES = 'file_type, classification, department_tag'
--     COLUMNS = 'summary, file_name'
--     AS (
--         SELECT file_id, file_name, file_type, classification,
--                department_tag, summary
--         FROM metadata_catalog
--         WHERE enrichment_status = 'completed'
--     );

-- SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
--     'metadata_search_demo',
--     '{"query": "find invoice documents from finance department", "columns": ["file_name", "classification"], "limit": 5}'
-- );

-- ─────────────────────────────────────────────────────────────────────────────
-- Cleanup (optional)
-- ─────────────────────────────────────────────────────────────────────────────

-- ALTER ICEBERG TABLE metadata_catalog DROP ROW ACCESS POLICY metadata_dept_policy;
-- DROP TABLE IF EXISTS metadata_catalog;
-- DROP ROW ACCESS POLICY IF EXISTS metadata_dept_policy;

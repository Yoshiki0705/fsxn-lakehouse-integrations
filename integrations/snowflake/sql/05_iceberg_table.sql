-- =============================================================================
-- 05 - Iceberg Table on FSx for ONTAP (Snowflake-Managed Catalog)
-- =============================================================================
--
-- Purpose:
--   Creates an Iceberg Table (PRODUCTS_ICEBERG) using Snowflake-managed catalog
--   with FSx for ONTAP as the underlying storage via S3 Access Point. Demonstrates full
--   DML support (INSERT, UPDATE, DELETE) and Time Travel capabilities.
--
-- Prerequisites:
--   - 01_storage_integration.sql executed (Storage Integration created)
--   - 02_external_stage.sql executed (Database and schemas created)
--   - Two-phase trust setup completed
--   - S3 Access Point alias available (from CloudFormation output)
--
-- Snowflake Iceberg Table Modes:
--   1. Snowflake-managed catalog (this script) — Snowflake manages metadata
--   2. External catalog (e.g., AWS Glue) — external engine manages metadata
--
-- Key Difference from External Tables:
--   - External Tables: read-only, metadata refresh required
--   - Iceberg Tables: full DML (INSERT/UPDATE/DELETE/MERGE), Time Travel
--
-- IMPORTANT: Snowflake Iceberg Tables require an EXTERNAL VOLUME (not just a
-- stage). The External Volume references the Storage Integration and defines
-- the S3 location where Iceberg data and metadata files are stored.
--
-- =============================================================================

-- =============================================================================
-- 1. Role & Context Setup
-- =============================================================================
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;
USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA SILVER;

-- =============================================================================
-- 2. Create External Volume for Iceberg Tables
-- =============================================================================
-- Iceberg Tables in Snowflake require an EXTERNAL VOLUME (not a stage).
-- The External Volume defines where Iceberg data and metadata files are stored.
-- It references the same Storage Integration used by External Stages.
--
-- Replace <AP_ALIAS> with your S3 Access Point alias from CloudFormation output.
-- Replace <IAM_ROLE_ARN> with the IAMRoleArn output from CloudFormation.
--
-- NOTE: CREATE EXTERNAL VOLUME requires ACCOUNTADMIN or a role with
-- CREATE EXTERNAL VOLUME privilege.
USE ROLE ACCOUNTADMIN;

CREATE OR REPLACE EXTERNAL VOLUME fsxn_iceberg_volume
  STORAGE_LOCATIONS = (
    (
      NAME = 'fsxn-silver-location'
      STORAGE_BASE_URL = 's3://<AP_ALIAS>/silver/'
      STORAGE_PROVIDER = 'S3'
      STORAGE_AWS_ROLE_ARN = '<IAM_ROLE_ARN>'
    )
  )
  COMMENT = 'External Volume for Iceberg Tables on FSx for ONTAP silver layer via S3 Access Point';

-- Grant USAGE to SYSADMIN so it can create Iceberg Tables referencing this volume
GRANT USAGE ON EXTERNAL VOLUME fsxn_iceberg_volume TO ROLE SYSADMIN;

-- Verify External Volume configuration
DESCRIBE EXTERNAL VOLUME fsxn_iceberg_volume;

-- Switch back to SYSADMIN for table operations
USE ROLE SYSADMIN;
USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA SILVER;

-- =============================================================================
-- 3. Create Iceberg Table: PRODUCTS_ICEBERG
-- =============================================================================
-- Snowflake-managed catalog: Snowflake manages Iceberg metadata files on FSx for ONTAP.
-- Other engines (Spark, Trino, etc.) can read via the metadata location.
--
-- Columns:
--   product_id   — Unique product identifier (PROD-XXXXXX)
--   name         — Product display name
--   category     — Product category (compute, storage, networking, etc.)
--   price        — Unit price (USD)
--   stock_qty    — Current stock quantity
--   supplier     — Supplier company name
--   updated_at   — Last update timestamp
--   is_active    — Whether product is currently active
--
CREATE OR REPLACE ICEBERG TABLE PRODUCTS_ICEBERG (
  product_id   STRING    NOT NULL,
  name         STRING    NOT NULL,
  category     STRING    NOT NULL,
  price        FLOAT     NOT NULL,
  stock_qty    INT       NOT NULL,
  supplier     STRING    NOT NULL,
  updated_at   TIMESTAMP_NTZ NOT NULL,
  is_active    BOOLEAN   NOT NULL
)
  CATALOG = 'SNOWFLAKE'
  EXTERNAL_VOLUME = 'fsxn_iceberg_volume'
  BASE_LOCATION = 'products_iceberg/'
  COMMENT = 'Product catalog as Iceberg table on FSx for ONTAP — Snowflake-managed catalog, full DML support';

-- =============================================================================
-- 4. INSERT — Populate with 5000 rows of sample product data
-- =============================================================================
-- Uses GENERATOR to produce 5000 rows with realistic product data.
-- Categories include cloud infrastructure product types for demo relevance.
--
-- ⏱ METRIC: Record INSERT latency (start)
-- SET insert_start = CURRENT_TIMESTAMP();

INSERT INTO PRODUCTS_ICEBERG (
  product_id, name, category, price, stock_qty, supplier, updated_at, is_active
)
SELECT
  'PROD-' || LPAD(SEQ4()::STRING, 6, '0') AS product_id,
  CASE MOD(SEQ4(), 8)
    WHEN 0 THEN 'Cloud Server ' || SEQ4()::STRING
    WHEN 1 THEN 'SSD Volume ' || SEQ4()::STRING
    WHEN 2 THEN 'Load Balancer ' || SEQ4()::STRING
    WHEN 3 THEN 'GPU Instance ' || SEQ4()::STRING
    WHEN 4 THEN 'Object Storage ' || SEQ4()::STRING
    WHEN 5 THEN 'VPN Gateway ' || SEQ4()::STRING
    WHEN 6 THEN 'Database Service ' || SEQ4()::STRING
    ELSE 'CDN Endpoint ' || SEQ4()::STRING
  END AS name,
  CASE MOD(SEQ4(), 6)
    WHEN 0 THEN 'compute'
    WHEN 1 THEN 'storage'
    WHEN 2 THEN 'networking'
    WHEN 3 THEN 'database'
    WHEN 4 THEN 'security'
    ELSE 'analytics'
  END AS category,
  ROUND(UNIFORM(10.0, 2000.0, RANDOM()), 2) AS price,
  UNIFORM(0, 5000, RANDOM()) AS stock_qty,
  CASE MOD(SEQ4(), 5)
    WHEN 0 THEN 'NetApp'
    WHEN 1 THEN 'AWS'
    WHEN 2 THEN 'Dell Technologies'
    WHEN 3 THEN 'HPE'
    ELSE 'Cisco'
  END AS supplier,
  DATEADD('second',
    UNIFORM(0, 86400 * 365, RANDOM()),
    '2024-01-01 00:00:00'::TIMESTAMP_NTZ
  ) AS updated_at,
  IFF(UNIFORM(0, 100, RANDOM()) > 15, TRUE, FALSE) AS is_active
FROM TABLE(GENERATOR(ROWCOUNT => 5000));

-- ⏱ METRIC: Record INSERT latency (end)
-- SELECT DATEDIFF('millisecond', $insert_start, CURRENT_TIMESTAMP()) AS insert_latency_ms;

-- Verify row count after INSERT
SELECT COUNT(*) AS total_rows FROM PRODUCTS_ICEBERG;
-- Expected: 5000

-- Quick sample of inserted data
SELECT * FROM PRODUCTS_ICEBERG LIMIT 10;

-- Category distribution
SELECT category, COUNT(*) AS cnt, ROUND(AVG(price), 2) AS avg_price
FROM PRODUCTS_ICEBERG
GROUP BY category
ORDER BY cnt DESC;

-- =============================================================================
-- 5. UPDATE — Apply 10% price discount to 'compute' category
-- =============================================================================
-- Demonstrates Iceberg UPDATE capability (not possible with External Tables).
-- Applies a 10% discount to all products in the 'compute' category.
--
-- ⏱ METRIC: Record UPDATE latency (start)
-- SET update_start = CURRENT_TIMESTAMP();

-- Record pre-update state for comparison
SELECT
  'BEFORE UPDATE' AS phase,
  COUNT(*) AS compute_products,
  ROUND(AVG(price), 2) AS avg_price,
  ROUND(MIN(price), 2) AS min_price,
  ROUND(MAX(price), 2) AS max_price
FROM PRODUCTS_ICEBERG
WHERE category = 'compute';

-- Apply 10% discount to compute category
UPDATE PRODUCTS_ICEBERG
SET
  price = ROUND(price * 0.90, 2),
  updated_at = CURRENT_TIMESTAMP()::TIMESTAMP_NTZ
WHERE category = 'compute';

-- ⏱ METRIC: Record UPDATE latency (end)
-- SELECT DATEDIFF('millisecond', $update_start, CURRENT_TIMESTAMP()) AS update_latency_ms;

-- Verify post-update state
SELECT
  'AFTER UPDATE' AS phase,
  COUNT(*) AS compute_products,
  ROUND(AVG(price), 2) AS avg_price,
  ROUND(MIN(price), 2) AS min_price,
  ROUND(MAX(price), 2) AS max_price
FROM PRODUCTS_ICEBERG
WHERE category = 'compute';

-- =============================================================================
-- 6. DELETE — Remove inactive products
-- =============================================================================
-- Demonstrates Iceberg DELETE capability.
-- Removes all products where is_active = FALSE.
--
-- ⏱ METRIC: Record DELETE latency (start)
-- SET delete_start = CURRENT_TIMESTAMP();

-- Record count of inactive products before deletion
SELECT COUNT(*) AS inactive_products_to_delete
FROM PRODUCTS_ICEBERG
WHERE is_active = FALSE;

-- Delete inactive products
DELETE FROM PRODUCTS_ICEBERG
WHERE is_active = FALSE;

-- ⏱ METRIC: Record DELETE latency (end)
-- SELECT DATEDIFF('millisecond', $delete_start, CURRENT_TIMESTAMP()) AS delete_latency_ms;

-- Verify remaining rows (all should be is_active = TRUE)
SELECT
  COUNT(*) AS remaining_rows,
  COUNT_IF(is_active = TRUE) AS active_count,
  COUNT_IF(is_active = FALSE) AS inactive_count
FROM PRODUCTS_ICEBERG;
-- Expected: inactive_count = 0

-- =============================================================================
-- 7. Time Travel — Query historical state
-- =============================================================================
-- Iceberg Tables support Snowflake Time Travel (default retention: 1 day).
-- Query the table as it existed 5 minutes (300 seconds) ago, before DML changes.
--
-- This demonstrates recovery capability: if an UPDATE or DELETE was incorrect,
-- you can query the previous state and restore data.
--
-- NOTE: Time Travel offset must be within the DATA_RETENTION_TIME_IN_DAYS
-- setting (default 1 day for Standard Edition, up to 90 days for Enterprise).

-- Query table state from 5 minutes ago (before UPDATE/DELETE)
SELECT
  'TIME_TRAVEL (5 min ago)' AS query_type,
  COUNT(*) AS total_rows,
  COUNT_IF(is_active = FALSE) AS inactive_rows,
  ROUND(AVG(CASE WHEN category = 'compute' THEN price END), 2) AS avg_compute_price
FROM PRODUCTS_ICEBERG AT(OFFSET => -300);

-- Compare with current state
SELECT
  'CURRENT' AS query_type,
  COUNT(*) AS total_rows,
  COUNT_IF(is_active = FALSE) AS inactive_rows,
  ROUND(AVG(CASE WHEN category = 'compute' THEN price END), 2) AS avg_compute_price
FROM PRODUCTS_ICEBERG;

-- =============================================================================
-- 8. Iceberg Table Information — Metadata inspection
-- =============================================================================
-- SYSTEM$GET_ICEBERG_TABLE_INFORMATION() returns metadata about the Iceberg
-- table including:
--   - Current snapshot ID
--   - Metadata file location on FSx for ONTAP
--   - Schema information
--   - Table properties
--
-- This is useful for:
--   - Verifying metadata files are stored on FSx for ONTAP (via S3 AP)
--   - Cross-engine access (other engines can read from metadata location)
--   - Debugging Iceberg table state

SELECT SYSTEM$GET_ICEBERG_TABLE_INFORMATION('FSXN_LAKEHOUSE.SILVER.PRODUCTS_ICEBERG')
  AS iceberg_table_info;

-- =============================================================================
-- 9. Summary Metrics
-- =============================================================================
-- Final state summary for verification report
SELECT
  'PRODUCTS_ICEBERG Final State' AS description,
  COUNT(*) AS total_rows,
  COUNT(DISTINCT category) AS categories,
  COUNT(DISTINCT supplier) AS suppliers,
  ROUND(AVG(price), 2) AS avg_price,
  ROUND(SUM(price * stock_qty), 2) AS total_inventory_value
FROM PRODUCTS_ICEBERG;

-- =============================================================================
-- ONTAP Snapshot + Iceberg Complementary Recovery
-- =============================================================================
-- Iceberg Time Travel: Row-level, within Snowflake retention (default 1 day)
-- ONTAP Snapshot: Volume-level, policy-based retention (days/weeks/months)
--
-- Recovery scenarios:
--   1. Bad UPDATE (within 1 day) → Iceberg Time Travel
--   2. Bad UPDATE (older than 1 day) → ONTAP Snapshot + FlexClone
--   3. Table DROP → ONTAP Snapshot restore
--   4. Cross-table consistency → ONTAP Snapshot (all tables at same point)
--
-- The combination of Iceberg Time Travel + ONTAP Snapshots provides
-- comprehensive data protection at both the logical and physical layer.

-- =============================================================================
-- TROUBLESHOOTING
-- =============================================================================
-- If CREATE ICEBERG TABLE fails:
--
-- 1. "External volume does not exist":
--    → Ensure the External Volume was created (Section 2 above)
--    → Verify GRANT USAGE ON EXTERNAL VOLUME was executed
--    → Check: SHOW EXTERNAL VOLUMES;
--
-- 2. "Insufficient privileges":
--    → External Volume creation requires ACCOUNTADMIN
--    → Table creation requires SYSADMIN with USAGE on the volume
--    → Check: SHOW GRANTS ON EXTERNAL VOLUME fsxn_iceberg_volume;
--
-- 3. "Access denied" on INSERT/UPDATE/DELETE:
--    → Storage Integration trust policy may not include write permissions
--    → Verify IAM Role policy allows s3:PutObject, s3:DeleteObject
--    → Check S3 AP policy allows write operations
--
-- 4. Time Travel query fails with "insufficient data retention":
--    → Offset exceeds DATA_RETENTION_TIME_IN_DAYS
--    → For Enterprise Edition: ALTER TABLE SET DATA_RETENTION_TIME_IN_DAYS = 90;
--    → For Standard Edition: maximum 1 day retention
--
-- 5. SYSTEM$GET_ICEBERG_TABLE_INFORMATION returns error:
--    → Table must be a Snowflake-managed Iceberg table
--    → Fully qualified name required: DATABASE.SCHEMA.TABLE
-- =============================================================================

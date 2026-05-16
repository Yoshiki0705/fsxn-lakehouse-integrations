-- =============================================================================
-- 05 - Iceberg Tables on FSxN
-- =============================================================================
-- Creates Iceberg Tables in Snowflake using FSxN as the storage layer.
-- Iceberg provides vendor-neutral ACID tables accessible from multiple engines.
--
-- Snowflake Iceberg Table modes:
--   1. Snowflake-managed catalog (Snowflake manages metadata)
--   2. External catalog (e.g., AWS Glue, Hive Metastore manages metadata)
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA SILVER;

-- =============================================================================
-- Iceberg Table: Snowflake-Managed Catalog
-- =============================================================================
-- Snowflake manages the Iceberg metadata files on FSxN.
-- Other engines can read via the metadata location.

CREATE OR REPLACE ICEBERG TABLE PRODUCTS_ICEBERG
  CATALOG = 'SNOWFLAKE'
  EXTERNAL_VOLUME = 'fsxn_iceberg_volume'
  BASE_LOCATION = 'silver/products_iceberg/'
  COMMENT = 'Product catalog as Iceberg table on FSxN (Snowflake-managed)'
  AS
  SELECT
    'PROD-' || LPAD(SEQ4()::STRING, 6, '0') AS product_id,
    'Product ' || SEQ4()::STRING AS name,
    CASE MOD(SEQ4(), 6)
      WHEN 0 THEN 'electronics'
      WHEN 1 THEN 'clothing'
      WHEN 2 THEN 'home'
      WHEN 3 THEN 'sports'
      WHEN 4 THEN 'books'
      ELSE 'food'
    END AS category,
    ROUND(UNIFORM(5.0, 999.99, RANDOM()), 2) AS price,
    UNIFORM(0, 1000, RANDOM()) AS stock_quantity,
    IFF(UNIFORM(0, 1, RANDOM()) > 0.5, TRUE, FALSE) AS is_active,
    DATEADD('day', UNIFORM(0, 365, RANDOM()), '2024-01-01'::DATE) AS last_updated
  FROM TABLE(GENERATOR(ROWCOUNT => 5000));

-- =============================================================================
-- Verify Iceberg Table
-- =============================================================================
SELECT * FROM PRODUCTS_ICEBERG LIMIT 10;

-- Check Iceberg metadata
SELECT SYSTEM$GET_ICEBERG_TABLE_INFORMATION('FSXN_LAKEHOUSE.SILVER.PRODUCTS_ICEBERG');

-- =============================================================================
-- Iceberg Table: External Catalog (AWS Glue)
-- =============================================================================
-- For tables managed by an external catalog (e.g., Glue Data Catalog).
-- Snowflake reads metadata from the external catalog.

-- Note: Requires Catalog Integration (Snowflake 7.34+)
-- CREATE OR REPLACE CATALOG INTEGRATION glue_catalog_integration
--   CATALOG_SOURCE = GLUE
--   CATALOG_NAMESPACE = 'fsxn_lakehouse'
--   TABLE_FORMAT = ICEBERG
--   GLUE_AWS_ROLE_ARN = '<glue-role-arn>'
--   GLUE_CATALOG_ID = '<aws-account-id>'
--   GLUE_REGION = 'ap-northeast-1'
--   ENABLED = TRUE;

-- CREATE ICEBERG TABLE PRODUCTS_ICEBERG_EXTERNAL
--   EXTERNAL_VOLUME = 'fsxn_iceberg_volume'
--   CATALOG = 'glue_catalog_integration'
--   CATALOG_TABLE_NAME = 'products'
--   COMMENT = 'Iceberg table on FSxN (Glue-managed catalog)';

-- =============================================================================
-- Iceberg DML Operations
-- =============================================================================

-- INSERT
INSERT INTO PRODUCTS_ICEBERG (product_id, name, category, price, stock_quantity, is_active, last_updated)
VALUES ('PROD-999999', 'New Product', 'electronics', 299.99, 50, TRUE, CURRENT_DATE());

-- UPDATE
UPDATE PRODUCTS_ICEBERG
SET price = price * 0.9, last_updated = CURRENT_DATE()
WHERE category = 'electronics' AND is_active = TRUE;

-- DELETE
DELETE FROM PRODUCTS_ICEBERG
WHERE is_active = FALSE AND last_updated < DATEADD('month', -6, CURRENT_DATE());

-- =============================================================================
-- Iceberg Time Travel (Snowflake-managed)
-- =============================================================================

-- Query previous version
-- SELECT * FROM PRODUCTS_ICEBERG AT(OFFSET => -60*5);  -- 5 minutes ago

-- Query at specific timestamp
-- SELECT * FROM PRODUCTS_ICEBERG AT(TIMESTAMP => '2024-06-01 00:00:00'::TIMESTAMP_LTZ);

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

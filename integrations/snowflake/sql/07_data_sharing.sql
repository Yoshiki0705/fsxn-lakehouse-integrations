-- =============================================================================
-- 07 - Secure Data Sharing with FSxN
-- =============================================================================
-- Demonstrates Snowflake Secure Data Sharing using data stored on FSxN.
-- Combines S3 AP per-consumer access control with Snowflake sharing.
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA GOLD;

-- =============================================================================
-- Create Shared Views (Gold Layer)
-- =============================================================================

-- Aggregated revenue view (safe to share)
CREATE OR REPLACE SECURE VIEW DAILY_REVENUE_SHARED AS
SELECT
  DATE_TRUNC('day', transaction_timestamp) AS revenue_date,
  category,
  COUNT(*) AS transaction_count,
  SUM(amount) AS total_revenue,
  AVG(amount) AS avg_transaction_value
FROM FSXN_LAKEHOUSE.BRONZE.TRANSACTIONS
WHERE status = 'completed'
GROUP BY 1, 2;

-- Product catalog view (filtered for sharing)
CREATE OR REPLACE SECURE VIEW PRODUCT_CATALOG_SHARED AS
SELECT
  product_id,
  name,
  category,
  price,
  is_active
FROM FSXN_LAKEHOUSE.SILVER.PRODUCTS_ICEBERG
WHERE is_active = TRUE;

-- =============================================================================
-- Create Share
-- =============================================================================
CREATE OR REPLACE SHARE FSXN_LAKEHOUSE_SHARE
  COMMENT = 'FSxN Lakehouse data products for partner access';

-- Grant privileges to share
GRANT USAGE ON DATABASE FSXN_LAKEHOUSE TO SHARE FSXN_LAKEHOUSE_SHARE;
GRANT USAGE ON SCHEMA FSXN_LAKEHOUSE.GOLD TO SHARE FSXN_LAKEHOUSE_SHARE;
GRANT SELECT ON VIEW FSXN_LAKEHOUSE.GOLD.DAILY_REVENUE_SHARED TO SHARE FSXN_LAKEHOUSE_SHARE;
GRANT SELECT ON VIEW FSXN_LAKEHOUSE.GOLD.PRODUCT_CATALOG_SHARED TO SHARE FSXN_LAKEHOUSE_SHARE;

-- =============================================================================
-- Add Consumer Accounts
-- =============================================================================
-- ALTER SHARE FSXN_LAKEHOUSE_SHARE ADD ACCOUNTS = <consumer_account_locator>;

-- =============================================================================
-- Data Sharing + FSxN Architecture
-- =============================================================================
-- Combined access control layers:
--
-- 1. ONTAP Export Policy → Volume-level access
-- 2. S3 Access Point Policy → Per-consumer S3 AP
-- 3. IAM Role → AWS authentication
-- 4. Snowflake Share → Logical data sharing (no data copy)
-- 5. Secure View → Row/column filtering
--
-- Pattern D (Data Sharing) with FSxN:
--   Producer (FSxN Volume) → S3 AP (scoped) → Snowflake Share → Consumer
--
-- Benefits:
--   - No data duplication (Snowflake reads from FSxN)
--   - ONTAP FlexClone for consumer-specific copies if needed
--   - Audit trail at every layer
--   - Revoke access instantly at any layer

-- =============================================================================
-- Verify Share
-- =============================================================================
SHOW SHARES LIKE 'FSXN_LAKEHOUSE_SHARE';
DESCRIBE SHARE FSXN_LAKEHOUSE_SHARE;

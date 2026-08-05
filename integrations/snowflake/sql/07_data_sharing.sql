-- =============================================================================
-- 07 - Secure Data Sharing with FSx for ONTAP
-- =============================================================================
-- Demonstrates Snowflake Secure Data Sharing using data stored on FSx for
-- NetApp ONTAP via S3 Access Point. Implements multi-layer security:
--
--   Layer 1: ONTAP Export Policy (volume-level)
--   Layer 2: S3 Access Point Policy (per-consumer S3 AP)
--   Layer 3: IAM Role + External ID (AWS authentication)
--   Layer 4: Snowflake Share (logical data sharing — no data copy)
--   Layer 5: Secure View (row/column filtering for consumers)
--
-- Security Model (Design §3.2):
--   ┌─────────────────┐                      ┌─────────────────┐
--   │ Producer Account │                      │ Consumer Account │
--   │                  │                      │                  │
--   │ Secure View      │──── Share ──────────▶│ Shared Database  │
--   │ (filtered data)  │                      │ (read-only)      │
--   │                  │                      │                  │
--   │ Row filter:      │                      │ Cannot:          │
--   │ - category IN .. │                      │ - See raw data   │
--   │ Column mask:     │                      │ - Modify data    │
--   │ - PII redacted   │                      │ - Copy to own    │
--   └─────────────────┘                      └─────────────────┘
--
-- Key Principle: Data remains on FSx for ONTAP. Snowflake reads via S3 AP at query time.
-- Consumers query the Share — no data duplication occurs.
--
-- Prerequisites:
--   - 01_storage_integration.sql (Storage Integration + trust setup)
--   - 02_external_stage.sql (FSXN_BRONZE_STAGE created)
--   - 04_external_table.sql (TRANSACTIONS External Table created)
--   - 05_iceberg_table.sql (PRODUCTS_ICEBERG Iceberg Table created)
--
-- Requirements: REQ-5 (Secure Data Sharing)
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA GOLD;

-- =============================================================================
-- 1. Base View: DAILY_REVENUE (Aggregated from TRANSACTIONS External Table)
-- =============================================================================
-- Aggregates raw transaction data by date and category.
-- This serves as the source for the secure shared view.
-- Data is read from FSx for ONTAP via S3 AP at query time (no materialization).
-- =============================================================================

CREATE OR REPLACE VIEW DAILY_REVENUE AS
SELECT
    DATE_TRUNC('day', transaction_timestamp)  AS revenue_date,
    category,
    customer_id,
    COUNT(*)                                  AS transaction_count,
    SUM(amount)                               AS total_revenue,
    AVG(amount)                               AS avg_transaction_value,
    MIN(amount)                               AS min_transaction_value,
    MAX(amount)                               AS max_transaction_value
FROM FSXN_LAKEHOUSE.BRONZE.TRANSACTIONS
WHERE transaction_timestamp IS NOT NULL
GROUP BY 1, 2, 3;

-- =============================================================================
-- 2. Secure View: DAILY_REVENUE_SHARED (Row + Column Filtering)
-- =============================================================================
-- Security controls applied:
--
--   Row Filter:
--     - Only expose data for approved categories (Electronics, Clothing, Food)
--     - Excludes sensitive categories (Healthcare, Finance) from consumers
--
--   Column Mask:
--     - customer_id is redacted (SHA-256 hash) for consumer privacy
--     - Consumers see hashed identifiers — cannot reverse to real customer IDs
--     - Producer retains full access to raw customer_id via base view
--
-- SECURE keyword ensures:
--   - View definition is hidden from consumers (SHOW VIEWS won't reveal logic)
--   - Query optimizer cannot expose filtered rows through side channels
--   - Consumers cannot use EXPLAIN or profile to infer filter conditions
-- =============================================================================

CREATE OR REPLACE SECURE VIEW DAILY_REVENUE_SHARED
    COMMENT = 'Aggregated daily revenue shared with partners — row/column filtered (REQ-5)'
AS
SELECT
    revenue_date,
    category,
    -- Column mask: redact customer_id with SHA-256 hash for consumer privacy
    SHA2(customer_id, 256)                    AS customer_id_hash,
    transaction_count,
    total_revenue,
    avg_transaction_value,
    min_transaction_value,
    max_transaction_value
FROM DAILY_REVENUE
WHERE
    -- Row filter: only share approved categories (exclude sensitive data)
    category IN ('Electronics', 'Clothing', 'Food', 'Sports', 'Home')
    -- Additional row filter: only share completed/recent data
    AND revenue_date >= DATEADD('month', -12, CURRENT_DATE());

-- =============================================================================
-- 3. Product Catalog Secure View (Filtered for Sharing)
-- =============================================================================
-- Shares active product information from Iceberg Table on FSx for ONTAP.
-- Excludes internal pricing tiers and inactive products.
-- =============================================================================

CREATE OR REPLACE SECURE VIEW PRODUCT_CATALOG_SHARED
    COMMENT = 'Active product catalog shared with partners — filtered (REQ-5)'
AS
SELECT
    product_id,
    name,
    category,
    price,
    is_active
FROM FSXN_LAKEHOUSE.SILVER.PRODUCTS_ICEBERG
WHERE is_active = TRUE;

-- =============================================================================
-- 4. Create Share Object
-- =============================================================================
-- The Share is a named object that packages views for external consumption.
-- No data is copied — consumers query the producer's compute or their own
-- warehouse against the same underlying FSx for ONTAP data via S3 AP.
--
-- Architecture:
--   Consumer Query → Snowflake Share → Secure View → External Table
--     → S3 Access Point → FSx for ONTAP Volume
-- =============================================================================

CREATE OR REPLACE SHARE FSXN_LAKEHOUSE_SHARE
    COMMENT = 'FSx for ONTAP Lakehouse data products for partner access — REQ-5';

-- =============================================================================
-- 5. Grant Privileges to Share
-- =============================================================================
-- Minimum required grants for consumers to query shared views:
--   1. USAGE on DATABASE — allows consumer to see the database
--   2. USAGE on SCHEMA — allows consumer to see objects in schema
--   3. SELECT on each VIEW — allows consumer to query specific views
--
-- Note: Consumers CANNOT access underlying tables, stages, or raw data.
-- The Secure View acts as the sole access boundary.
-- =============================================================================

-- Grant database-level access
GRANT USAGE ON DATABASE FSXN_LAKEHOUSE TO SHARE FSXN_LAKEHOUSE_SHARE;

-- Grant schema-level access (GOLD schema only — not BRONZE or SILVER)
GRANT USAGE ON SCHEMA FSXN_LAKEHOUSE.GOLD TO SHARE FSXN_LAKEHOUSE_SHARE;

-- Grant SELECT on secure views (consumers can only query these filtered views)
GRANT SELECT ON VIEW FSXN_LAKEHOUSE.GOLD.DAILY_REVENUE_SHARED
    TO SHARE FSXN_LAKEHOUSE_SHARE;
GRANT SELECT ON VIEW FSXN_LAKEHOUSE.GOLD.PRODUCT_CATALOG_SHARED
    TO SHARE FSXN_LAKEHOUSE_SHARE;

-- =============================================================================
-- 6. Add Consumer Account to Share
-- =============================================================================
-- Replace <consumer_account_locator> with the actual consumer account.
-- Format: <orgname>.<account_name> or legacy account locator
--
-- Example:
--   ALTER SHARE FSXN_LAKEHOUSE_SHARE ADD ACCOUNTS = 'AB12345';
--   ALTER SHARE FSXN_LAKEHOUSE_SHARE ADD ACCOUNTS = 'myorg.consumer_acct';
--
-- Multiple consumers:
--   ALTER SHARE FSXN_LAKEHOUSE_SHARE ADD ACCOUNTS = 'AB12345', 'CD67890';
--
-- IMPORTANT: Consumer must be in the same Snowflake region (ap-northeast-1)
-- for cross-region sharing, use Snowflake Replication or Listing.
-- =============================================================================

-- Uncomment and replace with actual consumer account locator:
-- ALTER SHARE FSXN_LAKEHOUSE_SHARE ADD ACCOUNTS = '<consumer_account_locator>';

-- =============================================================================
-- 7. Verification Queries (Producer Side)
-- =============================================================================
-- Run these queries to verify the share is correctly configured before
-- notifying the consumer.
-- =============================================================================

-- 7.1 Verify Share exists and is configured
SHOW SHARES LIKE 'FSXN_LAKEHOUSE_SHARE';

-- 7.2 Describe Share — shows granted objects and consumer accounts
DESCRIBE SHARE FSXN_LAKEHOUSE_SHARE;

-- 7.3 Verify Secure View returns data (producer can see all granted data)
SELECT
    'DAILY_REVENUE_SHARED' AS view_name,
    COUNT(*)               AS row_count,
    COUNT(DISTINCT category) AS category_count,
    MIN(revenue_date)      AS earliest_date,
    MAX(revenue_date)      AS latest_date
FROM DAILY_REVENUE_SHARED;

-- 7.4 Verify column masking is applied (customer_id_hash should be 64-char hex)
SELECT
    revenue_date,
    category,
    customer_id_hash,
    LENGTH(customer_id_hash) AS hash_length,
    transaction_count,
    total_revenue
FROM DAILY_REVENUE_SHARED
LIMIT 10;

-- 7.5 Verify row filtering — excluded categories should NOT appear
SELECT DISTINCT category
FROM DAILY_REVENUE_SHARED
ORDER BY category;
-- Expected: Electronics, Clothing, Food, Sports, Home
-- Should NOT contain: Healthcare, Finance, or other sensitive categories

-- 7.6 Verify Product Catalog Shared view
SELECT
    'PRODUCT_CATALOG_SHARED' AS view_name,
    COUNT(*)                 AS row_count,
    COUNT(DISTINCT category) AS category_count
FROM PRODUCT_CATALOG_SHARED;

-- 7.7 Compare producer vs consumer visibility
-- Producer can see ALL data via base view:
SELECT
    'DAILY_REVENUE (base - all data)' AS source,
    COUNT(*) AS total_rows,
    COUNT(DISTINCT category) AS all_categories
FROM DAILY_REVENUE;

-- Consumer only sees filtered data via secure view:
SELECT
    'DAILY_REVENUE_SHARED (filtered)' AS source,
    COUNT(*) AS visible_rows,
    COUNT(DISTINCT category) AS visible_categories
FROM DAILY_REVENUE_SHARED;

-- =============================================================================
-- 8. Consumer-Side Verification (Run on Consumer Account)
-- =============================================================================
-- After consumer account is added, the consumer runs these queries:
--
--   -- Create database from share
--   CREATE DATABASE FSXN_PARTNER_DATA FROM SHARE <producer_account>.FSXN_LAKEHOUSE_SHARE;
--
--   -- Query shared data
--   SELECT * FROM FSXN_PARTNER_DATA.GOLD.DAILY_REVENUE_SHARED LIMIT 10;
--
--   -- Verify cannot see raw data
--   SELECT * FROM FSXN_PARTNER_DATA.BRONZE.TRANSACTIONS;  -- ERROR: insufficient privileges
--
--   -- Verify cannot see view definition
--   SHOW VIEWS IN FSXN_PARTNER_DATA.GOLD;  -- definition column is empty for SECURE views
-- =============================================================================

-- =============================================================================
-- 9. Access Revocation
-- =============================================================================
-- Instantly revoke consumer access. Takes effect immediately — consumer
-- queries will fail with "Object does not exist" after revocation.
--
-- Revocation options:
--   a) Remove specific consumer account (preserves share for other consumers)
--   b) Drop the share entirely (revokes all consumers)
--   c) Revoke SELECT on specific view (partial revocation)
-- =============================================================================

-- 9.1 Remove specific consumer account from share
-- Uncomment and replace with actual consumer account locator:
-- ALTER SHARE FSXN_LAKEHOUSE_SHARE REMOVE ACCOUNTS = '<consumer_account_locator>';

-- 9.2 Verify consumer was removed
-- DESCRIBE SHARE FSXN_LAKEHOUSE_SHARE;
-- (consumer should no longer appear in the accounts list)

-- 9.3 Partial revocation — remove access to specific view only
-- REVOKE SELECT ON VIEW FSXN_LAKEHOUSE.GOLD.PRODUCT_CATALOG_SHARED
--     FROM SHARE FSXN_LAKEHOUSE_SHARE;

-- 9.4 Full revocation — drop the share entirely (nuclear option)
-- DROP SHARE FSXN_LAKEHOUSE_SHARE;

-- =============================================================================
-- 10. Security Model Summary (Design §3.2)
-- =============================================================================
-- Combined access control layers for FSx for ONTAP + Snowflake Data Sharing:
--
-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ Layer │ Mechanism                │ What It Controls                      │
-- ├───────┼──────────────────────────┼───────────────────────────────────────┤
-- │   1   │ ONTAP Export Policy      │ Volume-level NFS/SMB access           │
-- │   2   │ S3 Access Point Policy   │ Per-consumer S3 AP (IAM principal)    │
-- │   3   │ IAM Role + External ID   │ AWS authentication (STS AssumeRole)   │
-- │   4   │ Storage Integration      │ Path-level (STORAGE_ALLOWED_LOCATIONS)│
-- │   5   │ Snowflake RBAC           │ Role-based access on stages/tables    │
-- │   6   │ Secure View              │ Row/column filtering for consumers    │
-- │   7   │ Share Object             │ Logical sharing (no data copy)        │
-- └─────────────────────────────────────────────────────────────────────────┘
--
-- Data Flow:
--   Consumer Query
--     → Snowflake Share (Layer 7)
--       → Secure View with row/column filter (Layer 6)
--         → External Table (Layer 5 — RBAC)
--           → Storage Integration (Layer 4 — path restriction)
--             → IAM Role AssumeRole (Layer 3)
--               → S3 Access Point (Layer 2 — policy)
--                 → FSx for ONTAP Volume (Layer 1 — export policy)
--
-- Benefits of this architecture:
--   - Zero data duplication: consumers read from FSx for ONTAP at query time
--   - Instant revocation: remove account from share = immediate cutoff
--   - Audit trail at every layer (CloudTrail, Snowflake ACCESS_HISTORY)
--   - ONTAP FlexClone available for consumer-specific data copies if needed
--   - Granular control: can share different views to different consumers
--   - Column masking: PII (customer_id) never exposed to consumers
--   - Row filtering: sensitive categories excluded from consumer view
-- =============================================================================

-- =============================================================================
-- TROUBLESHOOTING
-- =============================================================================
-- If DESCRIBE SHARE shows no objects:
--   1. Verify GRANT USAGE ON DATABASE and SCHEMA were executed
--   2. Verify GRANT SELECT ON VIEW was executed
--   3. Check: SHOW GRANTS TO SHARE FSXN_LAKEHOUSE_SHARE;
--
-- If consumer cannot create database from share:
--   1. Verify consumer account was added: DESCRIBE SHARE FSXN_LAKEHOUSE_SHARE;
--   2. Verify consumer is in same region (ap-northeast-1)
--   3. Check consumer has CREATE DATABASE privilege
--
-- If consumer query returns 0 rows:
--   1. Verify base TRANSACTIONS table has data: SELECT COUNT(*) FROM BRONZE.TRANSACTIONS;
--   2. Verify row filter categories match actual data categories
--   3. Verify date filter is not excluding all data
--   4. Check Storage Integration is still valid (DESCRIBE INTEGRATION)
--
-- If "Secure view cannot be used in a share" error:
--   1. Ensure view is created with CREATE SECURE VIEW (not just CREATE VIEW)
--   2. Ensure view references only objects the share has access to
-- =============================================================================

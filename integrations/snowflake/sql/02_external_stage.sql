-- =============================================================================
-- 02 - External Stages for FSx for ONTAP via S3 Access Point
-- =============================================================================
--
-- Purpose:
--   Creates External Stages for each medallion layer (bronze, silver, gold)
--   and the media layer for unstructured data. Stages use the Storage
--   Integration created in 01_storage_integration.sql.
--
-- Prerequisites:
--   - 01_storage_integration.sql executed (Storage Integration created)
--   - Two-phase trust setup completed (CloudFormation updated with Snowflake trust)
--   - SYSADMIN has USAGE on fsxn_storage_integration (granted in 01)
--   - S3 Access Point alias available (from CloudFormation output)
--
-- Stage Hierarchy & Downstream Usage:
-- ┌─────────────────────────────────────────────────────────────────────────────┐
-- │ Stage                    │ Schema │ Used By                                  │
-- ├─────────────────────────────────────────────────────────────────────────────┤
-- │ FSXN_BRONZE_STAGE        │ BRONZE │ External Tables: TRANSACTIONS (Parquet), │
-- │                          │        │   IOT_SENSORS (Parquet, partitioned),    │
-- │                          │        │   CUSTOMERS_CSV (CSV), EVENTS_JSON (JSON)│
-- │                          │        │ Snowpipe: FSXN_EVENTS_PIPE (auto-ingest) │
-- │                          │        │ → See 04_external_table.sql, 06_snowpipe │
-- ├─────────────────────────────────────────────────────────────────────────────┤
-- │ FSXN_SILVER_STAGE        │ SILVER │ Iceberg Table: PRODUCTS_ICEBERG          │
-- │                          │        │   (Snowflake-managed catalog, DML)       │
-- │                          │        │ → See 05_iceberg_table.sql               │
-- ├─────────────────────────────────────────────────────────────────────────────┤
-- │ FSXN_GOLD_STAGE          │ GOLD   │ Secure View: DAILY_REVENUE_SHARED        │
-- │                          │        │ Share: FSXN_LAKEHOUSE_SHARE              │
-- │                          │        │ → See 07_data_sharing.sql                │
-- ├─────────────────────────────────────────────────────────────────────────────┤
-- │ FSXN_MEDIA_STAGE         │ MEDIA  │ Directory Table (file metadata)          │
-- │                          │        │ Pre-signed URLs (external access)        │
-- │                          │        │ Snowpark UDFs (image/doc processing)     │
-- │                          │        │ → See 08_directory_table.sql (recreated  │
-- │                          │        │   with DIRECTORY=TRUE), 09_snowpark, 10  │
-- └─────────────────────────────────────────────────────────────────────────────┘
--
-- NOTE on MEDIA stage:
--   This script creates a basic MEDIA stage for connectivity validation.
--   Script 08_directory_table.sql recreates it with DIRECTORY = (ENABLE = TRUE)
--   to enable Directory Table queries on unstructured files.
--
-- =============================================================================

-- =============================================================================
-- 1. Role & Warehouse Context
-- =============================================================================
-- SYSADMIN creates stages (ACCOUNTADMIN created the Storage Integration in 01)
USE ROLE SYSADMIN;
USE WAREHOUSE COMPUTE_WH;

-- =============================================================================
-- 2. Database & Schema Setup
-- =============================================================================
-- Create the database for all FSx for ONTAP lakehouse data
CREATE DATABASE IF NOT EXISTS FSXN_LAKEHOUSE
  COMMENT = 'FSx for NetApp ONTAP Lakehouse data via S3 Access Point';

USE DATABASE FSXN_LAKEHOUSE;

-- Create schemas for medallion architecture + media layer
CREATE SCHEMA IF NOT EXISTS BRONZE
  COMMENT = 'Raw ingested data from FSx for ONTAP (Parquet, CSV, JSON)';

CREATE SCHEMA IF NOT EXISTS SILVER
  COMMENT = 'Cleaned and transformed data (Iceberg Tables)';

CREATE SCHEMA IF NOT EXISTS GOLD
  COMMENT = 'Business-ready aggregates and shared views';

CREATE SCHEMA IF NOT EXISTS MEDIA
  COMMENT = 'Unstructured data: images, documents, video (Directory Table + Pre-signed URLs)';

-- =============================================================================
-- 3. External Stage — Bronze Layer
-- =============================================================================
-- Used by: External Tables (TRANSACTIONS, IOT_SENSORS, CUSTOMERS_CSV, EVENTS_JSON)
--          Snowpipe (FSXN_EVENTS_PIPE for auto-ingest)
-- Data:    Raw Parquet, CSV, JSON files written to FSx for ONTAP via NFS
-- Replace <AP_ALIAS> with your S3 Access Point alias from CloudFormation output
CREATE OR REPLACE STAGE BRONZE.FSXN_BRONZE_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<AP_ALIAS>/bronze/'
  COMMENT = 'Bronze layer — raw structured data on FSx for ONTAP. Used by External Tables and Snowpipe.';

-- =============================================================================
-- 4. External Stage — Silver Layer
-- =============================================================================
-- Used by: Iceberg Table (PRODUCTS_ICEBERG with Snowflake-managed catalog)
-- Data:    Iceberg data + metadata files managed by Snowflake DML operations
-- Replace <AP_ALIAS> with your S3 Access Point alias from CloudFormation output
CREATE OR REPLACE STAGE SILVER.FSXN_SILVER_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<AP_ALIAS>/silver/'
  COMMENT = 'Silver layer — Iceberg Tables on FSx for ONTAP. Snowflake manages metadata + data files.';

-- =============================================================================
-- 5. External Stage — Gold Layer
-- =============================================================================
-- Used by: Secure Views for Data Sharing (DAILY_REVENUE_SHARED)
--          Share object (FSXN_LAKEHOUSE_SHARE) for cross-account access
-- Data:    Business-ready aggregates, pre-computed metrics
-- Replace <AP_ALIAS> with your S3 Access Point alias from CloudFormation output
CREATE OR REPLACE STAGE GOLD.FSXN_GOLD_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<AP_ALIAS>/gold/'
  COMMENT = 'Gold layer — business-ready data on FSx for ONTAP. Used by Secure Data Sharing.';

-- =============================================================================
-- 6. External Stage — Media Layer (Basic)
-- =============================================================================
-- Used by: Directory Table queries, Pre-signed URL generation, Snowpark UDFs
-- Data:    Images (JPEG, PNG), Documents (PDF, DOCX), Video (MP4)
--
-- NOTE: This creates a basic stage for initial validation. Script
--       08_directory_table.sql will recreate this stage with:
--         DIRECTORY = (ENABLE = TRUE, AUTO_REFRESH = FALSE)
--       to enable Directory Table metadata queries.
--       AUTO_REFRESH = FALSE is required because FSx for ONTAP S3 Access Points
--       do NOT support S3 Event Notifications.
--
-- Replace <AP_ALIAS> with your S3 Access Point alias from CloudFormation output
CREATE OR REPLACE STAGE MEDIA.FSXN_MEDIA_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<AP_ALIAS>/media/'
  COMMENT = 'Media layer — unstructured files on FSx for ONTAP. Recreated with DIRECTORY=TRUE in 08_directory_table.sql.';

-- =============================================================================
-- 7. Validation — LIST Stages
-- =============================================================================
-- LIST verifies that:
--   1. Storage Integration trust is correctly configured
--   2. S3 Access Point is reachable from Snowflake
--   3. IAM Role has permission to list objects at each path
--   4. Files exist at the expected paths (if sample data was uploaded)
--
-- Expected output: file list with name, size, md5, last_modified
-- If empty but no error: integration works, but no files at that path yet
-- If error: check Storage Integration trust policy (see 01 troubleshooting)

-- Validate Bronze stage (should show Parquet/CSV/JSON files if sample data uploaded)
LIST @BRONZE.FSXN_BRONZE_STAGE;

-- Validate Silver stage (empty until Iceberg Table is created in 05)
LIST @SILVER.FSXN_SILVER_STAGE;

-- Validate Gold stage (empty until aggregates are created in 07)
LIST @GOLD.FSXN_GOLD_STAGE;

-- Validate Media stage (should show image/document/video files if uploaded)
LIST @MEDIA.FSXN_MEDIA_STAGE;

-- =============================================================================
-- 8. Stage Information (Optional)
-- =============================================================================
-- Show all stages in the database for verification
SHOW STAGES IN DATABASE FSXN_LAKEHOUSE;

-- =============================================================================
-- TROUBLESHOOTING
-- =============================================================================
-- If LIST returns an error:
--
-- 1. "Failure using stage area" or "Access Denied":
--    → Storage Integration trust not configured. Run:
--      DESCRIBE INTEGRATION fsxn_storage_integration;
--    → Verify STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID are set
--    → Ensure CloudFormation was updated with these values (see 01 script)
--
-- 2. "Integration does not exist":
--    → Run 01_storage_integration.sql first
--    → Verify GRANT USAGE ON INTEGRATION was executed for SYSADMIN
--
-- 3. "Bucket does not exist" or "Invalid bucket":
--    → Check <AP_ALIAS> matches your actual S3 Access Point alias
--    → Verify S3 AP exists: aws s3control list-access-points --account-id <ID>
--
-- 4. Empty result (no error):
--    → Integration is working correctly
--    → Upload sample data to FSx for ONTAP via NFS, then re-run LIST
-- =============================================================================

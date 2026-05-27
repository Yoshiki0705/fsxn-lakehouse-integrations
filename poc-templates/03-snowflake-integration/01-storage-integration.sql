-- FSx for ONTAP S3 Access Points — Snowflake Integration Setup
-- Step 1: Storage Integration
--
-- Replace:
--   <ACCOUNT_ID> with your AWS account ID
--   <ROLE_NAME> with your IAM role name for Snowflake
--   <AP_ALIAS> with your S3 Access Point alias

-- ============================================================
-- 1. Create Storage Integration
-- ============================================================
CREATE OR REPLACE STORAGE INTEGRATION fsxn_poc_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/<ROLE_NAME>'
  STORAGE_ALLOWED_LOCATIONS = ('s3://<AP_ALIAS>/');

-- ============================================================
-- 2. Get Snowflake's IAM user ARN (for trust policy)
-- ============================================================
DESC INTEGRATION fsxn_poc_integration;
-- Note: STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID
-- Use these to update your IAM role trust policy

-- ============================================================
-- 3. After updating IAM trust policy, verify:
-- ============================================================
-- SELECT SYSTEM$VERIFY_EXTERNAL_OAUTH_TOKEN(); -- if applicable

-- ============================================================
-- Next: Run 02-stage-and-table.sql
-- ============================================================

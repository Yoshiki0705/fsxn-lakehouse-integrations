-- =============================================================================
-- 01 - Storage Integration for FSx for ONTAP S3 Access Point
-- =============================================================================
--
-- Purpose:
--   Creates a Snowflake Storage Integration that allows Snowflake to access
--   FSx for NetApp ONTAP volumes via S3 Access Point using IAM Role authentication.
--
-- Prerequisites:
--   - Snowflake account (Enterprise Edition+, ap-northeast-1 region)
--   - ACCOUNTADMIN role access
--   - CloudFormation stack deployed (template.yaml) — Phase 1 (own-account trust)
--   - IAM Role ARN from CloudFormation output (IAMRoleArn)
--   - S3 Access Point Alias from CloudFormation output (S3AccessPointAlias)
--
-- =============================================================================
--
-- TWO-PHASE TRUST SETUP FLOW
-- ===========================
--
-- This script addresses the "chicken-and-egg" problem in Snowflake Storage
-- Integration setup:
--
--   Problem:
--     - Snowflake needs an IAM Role ARN to create the Storage Integration
--     - The IAM Role trust policy needs Snowflake's AWS Account ID + External ID
--     - But Snowflake's Account ID and External ID are only revealed AFTER
--       creating the Storage Integration (via DESCRIBE INTEGRATION)
--     - Neither side can be configured first without the other's information
--
--   Solution: Two-Phase Setup
--
--   ┌─────────────────────────────────────────────────────────────────────────┐
--   │ PHASE 1: Initial Setup (break the circular dependency)                  │
--   │                                                                         │
--   │  Step 1: Deploy CloudFormation with own-account trust (placeholder)     │
--   │          → IAM Role trusts your own AWS account temporarily             │
--   │          → This allows the role to exist so Snowflake can reference it  │
--   │                                                                         │
--   │  Step 2: Run CREATE STORAGE INTEGRATION (this script)                   │
--   │          → Snowflake registers the IAM Role ARN                         │
--   │          → Snowflake generates its unique AWS Account ID + External ID  │
--   │                                                                         │
--   │  Step 3: Run DESCRIBE INTEGRATION                                       │
--   │          → Retrieve STORAGE_AWS_IAM_USER_ARN (Snowflake's AWS account)  │
--   │          → Retrieve STORAGE_AWS_EXTERNAL_ID (unique per integration)    │
--   │                                                                         │
--   │  Step 4: Update CloudFormation with actual Snowflake trust info         │
--   │          → Replace own-account trust with Snowflake's AWS Account ID    │
--   │          → Add External ID condition (prevents confused deputy attack)  │
--   │                                                                         │
--   │  Step 5: Re-validate — run DESCRIBE INTEGRATION again                   │
--   │          → Confirm trust relationship is established                    │
--   │          → Integration should show no errors                            │
--   └─────────────────────────────────────────────────────────────────────────┘
--
--   ┌─────────────────────────────────────────────────────────────────────────┐
--   │ PHASE 2: Runtime Authentication (after trust is established)            │
--   │                                                                         │
--   │  1. Snowflake query references an External Stage                        │
--   │  2. Snowflake calls STS AssumeRole with External ID                     │
--   │  3. STS validates trust policy → returns temporary credentials          │
--   │  4. Snowflake uses temp credentials for S3 API calls to Access Point    │
--   │  5. S3 AP policy validates IAM principal                                │
--   │  6. Request forwarded to FSx for ONTAP volume                           │
--   └─────────────────────────────────────────────────────────────────────────┘
--
-- Usage:
--   1. Run this script in Snowflake (SnowSQL or Snowsight)
--   2. Note the DESCRIBE INTEGRATION output values
--   3. Run: integrations/snowflake/scripts/update_trust_policy.sh
--   4. Come back and run the Phase 2 validation section at the bottom
--
-- =============================================================================

-- #############################################################################
-- PHASE 1: Create Storage Integration
-- #############################################################################

-- Storage Integration requires ACCOUNTADMIN role
USE ROLE ACCOUNTADMIN;

-- Create the Storage Integration
-- Replace <IAM_ROLE_ARN> with the IAMRoleArn output from CloudFormation
-- Replace <AP_ALIAS> with the S3AccessPointAlias output from CloudFormation
--
-- Example values:
--   IAM_ROLE_ARN: arn:aws:iam::123456789012:role/fsxn-lakehouse-snowflake-s3-role
--   AP_ALIAS:     fsxn-snowflake-ap-abc123def456-s3alias
CREATE OR REPLACE STORAGE INTEGRATION fsxn_storage_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '<IAM_ROLE_ARN>'
  STORAGE_ALLOWED_LOCATIONS = (
    's3://<AP_ALIAS>/bronze/',
    's3://<AP_ALIAS>/silver/',
    's3://<AP_ALIAS>/gold/',
    's3://<AP_ALIAS>/media/'
  )
  COMMENT = 'FSx for ONTAP S3 Access Point integration — two-phase trust setup with IAM Role';

-- #############################################################################
-- DESCRIBE INTEGRATION — Retrieve Snowflake Trust Information
-- #############################################################################
-- After creating the integration, Snowflake assigns:
--   - STORAGE_AWS_IAM_USER_ARN: The Snowflake-managed AWS account/role
--     (e.g., arn:aws:iam::123456789012:user/abc1-b-self1234)
--   - STORAGE_AWS_EXTERNAL_ID: A unique ID for this integration
--     (e.g., ABC12345_SFCRole=2_abcdefghijklmnop=)
--
-- These two values are needed to update the CloudFormation trust policy.
DESCRIBE INTEGRATION fsxn_storage_integration;

-- ┌─────────────────────────────────────────────────────────────────────────┐
-- │ ACTION REQUIRED: Note the following values from DESCRIBE output         │
-- │                                                                         │
-- │   property_value for STORAGE_AWS_IAM_USER_ARN  → Snowflake's IAM user  │
-- │   property_value for STORAGE_AWS_EXTERNAL_ID   → External ID           │
-- │                                                                         │
-- │ Then run the trust policy update script:                                │
-- │                                                                         │
-- │   ./integrations/snowflake/scripts/update_trust_policy.sh \             │
-- │     --snowflake-arn <STORAGE_AWS_IAM_USER_ARN> \                        │
-- │     --external-id <STORAGE_AWS_EXTERNAL_ID>                             │
-- │                                                                         │
-- │ This updates the CloudFormation stack to trust Snowflake's account      │
-- │ with the External ID condition, completing the trust relationship.      │
-- └─────────────────────────────────────────────────────────────────────────┘

-- #############################################################################
-- GRANT USAGE — Allow SYSADMIN to use this integration
-- #############################################################################
-- SYSADMIN needs USAGE privilege to create stages referencing this integration.
-- ACCOUNTADMIN retains ownership.
GRANT USAGE ON INTEGRATION fsxn_storage_integration TO ROLE SYSADMIN;

-- #############################################################################
-- PHASE 2 VALIDATION (Run AFTER updating CloudFormation trust policy)
-- #############################################################################
-- After the trust policy update completes, run the following to confirm
-- the integration is working correctly.
--
-- Expected behavior:
--   - DESCRIBE INTEGRATION shows no error properties
--   - STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID are populated
--   - Creating a stage with this integration succeeds
--   - LIST @stage returns files (if data exists on FSx for ONTAP)

-- Re-describe to verify trust is established
DESCRIBE INTEGRATION fsxn_storage_integration;

-- Validation: Attempt to create a temporary stage to confirm S3 AP access
-- Replace <AP_ALIAS> with your actual S3 Access Point alias
CREATE OR REPLACE TEMPORARY STAGE fsxn_integration_test_stage
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<AP_ALIAS>/bronze/'
  FILE_FORMAT = (TYPE = 'PARQUET');

-- If the integration is correctly configured, LIST should succeed
-- (returns empty result if no files exist yet, but no error = success)
LIST @fsxn_integration_test_stage;

-- Clean up validation stage
DROP STAGE IF EXISTS fsxn_integration_test_stage;

-- #############################################################################
-- TROUBLESHOOTING
-- #############################################################################
-- If DESCRIBE INTEGRATION shows errors or LIST fails:
--
-- 1. Verify CloudFormation stack update completed successfully:
--    aws cloudformation describe-stacks --stack-name fsxn-lakehouse-snowflake \
--      --query 'Stacks[0].StackStatus'
--
-- 2. Check IAM Role trust policy has Snowflake's account:
--    aws iam get-role --role-name fsxn-lakehouse-snowflake-s3-role \
--      --query 'Role.AssumeRolePolicyDocument'
--
-- 3. Verify External ID matches:
--    The ExternalId in the trust policy must exactly match
--    STORAGE_AWS_EXTERNAL_ID from DESCRIBE INTEGRATION
--
-- 4. Confirm S3 Access Point has internet network origin:
--    aws s3control get-access-point --account-id <ACCOUNT_ID> \
--      --name fsxn-snowflake-ap --query 'NetworkOrigin'
--    Expected: "Internet"
--
-- 5. Re-run DESCRIBE INTEGRATION after fixing any issues:
--    DESCRIBE INTEGRATION fsxn_storage_integration;
-- =============================================================================

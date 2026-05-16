-- =============================================================================
-- 01 - Storage Integration for FSxN S3 Access Point
-- =============================================================================
-- Creates a Snowflake Storage Integration that allows Snowflake to access
-- FSx for NetApp ONTAP via S3 Access Point using IAM Role authentication.
--
-- Prerequisites:
--   - CloudFormation stack deployed (template.yaml)
--   - IAM Role ARN from CloudFormation output
--   - S3 Access Point ARN from CloudFormation output
--
-- After running this script:
--   1. Run DESCRIBE INTEGRATION to get Snowflake's AWS Account ID and External ID
--   2. Update CloudFormation stack with these values
--   3. Re-run DESCRIBE INTEGRATION to verify trust relationship
-- =============================================================================

-- Create Storage Integration
CREATE OR REPLACE STORAGE INTEGRATION fsxn_storage_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '<SnowflakeRoleArn from CloudFormation output>'
  STORAGE_ALLOWED_LOCATIONS = (
    's3://<S3AccessPointAlias>/',
    's3://<S3AccessPointAlias>/bronze/',
    's3://<S3AccessPointAlias>/silver/',
    's3://<S3AccessPointAlias>/gold/'
  )
  STORAGE_BLOCKED_LOCATIONS = (
    's3://<S3AccessPointAlias>/_internal/',
    's3://<S3AccessPointAlias>/_snapshots/'
  )
  COMMENT = 'Storage integration for FSx for NetApp ONTAP via S3 Access Point';

-- =============================================================================
-- IMPORTANT: After creating the integration, run this to get trust policy values
-- =============================================================================
DESCRIBE INTEGRATION fsxn_storage_integration;

-- Note the following values from the output:
--   STORAGE_AWS_IAM_USER_ARN  → Use as SnowflakeAccountId in CloudFormation
--   STORAGE_AWS_EXTERNAL_ID   → Use as SnowflakeExternalId in CloudFormation
--
-- Then update the CloudFormation stack:
--   aws cloudformation update-stack ... \
--     --parameter-overrides SnowflakeAccountId=<account-from-arn> \
--                           SnowflakeExternalId=<external-id>

-- Verify the integration after updating trust policy
-- DESCRIBE INTEGRATION fsxn_storage_integration;

-- Grant usage to roles
GRANT USAGE ON INTEGRATION fsxn_storage_integration TO ROLE SYSADMIN;
GRANT USAGE ON INTEGRATION fsxn_storage_integration TO ROLE DATA_ENGINEER;

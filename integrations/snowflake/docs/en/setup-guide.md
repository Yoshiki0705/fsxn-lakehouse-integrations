# Snowflake Setup Guide

## Overview

Configure FSx for NetApp ONTAP as a Snowflake External Stage to use as the
storage layer for External Tables and Iceberg Tables.

## Prerequisites

- AWS account with FSx for NetApp ONTAP deployed
- FSx for ONTAP SVM with S3 protocol enabled
- Snowflake account (Enterprise Edition or higher recommended)
- AWS CLI v2 configured
- ACCOUNTADMIN role access

## Setup Flow

```
Step 1: Deploy CloudFormation
    ↓
Step 2: Create Snowflake Storage Integration
    ↓
Step 3: DESCRIBE INTEGRATION to get AWS info
    ↓
Step 4: Update CloudFormation (trust policy)
    ↓
Step 5: Create External Stage
    ↓
Step 6: Create External Table / Iceberg Table
```

## Step 1: Deploy CloudFormation Stack

```bash
aws cloudformation deploy \
  --template-file integrations/snowflake/template.yaml \
  --stack-name fsxn-snowflake-integration \
  --parameter-overrides \
    S3BucketName=svm-lakehouse \
    VpcId=vpc-0123456789abcdef0 \
    SubnetIds=subnet-xxx,subnet-yyy \
  --capabilities CAPABILITY_NAMED_IAM \
  --region <YOUR_REGION>
```

Check outputs:
```bash
aws cloudformation describe-stacks \
  --stack-name fsxn-snowflake-integration \
  --query 'Stacks[0].Outputs' \
  --output table
```

## Step 2: Create Storage Integration

Run `sql/01_storage_integration.sql`:

```sql
CREATE STORAGE INTEGRATION fsxn_storage_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '<SnowflakeRoleArn>'
  STORAGE_ALLOWED_LOCATIONS = ('s3://<S3AccessPointAlias>/');
```

## Step 3: Get Trust Policy Information

```sql
DESCRIBE INTEGRATION fsxn_storage_integration;
```

Note these values:
- `STORAGE_AWS_IAM_USER_ARN` → Snowflake's AWS Account ID
- `STORAGE_AWS_EXTERNAL_ID` → External ID

## Step 4: Update CloudFormation

```bash
aws cloudformation update-stack \
  --stack-name fsxn-snowflake-integration \
  --use-previous-template \
  --parameter-overrides \
    SnowflakeAccountId=<account-id-from-arn> \
    SnowflakeExternalId=<external-id> \
  --capabilities CAPABILITY_NAMED_IAM
```

## Step 5: Create External Stage

Run `sql/02_external_stage.sql`:

```sql
CREATE STAGE FSXN_BRONZE_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<S3AccessPointAlias>/bronze/';
```

## Step 6: Create Tables

Run SQL scripts in order:
1. `03_file_format.sql` — File format definitions
2. `04_external_table.sql` — External Tables
3. `05_iceberg_table.sql` — Iceberg Tables
4. `06_snowpipe.sql` — Snowpipe setup (optional)
5. `07_data_sharing.sql` — Data sharing (optional)

## Troubleshooting

### Issue: LIST @stage returns empty

**Cause**: Storage Integration trust policy not configured

**Resolution**: Re-run Steps 3-4 to update trust policy

### Issue: "Failure using stage area" error

**Cause**: S3 AP policy or IAM role permission issue

**Resolution**:
1. Verify IAM role policy includes S3 AP ARN
2. Check S3 AP policy Principal is correct
3. Verify VPC condition

### Issue: Snowpipe not detecting files

**Cause**: FSx for ONTAP does not natively support S3 Event Notifications

**Resolution**: Use Lambda polling pattern (see `06_snowpipe.sql`)

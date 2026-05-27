🌐 **English** | [日本語](README-ja.md)

# Module 03: Snowflake Integration (External Table + Cortex AI)

## End-to-End Flow (30 minutes)

```
Step 1: Create Storage Integration (01-storage-integration.sql)
  ↓
Step 2: Update IAM trust policy with Snowflake's IAM user ARN
  ↓
Step 3: Create Stage + External Table (02-stage-and-table.sql)
  ↓
Step 4: Run Cortex AI demos (03-cortex-ai-demo.sql)
```

## Prerequisites

- [ ] Snowflake account (Standard or higher) in same AWS region as FSx for ONTAP
- [ ] FSx for ONTAP S3 Access Point (`AVAILABLE` lifecycle)
- [ ] IAM role for Snowflake with S3 AP permissions (GetObject, ListBucket)
- [ ] Sample data on FSx for ONTAP (Parquet at `sensor-data/sensor_data.parquet`)

## Step-by-Step

### Step 1: Storage Integration

Run `01-storage-integration.sql` in Snowflake:

```sql
CREATE OR REPLACE STORAGE INTEGRATION fsxn_poc_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/<ROLE_NAME>'
  STORAGE_ALLOWED_LOCATIONS = ('s3://<AP_ALIAS>/');
```

Then run `DESC INTEGRATION fsxn_poc_integration;` and note:
- `STORAGE_AWS_IAM_USER_ARN` → Add to IAM role trust policy
- `STORAGE_AWS_EXTERNAL_ID` → Add to IAM role trust policy condition

### Step 2: Update IAM Trust Policy

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"AWS": "<STORAGE_AWS_IAM_USER_ARN from Step 1>"},
    "Action": "sts:AssumeRole",
    "Condition": {"StringEquals": {"sts:ExternalId": "<STORAGE_AWS_EXTERNAL_ID from Step 1>"}}
  }]
}
```

### Step 3: Create Stage + External Table

Run `02-stage-and-table.sql`:

```sql
-- CRITICAL: Include AWS_ACCESS_POINT_ARN — without it, SELECT fails
CREATE OR REPLACE STAGE fsxn_poc_stage
  STORAGE_INTEGRATION = fsxn_poc_integration
  URL = 's3://<AP_ALIAS>/'
  AWS_ACCESS_POINT_ARN = 'arn:aws:s3:<REGION>:<ACCOUNT_ID>:accesspoint/<AP_NAME>'
  FILE_FORMAT = (TYPE = PARQUET);

-- Verify
LIST @fsxn_poc_stage/sensor-data/;
SELECT $1 FROM @fsxn_poc_stage/sensor-data/sensor_data.parquet LIMIT 3;
```

### Step 4: Cortex AI Demo

Run `03-cortex-ai-demo.sql` for AI functions on FSx data (zero-copy):
- SUMMARIZE — text summarization
- SENTIMENT — sentiment scoring
- TRANSLATE — multi-language
- COMPLETE — AI analysis
- PARSE_DOCUMENT — OCR on images

## Connecting to Demo Guide

After completing Steps 1-3, you can run all demos in the [AI Demo Guide](../../integrations/snowflake/docs/en/ai-demo-guide.md) by substituting:

| Demo Guide uses | PoC Template creates | They are the same if... |
|---|---|---|
| `@fsxn_stage` | `@fsxn_poc_stage` | Use same name, or `ALTER STAGE RENAME` |
| `fsxn_sensor_ext_table` | `fsxn_poc_sensor_ext` | Use same name in CREATE EXTERNAL TABLE |
| `fsxn_verification_integration` | `fsxn_poc_integration` | Use same name |

**Tip**: To match the demo guide exactly, replace `fsxn_poc_` with `fsxn_` in all SQL scripts before running.

## After This Module

- **Dynamic Table**: Add `CREATE DYNAMIC TABLE ... AS SELECT ... FROM fsxn_poc_sensor_ext` for automated enrichment
- **Cortex Search (RAG)**: `COPY INTO` → internal table → `CREATE CORTEX SEARCH SERVICE`
- **Data Sharing**: `GRANT SELECT ON TABLE fsxn_poc_sensor_ext TO SHARE ...`
- **Full documentation**: See [Blog Part 3](https://dev.to/aws-builders/snowflake-and-fsx-for-ontap-s3-access-points-from-access-denied-to-working-external-tables-9k8)
- **Internal Table guide**: See [Internal Table Ingestion Guide](../../integrations/snowflake/docs/en/internal-table-ingestion-guide.md)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| LIST works, SELECT fails "access denied" | Missing `AWS_ACCESS_POINT_ARN` | Add ARN parameter to stage |
| Integration creation fails | IAM role ARN incorrect | Verify role exists and ARN format |
| "Insufficient privileges" | Not using ACCOUNTADMIN or SYSADMIN | Switch to appropriate role |
| External Table returns 0 rows | File path mismatch | Verify with `LIST @stage/sensor-data/` |
| Cortex function error | Model not available in region | Enable Cross-Region Inference or use available model |

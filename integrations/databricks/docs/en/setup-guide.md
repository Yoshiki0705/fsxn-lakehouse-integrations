# Databricks Setup Guide

## Overview

Configure FSx for NetApp ONTAP as a Databricks Unity Catalog External Location
to use as the storage layer for Delta Lake / Iceberg tables.

## Prerequisites

- AWS account with FSx for NetApp ONTAP deployed
- FSx for ONTAP SVM with S3 protocol enabled
- Databricks workspace (Unity Catalog enabled)
- AWS CLI v2 configured
- Terraform 1.5+ (for Unity Catalog resource management)

## Architecture

```
Databricks Unity Catalog
    │
    ├── Storage Credential (IAM Role)
    │       │
    │       └── AssumeRole ──→ fsxn-lakehouse-databricks-s3-role
    │
    └── External Location
            │
            └── s3://<s3ap-alias>/ ──→ S3 Access Point ──→ FSx for ONTAP Volume
```

## Step 1: Deploy CloudFormation Stack

### Parameter Preparation

| Parameter | Description | Example |
|-----------|-------------|---------|
| S3BucketName | FSx for ONTAP SVM S3 bucket name | `svm-lakehouse` |
| VpcId | VPC where FSx for ONTAP resides | `vpc-0123456789abcdef0` |
| SubnetIds | Platform subnets | `subnet-xxx,subnet-yyy` |
| DatabricksAccountId | Databricks AWS account | `414351767826` |
| DatabricksWorkspaceId | Workspace ID | `1234567890` |
| ExternalId | External ID (see below) | Obtained from Databricks UI |

### Deploy Command

```bash
aws cloudformation deploy \
  --template-file integrations/databricks/template.yaml \
  --stack-name fsxn-databricks-integration \
  --parameter-overrides \
    S3BucketName=svm-lakehouse \
    VpcId=vpc-0123456789abcdef0 \
    SubnetIds=subnet-xxx,subnet-yyy \
    DatabricksWorkspaceId=1234567890 \
    ExternalId=<databricks-external-id> \
  --capabilities CAPABILITY_NAMED_IAM \
  --region <YOUR_REGION>
```

### Check Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name fsxn-databricks-integration \
  --query 'Stacks[0].Outputs' \
  --output table
```

Key outputs:
- `DatabricksRoleArn` — Used for Storage Credential
- `S3AccessPointAlias` — Used in External Location URL

## Step 2: Obtain External ID

1. Log in to Databricks workspace
2. Navigate to **Catalog** → **External Data** → **Storage Credentials** → **Create credential**
3. Select **AWS IAM Role**
4. Copy the displayed **External ID**
5. Update CloudFormation stack with the correct `ExternalId` parameter

## Step 3: Create Storage Credential

### Using Terraform

```bash
cd integrations/databricks/terraform

terraform init
terraform plan \
  -var="databricks_workspace_url=https://xxx.cloud.databricks.com" \
  -var="databricks_account_id=your-account-id" \
  -var="s3_access_point_alias=<cfn-output-alias>" \
  -var="s3_access_point_arn=<cfn-output-arn>" \
  -var="iam_role_arn=<cfn-output-role-arn>" \
  -var="metastore_id=<your-metastore-id>"

terraform apply
```

### Using Databricks UI

1. **Catalog** → **External Data** → **Storage Credentials**
2. Click **Create credential**
3. Configure:
   - Name: `fsxn-lakehouse-fsxn-credential`
   - IAM Role ARN: `DatabricksRoleArn` from CloudFormation output
4. Click **Create**

## Step 4: Create External Location

### Using Databricks UI

1. **Catalog** → **External Data** → **External Locations**
2. Click **Create location**
3. Configure:
   - Name: `fsxn-lakehouse-root`
   - URL: `s3://<S3AccessPointAlias>/`
   - Storage Credential: `fsxn-lakehouse-fsxn-credential`
4. Click **Test connection** to validate
5. Click **Create**

## Step 5: Validate Connectivity

Run notebook `01_setup_external_location.py` to verify the connection.

```python
# Execute in Databricks notebook
files = dbutils.fs.ls("s3://<s3ap-alias>/")
print(f"Files found: {len(files)}")
```

## Step 6: Create Tables

Run notebooks in order:

1. `02_create_external_table.py` — Parquet/CSV/JSON tables
2. `03_delta_lake_on_fsxn.py` — Delta Lake tables
3. `04_iceberg_on_fsxn.py` — Iceberg tables

## Troubleshooting

### Issue: Storage Credential test fails

**Cause**: IAM Role trust policy missing External ID

**Resolution**:
1. Verify the `ExternalId` parameter in CloudFormation
2. Update the stack with the correct External ID

### Issue: External Location test returns "Access Denied"

**Cause**: S3 AP policy does not allow the IAM Role

**Resolution**:
1. Verify S3 AP policy Principal matches the Role ARN
2. Check VPC condition is correct
3. Confirm IAM Role policy includes S3 AP ARN

### Issue: ListObjects returns empty

**Cause**: No data in FSx for ONTAP SVM S3 bucket, or incorrect path

**Resolution**:
1. Verify S3 bucket contents via ONTAP CLI
2. Check S3 AP path prefix
3. Run sample data generator

## Next Steps

- [Unity Catalog Integration Details](unity-catalog-integration.md)
- [Notebook 05: ML Feature Store](../../notebooks/05_ml_feature_store.py)
- [Notebook 06: Snapshot + Time Travel](../../notebooks/06_snapshot_time_travel.py)

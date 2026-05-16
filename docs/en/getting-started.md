# Quick Start Guide

🌐 [日本語](../ja/getting-started.md)

## Prerequisites

- AWS Account
- FSx for NetApp ONTAP file system (deployed)
- S3 Access Point enabled on FSxN SVM
- AWS CLI v2 configured
- Python 3.12+

## Step 1: Clone Repository

```bash
git clone https://github.com/Yoshiki0705/fsxn-lakehouse-integrations.git
cd fsxn-lakehouse-integrations
```

## Step 2: Deploy Base Infrastructure

### VPC + Networking

```bash
aws cloudformation deploy \
  --template-file shared/cloudformation/vpc-networking.yaml \
  --stack-name fsxn-lakehouse-vpc \
  --capabilities CAPABILITY_IAM \
  --region ap-northeast-1
```

### FSxN + S3 Access Point

```bash
aws cloudformation deploy \
  --template-file shared/cloudformation/fsxn-s3ap-base.yaml \
  --stack-name fsxn-lakehouse-base \
  --parameter-overrides \
    VpcId=<vpc-id> \
    PreferredSubnetId=<subnet-1> \
    StandbySubnetId=<subnet-2> \
    FSxNSecurityGroupId=<sg-id> \
    S3BucketName=<svm-bucket-name> \
  --capabilities CAPABILITY_IAM \
  --region ap-northeast-1
```

## Step 3: Validate Connectivity

```bash
# Get S3 AP alias from CloudFormation output
AP_ALIAS=$(aws cloudformation describe-stacks \
  --stack-name fsxn-lakehouse-base \
  --query 'Stacks[0].Outputs[?OutputKey==`S3AccessPointAlias`].OutputValue' \
  --output text)

# Run connectivity test
python shared/scripts/validate-access.py --access-point-alias $AP_ALIAS
```

## Step 4: Choose Vendor Integration

| Vendor | Directory | Status |
|--------|-----------|--------|
| Databricks | `integrations/databricks/` | ✅ Implemented |
| Snowflake | `integrations/snowflake/` | ✅ Implemented |
| Athena | `integrations/athena/` | 🚧 Planned |
| Glue | `integrations/glue/` | 🚧 Planned |

See each vendor's `README.md` and `docs/en/setup-guide.md` for details.

## Next Steps

- [Architecture Overview](architecture.md)
- [S3 AP Fundamentals](s3ap-fundamentals.md)
- [Vendor Comparison](vendor-comparison.md)

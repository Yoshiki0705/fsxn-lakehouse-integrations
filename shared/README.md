# Shared Resources / 共通リソース

Reusable CloudFormation templates, scripts, and utilities for all integrations.

## CloudFormation Templates

| Template | Purpose | Used By |
|----------|---------|---------|
| `cloudformation/vpc-networking.yaml` | VPC + subnets + NAT + VPC endpoints | All integrations |
| `cloudformation/fsxn-s3ap-base.yaml` | FSx for ONTAP + SVM + volumes + S3 AP | All integrations |
| `cloudformation/iam-policies.yaml` | Reusable IAM policy fragments | All integrations |
| `cloudformation/fpolicy-server-fargate.yaml` | FPolicy event server (ECS Fargate) | Event-driven patterns |
| `cloudformation/fpolicy-ingestion.yaml` | SQS + Lambda bridge for FPolicy events | Event-driven patterns |
| `cloudformation/fpolicy-routing.yaml` | EventBridge routing to targets | Event-driven patterns |
| `cloudformation/fpolicy-ip-updater.yaml` | Auto-update FPolicy IP on task restart | Event-driven patterns |
| `cloudformation/sample-data-generator.yaml` | Lambda for generating test data | Testing |

## Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/validate-access.py` | Validate S3 AP connectivity (List, Get, Put, Delete) | `python validate-access.py --access-point-alias <alias>` |
| `scripts/verify-s3ap-connectivity.py` | Comprehensive S3 AP check with YAML output | `python verify-s3ap-connectivity.py --ap-alias <alias> --output-yaml <path>` |
| `scripts/generate-sample-data.py` | Generate Parquet/CSV/JSON test data | `python generate-sample-data.py --rows 10000 --format parquet` |
| `scripts/generate-test-data.py` | Generate sensor_data Parquet (10K/5M rows) | `python generate-test-data.py --ap-alias <alias> --rows 10000` |
| `scripts/upload-media-samples.sh` | Upload images/documents/video to FSx for ONTAP | `./upload-media-samples.sh <nfs-mount-path>` |
| `scripts/setup-s3ap.sh` | Create and configure S3 Access Point | `./setup-s3ap.sh` |
| `scripts/mask-screenshots.py` | Mask PII in screenshots | `python mask-screenshots.py <image-path>` |
| `scripts/pre-push-security-check.sh` | Check for secrets before push | `./pre-push-security-check.sh` |

## FPolicy Server

| File | Purpose |
|------|---------|
| `fpolicy-server/fpolicy_server.py` | FPolicy binary protocol server (Python) |
| `fpolicy-server/Dockerfile` | Container image for ECS Fargate |
| `fpolicy-server/schemas/fpolicy-event-schema.json` | Event schema definition |

## Quick Start

```bash
# 1. Deploy base infrastructure
aws cloudformation deploy \
  --template-file shared/cloudformation/vpc-networking.yaml \
  --stack-name fsxn-vpc --capabilities CAPABILITY_IAM

aws cloudformation deploy \
  --template-file shared/cloudformation/fsxn-s3ap-base.yaml \
  --stack-name fsxn-base --capabilities CAPABILITY_IAM \
  --parameter-overrides VpcId=<vpc-id> ...

# 2. Validate connectivity
python shared/scripts/validate-access.py \
  --access-point-alias <your-ap-alias> \
  --region ap-northeast-1

# 3. Generate test data
python shared/scripts/generate-test-data.py \
  --ap-alias <your-ap-alias> \
  --rows 10000

# 4. Choose integration: integrations/<vendor>/README.md
```

## Prerequisites

- AWS CLI v2 configured
- Python 3.9+ with boto3, pandas, pyarrow
- Docker (for FPolicy server and DuckDB Lambda layer)
- FSx for ONTAP with S3 Access Point enabled (ONTAP 9.17.1+)

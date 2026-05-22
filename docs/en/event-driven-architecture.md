# Event-Driven Architecture (FPolicy Integration)

## Overview

Leveraging ONTAP FPolicy to detect NFS/SMB file operations in real-time and
automatically trigger pipelines across Lakehouse services (Databricks, Snowflake,
Glue, Athena, EMR).

This architecture replaces traditional polling-based approaches (minute-level latency)
with event-driven patterns (second-level latency) for near-real-time data ingestion.

## Architecture Overview

```
NFS/SMB File Operations
    → ONTAP FPolicy (File Event Detection)
        → ECS Fargate (FPolicy Server — Binary Protocol Processing)
            → SQS (Event Buffering)
                → Lambda (Bridge — Convert to EventBridge Format)
                    → EventBridge Custom Bus (Routing)
                        ├── Databricks Jobs API (Spark Job Trigger)
                        ├── SNS → Snowpipe (Real-time Ingestion)
                        ├── Glue Job (Automated ETL)
                        ├── Glue Crawler (Auto Schema Update → Athena)
                        └── Step Functions → EMR Step (Large-scale Batch)
```

## Vendor Integration Patterns

### Databricks: FPolicy → Databricks Job API

```
FPolicy → SQS → Lambda → EventBridge → API Destination → Databricks Jobs API
```

- **Latency**: <2 seconds (file operation → job start)
- **Use cases**: New data ingestion, image processing, document processing
- **Authentication**: Databricks PAT (stored in Secrets Manager)

### Snowflake: FPolicy → SNS → Snowpipe

```
FPolicy → SQS → Lambda → EventBridge → SNS → Snowflake SQS → Snowpipe → COPY INTO
```

- **Latency**: <30 seconds (file operation → table available)
- **Improvement**: Lambda polling (5-7 min) → FPolicy (30 sec) = 90%+ reduction
- **Use cases**: Streaming ingestion, near-real-time analytics

### Glue: FPolicy → EventBridge → Glue Job

```
FPolicy → SQS → Lambda → EventBridge → Glue Job (Bronze → Silver ETL)
```

- **Latency**: <5 seconds (file operation → job start)
- **Improvement**: Scheduled execution (minutes) → event-driven (seconds)
- **Use cases**: Medallion Architecture ETL, data quality checks

### Athena: FPolicy → Glue Crawler → Data Catalog

```
FPolicy → SQS → Lambda → EventBridge → Glue Crawler → Data Catalog Update
```

- **Latency**: <60 seconds (file operation → Athena queryable)
- **Use cases**: Auto schema discovery, auto partition addition

### EMR: FPolicy → Step Functions → EMR Step

```
FPolicy → SQS → Lambda → EventBridge → Step Functions → EMR AddStep
```

- **Latency**: <10 seconds (file operation → EMR step start)
- **Use cases**: Large-scale batch processing, ML pipelines

## Latency Comparison

| Vendor | Polling Approach | FPolicy Approach | Improvement |
|--------|-----------------|-----------------|-------------|
| Databricks | N/A (manual) | <2 sec | — |
| Snowflake (Snowpipe) | 5-7 min | <30 sec | 90%+ |
| Glue | Minutes (schedule) | <5 sec | 95%+ |
| Athena (Crawler) | Minutes (schedule) | <60 sec | 90%+ |
| EMR | N/A (manual) | <10 sec | — |

## CloudFormation Templates

| Template | Path | Description |
|----------|------|-------------|
| FPolicy Server | `shared/cloudformation/fpolicy-server-fargate.yaml` | ECS Fargate + FPolicy binary protocol |
| FPolicy Ingestion | `shared/cloudformation/fpolicy-ingestion.yaml` | SQS + Lambda Bridge + EventBridge Custom Bus |
| FPolicy Routing | `shared/cloudformation/fpolicy-routing.yaml` | EventBridge rules + various targets |

## Deployment Steps

### Step 1: FPolicy Ingestion Stack

```bash
aws cloudformation deploy \
  --template-file shared/cloudformation/fpolicy-ingestion.yaml \
  --stack-name fsxn-fpolicy-ingestion \
  --parameter-overrides \
    VpcId=<VPC_ID> \
    PrivateSubnetIds=<SUBNET_1>,<SUBNET_2> \
    VpcEndpointSecurityGroupId=<SG_ID> \
  --capabilities CAPABILITY_NAMED_IAM
```

### Step 2: FPolicy Server Stack

```bash
aws cloudformation deploy \
  --template-file shared/cloudformation/fpolicy-server-fargate.yaml \
  --stack-name fsxn-fpolicy-server \
  --parameter-overrides \
    VpcId=<VPC_ID> \
    SubnetIds=<PRIVATE_SUBNET_1>,<PRIVATE_SUBNET_2> \
    FSxNSecurityGroupId=<FSXN_SG_ID> \
    SQSQueueArn=<QUEUE_ARN> \
    SQSQueueUrl=<QUEUE_URL> \
  --capabilities CAPABILITY_IAM
```

### Step 3: FPolicy Routing Stack (per target)

```bash
# For Glue Job
aws cloudformation deploy \
  --template-file shared/cloudformation/fpolicy-routing.yaml \
  --stack-name fsxn-fpolicy-routing-glue \
  --parameter-overrides \
    TargetType=GLUE_JOB \
    GlueJobName=fsxn-bronze-to-silver \
  --capabilities CAPABILITY_IAM

# For Snowpipe
aws cloudformation deploy \
  --template-file shared/cloudformation/fpolicy-routing.yaml \
  --stack-name fsxn-fpolicy-routing-snowpipe \
  --parameter-overrides \
    TargetType=SNS_SNOWPIPE \
    SNSTopicArn=arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:snowpipe-notify \
  --capabilities CAPABILITY_IAM
```

### Step 4: ONTAP FPolicy Configuration

```bash
# Get Fargate task IP
TASK_ARN=$(aws ecs list-tasks --cluster fsxn-fpolicy-server-fpolicy-cluster \
  --desired-status RUNNING --query 'taskArns[0]' --output text)
TASK_IP=$(aws ecs describe-tasks --cluster fsxn-fpolicy-server-fpolicy-cluster \
  --tasks $TASK_ARN \
  --query 'tasks[0].attachments[0].details[?name==`privateIPv4Address`].value' \
  --output text)

# Configure FPolicy via ONTAP REST API
# See: fpolicy-configuration-reference.md
```

### Step 5: Test

```bash
# NFS mount (vers=4.1 required)
sudo mount -t nfs -o vers=4.1 <SVM_IP>:/vol1 /mnt/fsxn

# Create test file
echo "fpolicy-test" > /mnt/fsxn/test-file.parquet

# Verify SQS message
aws sqs receive-message --queue-url <QUEUE_URL> --max-number-of-messages 5
```

## Important Constraints

| Constraint | Details | Workaround |
|-----------|---------|-----------|
| **NFSv4.2 not supported** | FPolicy does not support NFSv4.2 monitoring. `mount -o vers=4` negotiates to NFSv4.2 | Use `vers=4.1` or `vers=3` explicitly |
| **NLB incompatible** | FPolicy binary framing does not work with NLB TCP passthrough | Specify Fargate task IP directly in ONTAP external-engine |
| **SMB requires AD** | CIFS server must be joined to Active Directory | Not required for NFS-only |
| **SQS VPC Endpoint required** | Fargate (Private Subnet) needs path to SQS | Create Interface VPC Endpoint |
| **Direct IP connection** | ONTAP external-engine requires Fargate task's direct Private IP | Auto-update script needed on task restart |

## Cost Estimate

| Component | Monthly Cost (approx.) | Notes |
|-----------|----------------------|-------|
| ECS Fargate (0.25 vCPU, 0.5GB) | ~$15 | 24/7 running |
| SQS | ~$0.50 | Depends on message volume |
| Lambda (Bridge) | ~$1 | Depends on event count |
| EventBridge | ~$1 | Rule evaluation + event delivery |
| SQS VPC Endpoint | ~$7 | Interface Endpoint |
| **Total** | **~$25/month** | |

## Reference Repository

- [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns)
  - `docs/event-driven/architecture-design.md` — Architecture comparison
  - `docs/event-driven/fpolicy-configuration-reference.md` — FPolicy configuration reference
  - `docs/event-driven/fpolicy-e2e-verification-report.md` — E2E verification report
  - `shared/cfn/fpolicy-server-fargate.yaml` — Reference template
  - `shared/cfn/fpolicy-ingestion.yaml` — Reference template
  - `shared/cfn/fpolicy-routing.yaml` — Reference template

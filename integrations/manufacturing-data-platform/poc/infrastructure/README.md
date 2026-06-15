# PoC Infrastructure

🌐 **English** | [日本語](README-ja.md)

---

## Overview

CloudFormation templates for the manufacturing data platform PoC infrastructure.

## Components

| Template | Service | Purpose |
|----------|---------|---------|
| `msk-serverless.yaml` | Amazon MSK Serverless | Kafka event backbone |

## Prerequisites

- AWS CLI configured with appropriate permissions
- A VPC with at least 2 private subnets in different AZs
- VPC endpoints for S3 and STS (recommended)

## Deployment

### Step 1: Deploy MSK Serverless

```bash
# Replace placeholder values with your VPC/subnet IDs
aws cloudformation deploy \
  --template-file msk-serverless.yaml \
  --stack-name manufacturing-poc-msk \
  --parameter-overrides \
    VpcId=vpc-xxxxxxxxx \
    SubnetIds=subnet-aaa,subnet-bbb \
    ClusterName=manufacturing-poc-msk \
    Environment=poc \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-northeast-1
```

### Step 2: Get Bootstrap Servers

```bash
# Get the cluster ARN from stack outputs
CLUSTER_ARN=$(aws cloudformation describe-stacks \
  --stack-name manufacturing-poc-msk \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterArn`].OutputValue' \
  --output text \
  --region ap-northeast-1)

# Get bootstrap servers
aws kafka get-bootstrap-brokers \
  --cluster-arn "$CLUSTER_ARN" \
  --region ap-northeast-1
```

The output will include `BootstrapBrokerStringSaslIam` — use this as `KAFKA_BOOTSTRAP_SERVERS`.

### Step 3: Configure ClickHouse Cloud Connection

1. Go to ClickHouse Cloud console → your service → Settings → Networking
2. Add PrivateLink or configure IP allowlist for MSK endpoints
3. Create Kafka Engine table in ClickHouse:

```sql
-- Example: Kafka Engine table for sensor data
CREATE TABLE factory.sensor_data_kafka (
    raw String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = '<bootstrap-servers>',
    kafka_topic_list = 'factory.sensor-data',
    kafka_group_name = 'clickhouse-consumer-sensor',
    kafka_format = 'JSONEachRow',
    kafka_security_protocol = 'SASL_SSL',
    kafka_sasl_mechanism = 'AWS_MSK_IAM';
```

> **Note**: ClickHouse Cloud + MSK IAM auth connectivity needs validation.
> [仮説] MSK IAM auth may require ClickHouse BYOC or self-managed for VPC-local access.
> See ADR-006 for fallback options.

### Step 4: Configure Databricks Connection

1. In Databricks workspace, configure VPC peering or PrivateLink to the VPC containing MSK
2. Use the following Structured Streaming configuration:

```python
kafka_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "<bootstrap-servers>")
    .option("subscribe", "factory.sensor-data")
    .option("kafka.security.protocol", "SASL_SSL")
    .option("kafka.sasl.mechanism", "AWS_MSK_IAM")
    .option("kafka.sasl.jaas.config",
            "software.amazon.msk.auth.iam.IAMLoginModule required;")
    .option("kafka.sasl.client.callback.handler.class",
            "software.amazon.msk.auth.iam.IAMClientCallbackHandler")
    .load()
)
```

## Cleanup

```bash
aws cloudformation delete-stack \
  --stack-name manufacturing-poc-msk \
  --region ap-northeast-1
```

## Architecture References

- [ADR-001](../../docs/adr/ADR-001.md) — Kafka as factory event backbone
- [ADR-006](../../docs/adr/ADR-006.md) — ClickHouse Cloud as PoC deployment model
- [DES-003](../../docs/en/03_architecture_design.md) — Kafka topic design
- [DES-008](../../docs/en/03_architecture_design.md) — Network architecture

## Security Notes

- MSK Serverless uses IAM authentication only (no username/password)
- Security group restricts access to VPC CIDR (10.0.0.0/16)
- No public access endpoints
- All credentials managed via IAM roles, not static keys

## Cost Estimate

MSK Serverless pricing (PoC workload):
- Cluster hours: ~$0.75/hour per partition-hour (min 1 partition per topic)
- Storage: $0.10/GB-month
- Data in/out: $0.10/GB

Estimated PoC cost: **$50-150/month** for low-throughput testing.

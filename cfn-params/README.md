# CloudFormation Parameter Files

Example parameter files for `aws cloudformation create-stack --parameters file://cfn-params/<file>.json`.

## Usage

```bash
# Copy and customize
cp cfn-params/athena.example.json cfn-params/athena.json
# Edit with your actual values
vim cfn-params/athena.json
# Deploy
aws cloudformation create-stack \
  --stack-name fsxn-athena-dev \
  --template-body file://integrations/athena/template.yaml \
  --parameters file://cfn-params/athena.json \
  --capabilities CAPABILITY_NAMED_IAM
```

> **Security note**: After customizing example files with real values (account IDs, VPC IDs, External IDs), do NOT commit them to version control. Add `cfn-params/*.json` (without `.example`) to `.gitignore`, or use environment-specific naming like `cfn-params/athena.prod.json`.

## Format

Standard AWS CLI parameter JSON format:

```json
[
  {"ParameterKey": "KeyName", "ParameterValue": "value"}
]
```

## Placeholder Values

| Placeholder | Replace With |
|---|---|
| `vpc-0EXAMPLE` | Your VPC ID |
| `subnet-0EXAMPLE*` | Your subnet IDs |
| `sg-0EXAMPLE` | Your security group ID |
| `fs-0EXAMPLE` | Your FSx for ONTAP file system ID |
| `svm-0EXAMPLE` | Your SVM ID |
| `vol-0EXAMPLE` | Your volume ID |
| `198.51.100.x` | Your actual IPs (RFC 5737 documentation range) |
| `123456789012` | Your AWS account ID |
| `YOUR-*` | Your actual resource names/aliases |

## File Inventory

| File | Template | Deployment Path |
|---|---|---|
| `athena.example.json` | `integrations/athena/template.yaml` | Path 1 |
| `glue.example.json` | `integrations/glue/template.yaml` | Path 2 |
| `duckdb.example.json` | `integrations/duckdb/template.yaml` | Path 3 |
| `snowflake-phase1.example.json` | `integrations/snowflake/template.yaml` | Path 4 (Phase 1) |
| `snowflake-phase2.example.json` | `integrations/snowflake/template.yaml` | Path 4 (Phase 2) |
| `databricks-network.example.json` | `integrations/databricks/customer-vpc-network.yaml` | Path 6 (Step 1) |
| `databricks.example.json` | `integrations/databricks/template.yaml` | Path 6 (Step 2) |
| `fpolicy-routing.example.json` | `shared/cloudformation/fpolicy-routing.yaml` | Path 5 (E1) |
| `fpolicy-ingestion.example.json` | `shared/cloudformation/fpolicy-ingestion.yaml` | Path 5 (E2) |
| `fpolicy-server.example.json` | `shared/cloudformation/fpolicy-server-fargate.yaml` | Path 5 (E3) |
| `fpolicy-ip-updater.example.json` | `shared/cloudformation/fpolicy-ip-updater.yaml` | Path 5 (E4) |
| `iam-policies.example.json` | `shared/cloudformation/iam-policies.yaml` | Shared |
| `opensharing-server.example.json` | `integrations/opensharing-server/template.yaml` | OpenSharing |
| `delta-lake-oss.example.json` | `integrations/delta-lake-oss/template.yaml` | Delta Lake |
| `iceberg-s3-tables.example.json` | `integrations/iceberg-metadata-catalog/cloudformation/s3-tables-setup.yaml` | Iceberg |
| `snapmirror-flexcache.example.json` | `integrations/snapmirror-flexcache-multicloud/template.yaml` | SnapMirror/FlexCache validation |

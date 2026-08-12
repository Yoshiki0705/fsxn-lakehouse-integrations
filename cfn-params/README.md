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

---

## `databricks-uc-storage-credential.example.json`

For `integrations/databricks/uc-storage-credential-role.yaml` — the IAM role a Databricks
Unity Catalog storage credential assumes to reach an FSx for ONTAP S3 Access Point, plus an
optional native S3 bucket used as a control.

> Parameter files accept only `ParameterKey`, `ParameterValue`, `UsePreviousValue` and
> `ResolvedValue`. A `_comment` key makes the CLI fail with
> `Unknown parameter in Parameters[n]`, which is why the guidance lives here rather than
> inline.

### Where each value comes from

| Parameter | How to get it |
|---|---|
| `DatabricksAccountId` | The account UUID in the Databricks account console URL (`account_id=…`). **This is the external ID.** |
| `DatabricksUnityCatalogAwsAccountId` | `414351767826` for the AWS commercial control plane as observed 2026-08. Re-confirm against Databricks documentation — an account ID pinned in a template is exactly the value that goes stale quietly. |
| `S3AccessPointName` | `aws fsx describe-s3-access-point-attachments --region <region> --query 'S3AccessPointAttachments[].{name:Name,alias:S3AccessPoint.Alias}' --output table` |
| `S3AccessPointAlias` | The `alias` column from the same command. Ends in `-s3alias`. |
| `RoleName` | Your choice. Lowercase, ≤ 40 characters — the control bucket is named `<RoleName>-ctl-<account id>` and must stay inside S3's 63-character limit. |
| `CreateControlBucket` | Keep `yes`. See below. |
| `ControlBucketName` | Leave empty unless you need a specific name. |

### Two values that are easy to get wrong

Both produce a `403` that reads as "S3 Access Points are not supported", which is how this
repository carried an incorrect blocker for three months.

1. **The external ID is the account UUID.** Not the metastore ID, not the workspace ID.
2. **The IAM policy needs the access point ARN**, not just the alias-as-bucket ARN. The
   template grants both, so this only bites if you hand-write the policy.

There is an asymmetry worth remembering: the **external location URL** must use the alias
form (`s3://<alias>/`) — the ARN-style URL is rejected with `url does not specify a valid
bucket name` — while the **IAM policy** wants the access point ARN form.

### Why the control bucket is not optional in practice

A failure with no control tells you nothing. It could be the platform, or it could be your
own IAM setup. With a native S3 path running the identical query in the same session, the
comparison is decisive: if the control works and the Access Point does not, the difference
is on the platform side.

### Deploy

```bash
cp cfn-params/databricks-uc-storage-credential.example.json \
   cfn-params/databricks-uc-storage-credential.json
# edit the copy with your values

aws cloudformation deploy \
  --region <region> \
  --stack-name fsxn-databricks-uc-credential \
  --template-file integrations/databricks/uc-storage-credential-role.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides file://cfn-params/databricks-uc-storage-credential.json
```

`aws cloudformation deploy --parameter-overrides` also accepts `Key=Value` pairs directly if
you prefer not to keep a file.

The stack outputs the role ARN, both external location URLs, and the command that runs the
registration and the comparison. Expected result as of 2026-08-12: registration succeeds on
both locations, reads succeed on the control and are denied on the Access Point. See
[BLK-001](../docs/en/blocker-tracker.md#blk-001-uc-credential-vending-does-not-authorise-s3-ap-reads).

# Databricks + AWS Audit Correlation Guide

🌐 [日本語](audit-correlation-guide-ja.md) | English

## Purpose

Define how to correlate audit events across Databricks Unity Catalog and AWS services for end-to-end incident investigation.

## Audit Sources

| Source | What it captures | Retention |
|---|---|---|
| Databricks `system.access.audit` | UC metadata queries, credential issuance, table access | System table (configurable) |
| AWS CloudTrail | API calls (Glue, S3, Lake Formation, Bedrock) | 90 days (event history) or S3 Trail (configurable) |
| S3 Access Logs | Object-level reads/writes on S3 AP | S3 bucket (configurable) |
| Lake Formation audit | Data access via LF-governed tables | CloudTrail |
| OpenSearch audit | Search queries and index operations | CloudWatch Logs |

## Correlation Keys

| Databricks field | AWS field | Correlation method |
|---|---|---|
| `user_identity.email` | CloudTrail `userIdentity.arn` | Map Databricks user → IAM role assumed |
| `service_name = 'uniformIcebergRestCatalog'` | — | Identifies external engine access |
| `action_name = 'loadTableCredentials'` | CloudTrail `AssumeRole` | Credential issuance → role assumption |
| `request_params.table_name` | Glue `GetTable` / S3 `GetObject` | Table → underlying S3 path |
| `source_ip_address` | CloudTrail `sourceIPAddress` | Network correlation |
| `event_time` | CloudTrail `eventTime` | Temporal correlation (±5 min window) |

## Investigation Workflow

### Scenario: "Who accessed sensitive metadata from Databricks?"

```sql
-- Step 1: Query Databricks audit for metadata table access
SELECT
  event_time,
  user_identity.email,
  action_name,
  request_params.full_name_arg AS table_accessed,
  source_ip_address
FROM system.access.audit
WHERE service_name = 'unityCatalog'
  AND request_params.full_name_arg LIKE '%unstructured_files%'
  AND event_date >= '2026-06-01'
ORDER BY event_time DESC;
```

```sql
-- Step 2: Query CloudTrail for corresponding AWS API calls
-- (via Athena on CloudTrail logs)
SELECT
  eventtime,
  useridentity.arn,
  eventsource,
  eventname,
  requestparameters
FROM cloudtrail_logs
WHERE eventsource = 'glue.amazonaws.com'
  AND eventname IN ('GetTable', 'GetDatabase')
  AND eventtime >= '2026-06-01'
ORDER BY eventtime DESC;
```

### Scenario: "Did credential vending lead to raw file access?"

```sql
-- Step 1: Find credential issuance in Databricks audit
SELECT
  event_time,
  user_identity.email,
  action_name,
  request_params
FROM system.access.audit
WHERE service_name = 'uniformIcebergRestCatalog'
  AND action_name = 'loadTableCredentials'
ORDER BY event_time DESC;

-- Step 2: Correlate with S3 access logs
-- Look for AssumeRole events within 5 minutes of credential issuance
-- Then check S3 GetObject calls from the assumed role
```

## Audit Gap: Post-Credential File Access

Databricks UC audit logs record **credential issuance**, not individual S3 file reads after credentials are vended. To achieve file-level audit:

1. Enable S3 Access Logging on the S3 Tables bucket
2. Enable CloudTrail data events for S3
3. Correlate the assumed role ARN from credential issuance with S3 access logs
4. Consider AWS Config rules for compliance monitoring

## Recommended Dashboard

| Panel | Data source | Query |
|---|---|---|
| Metadata queries/day | `system.access.audit` | COUNT by day, grouped by user |
| Credential issuance events | `system.access.audit` | WHERE action = 'loadTableCredentials' |
| S3 Tables API calls | CloudTrail | WHERE eventsource = 's3tables' |
| Lake Formation grants/revokes | CloudTrail | WHERE eventsource = 'lakeformation' |
| Failed access attempts | Both | WHERE errorCode IS NOT NULL |

## References

- [Databricks system.access.audit](https://docs.databricks.com/aws/en/admin/system-tables/audit)
- [AWS CloudTrail](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/)
- [Lake Formation audit logging](https://docs.aws.amazon.com/lake-formation/latest/dg/cloudtrail-logging.html)

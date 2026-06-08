# Regulated Workload Readiness Checklist

## Purpose

Checklist for deploying the AI-powered metadata catalog in regulated industries (public sector, healthcare, financial services, education).

## Data Residency

| Requirement | Design | Evidence |
|-------------|--------|----------|
| Raw files remain in designated region | FSx for ONTAP in single region | FSx file system ARN |
| Metadata remains in designated region | S3 Tables in same region | Table bucket ARN |
| AI processing in same region | Bedrock endpoint in same region | API endpoint URL |
| No cross-border data transfer | All services in same region | VPC flow logs |

## Encryption

| Layer | Method | Key Management |
|-------|--------|---------------|
| Raw files at rest | FSx for ONTAP encryption | AWS KMS or FSx-managed |
| Metadata at rest | S3 Tables SSE-S3 | AWS-managed |
| In transit | TLS 1.2+ (all API calls) | AWS default |
| OpenSearch at rest | AWS-managed encryption | Serverless default |

## Access Boundaries

### Raw Data Access Boundary

| Component | Access Method | Authorization |
|-----------|-------------|---------------|
| Production apps | NFS/SMB | ONTAP file permissions |
| AI enrichment | S3 Access Point | IAM + AP policy + ONTAP identity |
| Analyst query | NOT direct file access | Metadata only via Athena/Snowflake |

### Metadata Access Boundary

| Component | Access Method | Authorization |
|-----------|-------------|---------------|
| Athena query | SQL via Glue catalog | Lake Formation grants |
| Snowflake query | VENDED_CREDENTIALS | Lake Formation + IAM |
| OpenSearch search | kNN API | IAM + VPC endpoint |
| Admin operations | PyIceberg/CLI | IAM + Lake Formation admin |

## AI Processing Data Flow

```
File on FSx for ONTAP
  → Read via S3 Access Point (file content in memory)
  → Sent to Bedrock API (TLS, not stored by provider)
  → Classification + embedding returned
  → Written to S3 Tables (metadata only)
  → Optionally indexed in OpenSearch
  → Original file NOT copied, NOT moved
```

Per [AWS Bedrock data protection](https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html):
- Model providers have no access to customer prompts or completions
- Inputs/outputs are not used for model training
- Data processed in the same region as the API endpoint

## PII Detection Scope and Limitations

| Language | Engine | Coverage | Known Gaps |
|----------|--------|----------|-----------|
| English | Amazon Comprehend | NAME, EMAIL, PHONE, ADDRESS, SSN, CREDIT_CARD | Context-dependent PII may be missed |
| Japanese | Bedrock Claude | 氏名, メール, 電話, 住所, マイナンバー | New PII types require prompt update |
| Other languages | Not covered | — | Requires additional engine integration |

**Important**: PII detection is assistive, not exhaustive. False negatives are possible. Human review is required for regulatory compliance.

## Audit and Evidence

| Audit Type | Source | Retention | Analysis |
|-----------|--------|-----------|----------|
| Metadata query audit | CloudTrail | 90 days (default) / Trail for longer | CloudTrail Lake or Athena |
| File access audit | ONTAP audit logs | Configurable | SVM audit policy |
| AI invocation audit | CloudTrail (Bedrock) | 90 days (default) | CloudTrail Lake |
| Governance changes | CloudTrail (Lake Formation) | 90 days (default) | CloudTrail Lake |

## Deletion and Retention

| Data Type | Retention Owner | Deletion Mechanism | Evidence |
|-----------|----------------|-------------------|----------|
| Raw files | Storage admin | FSx file deletion | ONTAP audit log |
| Metadata records | Catalog admin | Iceberg append (is_deleted=true) | Athena query |
| Iceberg snapshots | S3 Tables service | Auto-expiration (configurable) | S3 Tables settings |
| OpenSearch index | Platform admin | Index deletion | API call log |
| Snowflake sync | Snowflake admin | Table DROP / Time Travel expiry | Snowflake query history |

> **Warning**: Iceberg time travel may expose deleted metadata until snapshots expire. Align snapshot expiration with your deletion SLA.

## Legal and Compliance Sign-Off

| Item | Owner | Status |
|------|-------|--------|
| Data processing agreement | Legal | Required before production |
| AI usage approval | Compliance | Required for Bedrock usage |
| PII handling approval | DPO / Privacy | Required for PII detection |
| Audit retention policy | Security + Legal | Define retention periods |
| Incident response plan | Security | Define breach notification SLA |
| Third-party access review | Security | Snowflake/Databricks data flow review |

## Production Approval Gates

Before production deployment in regulated environments, complete the following gates in order:

1. **Data owner approval** — Confirm which data is in scope, classification levels, and acceptable AI processing
2. **Security architecture review** — IAM, network, encryption, access boundaries validated
3. **Legal / compliance review** — Data processing agreement, AI usage terms, cross-border assessment
4. **AI evaluation sign-off** — Classification accuracy, PII detection false negative rate, human review acceptance rate meet defined thresholds
5. **Operations readiness review** — Runbooks, alerting, DR procedure, cost model validated
6. **Deletion / retention SLA approval** — Snapshot expiration, metadata retention, audit evidence retention aligned with policy

## Evidence Mapping

For audit and compliance reporting, map evidence to the following categories:

| Evidence Category | Source | Location |
|------------------|--------|----------|
| Access control | CloudTrail + Lake Formation logs | CloudTrail Lake / S3 Trail bucket |
| AI evaluation | Labeled validation set results | `verification-evidence/ai-evaluation/` |
| PII redaction | Before/after redaction samples | `verification-evidence/pii-redaction/` |
| Deletion | Snapshot expiration logs + raw file deletion audit | ONTAP audit logs + S3 Tables settings |
| Cross-platform access | Athena / Snowflake / EMR screenshots + query logs | `snowflake/screenshots/`, CloudTrail |
| Governance changes | Lake Formation grant/revoke logs | CloudTrail |
| Performance baseline | Demo execution logs, latency measurements | `verification-evidence/2026-05-31/` |

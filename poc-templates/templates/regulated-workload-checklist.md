🌐 **English** | [日本語](ja/regulated-workload-checklist.md)

# Regulated Workload Checklist

## Purpose

Complete this checklist BEFORE starting a PoC with regulated data (HIPAA, PCI DSS, SOX, GDPR, FINRA).

---

## Pre-PoC Approval

| # | Item | Owner | Status | Date |
|---|------|-------|:---:|------|
| 1 | Data classification confirmed (Public/Internal/Confidential/Regulated) | Data owner | ☐ | |
| 2 | PoC uses synthetic data only (no real PHI/PII in dev/test) | Data owner | ☐ | |
| 3 | Security owner approves S3 AP access path | CISO/Security | ☐ | |
| 4 | Data owner approves analytics access scope | Data owner | ☐ | |
| 5 | Compliance officer confirms no regulatory conflict | Legal/Compliance | ☐ | |
| 6 | Network origin decision documented (VPC vs Internet) | Security | ☐ | |
| 7 | Approval record stored with expiration date | All | ☐ | |

---

## Access Control

| # | Item | Configuration | Status |
|---|------|--------------|:---:|
| 8 | S3 AP file system user is read-only (not root) | Username: _______ | ☐ |
| 9 | IAM policy scoped to specific AP ARN (no wildcards) | Role: _______ | ☐ |
| 10 | S3 AP resource policy restricts to specific principals | Principals: _______ | ☐ |
| 11 | VPC-origin AP used for regulated data (if not using Athena) | AP name: _______ | ☐ |
| 12 | Lake Formation permissions configured (table/column/row) | Database: _______ | ☐ |
| 13 | Snowflake governance applied (if using Snowflake) | Tags/Policies: _______ | ☐ |

---

## Audit & Logging

| # | Item | Configuration | Status |
|---|------|--------------|:---:|
| 14 | CloudTrail S3 data events enabled for AP | Trail: _______ | ☐ |
| 15 | Log retention configured (≥6 years HIPAA, ≥7 years SOX) | Retention: ___years | ☐ |
| 16 | Platform audit logs enabled (Athena/Snowflake/Databricks) | Platform: _______ | ☐ |
| 17 | Alert configured for unauthorized access attempts | Alert: _______ | ☐ |

---

## Encryption

| # | Item | Status | Notes |
|---|------|:---:|-------|
| 18 | FSx encryption at rest (SSE-FSX, automatic) | ☐ | Cannot be disabled |
| 19 | S3 AP access via HTTPS (TLS 1.2+, automatic) | ☐ | Enforced by AWS |
| 20 | Query result encryption configured | ☐ | Athena workgroup / Snowflake / Redshift |
| 21 | KMS key ownership documented | ☐ | AWS-managed vs customer-managed |

---

## Data Residency

| # | Item | Value | Status |
|---|------|-------|:---:|
| 22 | FSx for ONTAP region | _______ | ☐ |
| 23 | S3 AP in same region as FSx | Yes / No | ☐ |
| 24 | Query results stay in same region | Yes / No | ☐ |
| 25 | Cross-region inference disabled (if Snowflake Cortex) | Yes / No / N/A | ☐ |
| 26 | No data leaves region without approval | Confirmed | ☐ |

---

## AI/RAG Specific (if applicable)

| # | Item | Status | Notes |
|---|------|:---:|-------|
| 27 | Source documents de-identified before AI processing | ☐ | |
| 28 | Human review required for AI-generated responses | ☐ | Reviewer: _______ |
| 29 | Bedrock guardrails configured (PII detection, topic filtering) | ☐ | |
| 30 | Cortex AI Cross-Region Inference setting documented | ☐ | Setting: _______ |
| 31 | AI output not used for clinical decisions without physician review | ☐ | |

---

## Industry-Specific

### Healthcare (HIPAA)
- [ ] BAA in place with AWS
- [ ] No real PHI in PoC environment
- [ ] De-identification pipeline validated (if using real data post-PoC)
- [ ] Minimum necessary standard applied (access only what's needed)

### Financial Services (PCI DSS / SOX)
- [ ] Segregation of duties (admin ≠ analyst)
- [ ] Change management process documented
- [ ] Audit trail retention ≥7 years
- [ ] DR/BCP plan includes FSx for ONTAP S3 AP path

### Public Sector
- [ ] Data sovereignty confirmed (single region)
- [ ] FedRAMP/ISO certification requirements met by AWS services
- [ ] No data export without classification review

---

## Sign-Off

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Data Owner | | | |
| Security Owner (CISO) | | | |
| Compliance Officer | | | |
| Platform Owner | | | |
| PoC Lead | | | |

**Approval expiration date**: _______________
**Next review date**: _______________
**Evidence location**: _______________

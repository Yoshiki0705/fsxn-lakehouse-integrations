# Governance Deep Dive: Lake Formation + CloudTrail + PII

🌐 [日本語](governance-deep-dive-ja.md) | English

> Cross-industry governance demo showing Lake Formation row/column filtering, CloudTrail audit trail, and PII masking applied to the AI Metadata Catalog.

---

## Purpose

This guide demonstrates governance controls that apply across all 23 industry scenarios. Regardless of industry, the same `sensitivity_level` field and Lake Formation policies provide consistent data access control, audit evidence, and PII protection.

**Key concept**: The metadata catalog uses a common `sensitivity_level` field (values: `public`, `internal`, `confidential`, `restricted`) across all industries. This single field enables unified governance policies regardless of the underlying industry data.

---

## Prerequisites

- AI Metadata Catalog deployed with sample data (any industry)
- Lake Formation configured with `s3_tables.metadata_catalog` database
- IAM roles: `CatalogAdmin`, `CatalogAnalyst`, `CatalogRestricted`
- CloudTrail enabled with data events for S3 Tables

---

## Demo Steps

### Step 1: Show Full Access (Admin View)

**Duration**: 2 minutes

Query as the admin role with full column visibility:

```sql
-- As CatalogAdmin: all columns visible
SELECT file_path, ai_classification, confidence_score,
       customer_id, pii_detected, pii_types,
       sensitivity_level, retention_years
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'financial'
LIMIT 10;
```

**Expected**: All columns returned, including PII-containing fields (`customer_id`, `pii_types`).

**Talking points**:
- "Admin sees everything — this is the baseline for comparison"
- "Notice the `sensitivity_level` field — this drives all access decisions"

---

### Step 2: Create Restricted Role with Column Filtering

**Duration**: 3 minutes

In Lake Formation, grant the `CatalogAnalyst` role access to only non-sensitive columns:

```sql
-- Lake Formation column-level grant (via Console or CLI)
-- Grant: CatalogAnalyst
-- Database: s3_tables.metadata_catalog
-- Table: file_metadata
-- Columns INCLUDED:
--   file_path, ai_classification, confidence_score,
--   industry, department, file_size_bytes, last_modified,
--   sensitivity_level
-- Columns EXCLUDED:
--   customer_id, pii_types, pii_detected, risk_level,
--   retention_years
```

**AWS CLI equivalent** (Lake Formation grant):

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipal":{"DataLakePrincipalIdentifier":"arn:aws:iam::<ACCOUNT_ID>:role/CatalogAnalyst"}}' \
  --resource '{"TableWithColumns":{"DatabaseName":"metadata_catalog","Name":"file_metadata","ColumnNames":["file_path","ai_classification","confidence_score","industry","department","file_size_bytes","last_modified","sensitivity_level"],"CatalogId":"<ACCOUNT_ID>"}}' \
  --permissions '["SELECT"]' \
  --region ap-northeast-1
```

**Important limitation**: Column-level grants on S3 Tables via federated catalog (Glue Data Catalog integration) are not yet working as of testing. The workaround below uses Athena Views.

---

### Step 3: Query as Restricted Role — Blocked Columns Invisible

**Duration**: 3 minutes

```sql
-- As CatalogAnalyst: only granted columns visible
SELECT file_path, ai_classification, confidence_score,
       sensitivity_level, department
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'financial'
LIMIT 10;
```

**Expected**: Query succeeds with only the granted columns.

```sql
-- Attempt to access blocked column
SELECT customer_id
FROM s3_tables.metadata_catalog.file_metadata
LIMIT 1;
```

**Expected**: Access denied — column not visible to this role.

**Talking points**:
- "Analysts can classify and search without seeing PII"
- "Same metadata catalog, different views based on role"
- "No data duplication — zero-copy storage, access-level filtering"

---

### Step 4: PII-Redacted View (Sensitivity Level Filtering)

**Duration**: 5 minutes

Create a row-filtered view that only shows records where `sensitivity_level` allows access:

```sql
-- Create a view with row-level filtering based on sensitivity
CREATE OR REPLACE VIEW metadata_catalog.public_metadata AS
SELECT file_path, ai_classification, confidence_score,
       industry, department, file_size_bytes, last_modified
FROM s3_tables.metadata_catalog.file_metadata
WHERE sensitivity_level IN ('public', 'internal');
```

Apply Lake Formation row filter (for direct table access):

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipal":{"DataLakePrincipalIdentifier":"arn:aws:iam::<ACCOUNT_ID>:role/CatalogRestricted"}}' \
  --resource '{"Table":{"DatabaseName":"metadata_catalog","Name":"file_metadata","CatalogId":"<ACCOUNT_ID>"}}' \
  --permissions '["SELECT"]' \
  --permissions-with-grant-option '[]' \
  --region ap-northeast-1
```

Row filter expression (via Lake Formation Console → Data filters):

```json
{
  "RowFilter": {
    "FilterExpression": "sensitivity_level IN ('public', 'internal')"
  }
}
```

```sql
-- As CatalogRestricted: only non-sensitive rows visible
SELECT file_path, ai_classification, sensitivity_level
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'healthcare';
-- Only returns rows where sensitivity_level = 'public' or 'internal'
-- PHI-flagged rows (sensitivity_level = 'restricted') are invisible
```

**Talking points**:
- "Healthcare PHI records simply don't appear for unauthorized roles"
- "Financial PII documents are filtered at the row level before query results return"
- "Works identically across all 23 industries — same field, same policy"

---

### Step 5: CloudTrail Audit Evidence

**Duration**: 5 minutes

Query CloudTrail logs to show access attempts and denials:

```sql
-- CloudTrail query via Athena (CloudTrail Lake or S3-based logs)
SELECT eventTime, userIdentity.arn AS user_arn,
       eventName, requestParameters,
       errorCode, errorMessage
FROM cloudtrail_logs
WHERE eventSource = 'lakeformation.amazonaws.com'
  AND eventTime > current_timestamp - interval '1' hour
ORDER BY eventTime DESC
LIMIT 20;
```

**Example audit evidence**:

| eventTime | user_arn | eventName | errorCode |
|-----------|----------|-----------|-----------|
| 2026-06-01T10:15:32Z | .../CatalogAnalyst | GetTableData | - |
| 2026-06-01T10:15:45Z | .../CatalogAnalyst | GetTableData | AccessDeniedException |
| 2026-06-01T10:14:12Z | .../CatalogAdmin | GetTableData | - |

```sql
-- S3 data access events (if S3 data events enabled)
SELECT eventTime, userIdentity.arn AS user_arn,
       eventName, 
       requestParameters.bucketName,
       requestParameters.key
FROM cloudtrail_logs
WHERE eventSource = 's3.amazonaws.com'
  AND requestParameters.bucketName LIKE '%metadata-catalog%'
  AND eventTime > current_timestamp - interval '1' hour
ORDER BY eventTime DESC;
```

**Talking points**:
- "Every access attempt is logged — successful or denied"
- "Auditors can prove who accessed what, when, and whether they were authorized"
- "This meets regulatory requirements across financial, healthcare, and public sector"
- "CloudTrail logs are immutable — cannot be tampered with by data users"

---

## Sensitivity Level Reference

The `sensitivity_level` field is set during AI classification and applies consistently:

| Level | Description | Typical Content | Access |
|-------|-------------|-----------------|--------|
| `public` | Non-sensitive metadata | File type, size, creation date | All roles |
| `internal` | Business-internal | Department info, project names | Analyst+ |
| `confidential` | Business-sensitive | Financial figures, contracts | Manager+ |
| `restricted` | Regulated/PII | Customer PII, PHI, classified | Admin only |

**Industry mapping examples**:

| Industry | `restricted` content |
|----------|---------------------|
| Financial | Customer IDs, account numbers, KYC documents |
| Healthcare | PHI (patient records, DICOM with patient data) |
| Public Sector | Classified documents, PII in FOIA requests |
| Legal | Privileged communications, settlement details |
| Retail | Customer payment data, loyalty program PII |

---

## Working vs. Not-Yet-Working

### Confirmed Working

| Feature | Status | Notes |
|---------|--------|-------|
| Table-level Lake Formation grants | ✅ Working | Full table grant/revoke on S3 Tables |
| Athena Views for column filtering | ✅ Working | CREATE VIEW with column subset |
| Athena Views for row filtering | ✅ Working | WHERE clause in view definition |
| CloudTrail audit logging | ✅ Working | All access events captured |
| IAM role-based access | ✅ Working | AssumeRole for different access levels |
| Lake Formation tags | ✅ Working | Tag-based access control on databases |

### Known Limitations (Observed)

| Feature | Status | Workaround |
|---------|--------|-----------|
| Lake Formation column-level filtering on S3 Tables (federated catalog) | ⚠️ Not yet working | Use Athena Views with column subsets |
| Lake Formation row-level filtering (data filters) on S3 Tables | ⚠️ Not yet working | Use Athena Views with WHERE clauses |
| Cross-account Lake Formation sharing for S3 Tables | ⚠️ Not tested | Use S3 cross-account replication |
| Fine-grained audit of column access in CloudTrail | ⚠️ Limited | Table-level events available; column-level detail not granular |

---

## SQL Reference: Common Governance Queries

```sql
-- Compliance dashboard: sensitivity distribution
SELECT industry, sensitivity_level, COUNT(*) as file_count
FROM s3_tables.metadata_catalog.file_metadata
GROUP BY industry, sensitivity_level
ORDER BY industry, sensitivity_level;

-- PII inventory across all industries
SELECT industry, ai_classification, COUNT(*) as pii_files
FROM s3_tables.metadata_catalog.file_metadata
WHERE pii_detected = true
GROUP BY industry, ai_classification
ORDER BY pii_files DESC;

-- Retention compliance: files past retention date
SELECT file_path, industry, ai_classification, 
       retention_expiry_date, sensitivity_level
FROM s3_tables.metadata_catalog.file_metadata
WHERE retention_expiry_date < current_date
  AND sensitivity_level IN ('confidential', 'restricted')
ORDER BY retention_expiry_date ASC;

-- Access pattern audit: who queries what
SELECT DATE(eventTime) as access_date,
       userIdentity.arn as user_role,
       COUNT(*) as query_count
FROM cloudtrail_logs
WHERE eventSource = 'athena.amazonaws.com'
  AND eventTime > current_timestamp - interval '30' day
GROUP BY DATE(eventTime), userIdentity.arn
ORDER BY access_date DESC;
```

---

## Integration with Industry Scenarios

Each industry scenario inherits these governance controls:

1. **AI classification** sets `sensitivity_level` automatically during processing
2. **Lake Formation** (or Athena Views) enforces access based on that level
3. **CloudTrail** logs all access for audit evidence
4. **No code changes needed** — governance is infrastructure-level

To apply governance to a specific industry demo, simply ensure the IAM roles are configured and run the demo as the appropriate role.

---

*Related: [AI Prompt Customization Guide](ai-prompt-customization-guide.md) — how classification sets sensitivity_level*
*Related: [Snowflake Activation Pattern](snowflake-activation-pattern.md) — governance considerations for cross-platform access*
*Pair document: [governance-deep-dive-ja.md](governance-deep-dive-ja.md)*

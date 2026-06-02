# Financial Services Demo Scenario: KYC Document AI Classification & Compliance Search

> Demo scenario for improving document governance and search in financial institutions.

---

## Business Context

### Challenge

Financial institutions face:

- **Regulatory document sprawl**: KYC documents, contracts, risk reports, and regulatory filings spread across file shares with no systematic classification
- **Compliance audit burden**: Finding specific documents for regulatory audits takes days of manual searching
- **PII exposure risk**: Sensitive customer data exists in unclassified files with no visibility into what contains PII
- **Retention policy gaps**: Documents past retention periods remain because no one knows what they are

### Solution Value

- Files classified automatically upon creation/modification via AI
- "Find all KYC documents expiring in 90 days" answered in seconds via SQL
- PII-containing documents flagged immediately for compliance review
- Retention policy enforcement becomes data-driven rather than manual

---

## Demo Flow

### Step 1: Place Sample Financial Documents on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry financial --target /vol/compliance/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `kyc-customer-C789012-2024.pdf` | KYC Document | Customer verification, risk assessment |
| `loan-agreement-FIN-2026-0042.pdf` | Contract | ¥50M loan agreement |
| `portfolio-var-report-Q1-2026.xlsx` | Risk Report | Quarterly VaR and stress test results |
| `basel3-filing-2026Q1.pdf` | Regulatory Filing | Basel III quarterly submission |
| `client-review-corpABC.msg` | Communication | Account review correspondence |

**Talking points**:
- "Compliance officers don't need to change how they save files. The pipeline triggers automatically."
- "Both NFS and SMB access trigger FPolicy — works with existing Windows file shares."

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: kyc-customer-C789012-2024.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: KYC/Customer Verification
   - Customer ID: C-789012
   - Risk level: Low
   - Verification status: Complete
   - PII detected: Yes (name, address, national ID)
   - Retention: 10 years from last transaction
✅ Classified in 41.8s | Cost: $0.07
```

**Talking points**:
- "FPolicy is filesystem-level event detection — no polling, no crawling"
- "Bedrock Claude reads the document content and extracts structured metadata"
- "PII detection runs automatically — no separate tool needed"
- "Classification confidence: 0.94 average on PoC test dataset. Production accuracy varies by document quality and language mix."

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
-- Check classification results via Athena
SELECT file_path, ai_classification, confidence_score,
       customer_id, risk_level, pii_detected, retention_years
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'financial'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | customer_id | risk_level | pii_detected |
|-----------|------------------|:---------:|:-----------:|:----------:|:------------:|
| /vol/compliance/kyc-customer-C789012-2024.pdf | KYC/Customer Verification | 0.94 | C-789012 | Low | Yes |
| /vol/compliance/loan-agreement-FIN-2026-0042.pdf | Contract/Loan | 0.96 | - | - | Yes |
| /vol/compliance/portfolio-var-report-Q1-2026.xlsx | Risk Report | 0.92 | - | - | No |
| /vol/compliance/basel3-filing-2026Q1.pdf | Regulatory Filing | 0.95 | - | - | No |
| /vol/compliance/client-review-corpABC.msg | Client Communication | 0.91 | - | Normal | Yes |

**Note**: Confidence scores shown are PoC results on test dataset. Production accuracy varies by file type, language mix, and domain terminology.

**Talking points**:
- "All 5 documents correctly classified with high confidence"
- "PII flagged automatically on 3 of 5 documents"
- "This data is now queryable for compliance reporting"

---

### Step 4: Compliance Queries

**Duration**: 5 minutes

**Scenario**: "Find all KYC documents expiring within 90 days"

```sql
-- KYC documents approaching retention expiry
SELECT file_path, customer_id, risk_level, retention_expiry_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'KYC/Customer Verification'
  AND retention_expiry_date < current_date + interval '90' day
ORDER BY retention_expiry_date ASC;

-- Documents with PII that lack redaction
SELECT file_path, ai_classification, pii_types, pii_redacted
FROM s3_tables.metadata_catalog.file_metadata
WHERE pii_detected = true AND pii_redacted = false
ORDER BY scan_timestamp DESC;

-- High-risk client document inventory
SELECT file_path, ai_classification, customer_id, last_modified
FROM s3_tables.metadata_catalog.file_metadata
WHERE risk_level = 'High'
ORDER BY last_modified DESC;
```

**Talking points**:
- "Previously this required days of manual searching through folder structures"
- "Now it's SQL — automatable, auditable, repeatable"
- "Note: first Athena query after idle period takes 3–5 seconds (cold start). Subsequent queries are faster."

---

### Step 5: Semantic Search for Related Documents

**Duration**: 5 minutes

**Scenario**: "Find all documents related to customer C-789012"

Using OpenSearch:
1. **Keyword search**: `"C-789012"` → all documents mentioning this customer
2. **Semantic search**: "loan agreement collateral documents" → vector similarity finds related files
3. **Combined**: Filter by customer + semantic relevance

**Talking points**:
- "Vector search finds related documents even when they don't share exact keywords"
- "OpenSearch Serverless note: if idle for extended periods, first search may take 10–30 seconds for OCU warm-up"
- "Once warm, sub-second response for both keyword and semantic search"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 90%+ (5 categories) | PoC result; production varies |
| Processing time | 42 seconds/file | Single file; batch depends on concurrency |
| Cost per file | $0.07 | 100KB–1MB documents |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Audit preparation time | 5 days/audit → 2 hours/audit × 4 audits/year | **80 hours saved** |
| Document search (compliance team) | 10 min/day × 20 people × 50% adoption | **~370 hours/year** |
| PII exposure reduction | Risk mitigation (not directly quantified) | **Risk reduction** |
| Retention policy automation | Manual review: 2 weeks/year → automated | **80 hours saved** |

**Conservative annual productivity value**: ~530 hours × ¥5,000/hr = **¥2,650,000** (~$17,700)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~1,194%

**Assumptions**: 50% user adoption, 10 min/day actual search reduction, no additional value from compliance risk reduction.

---

## Limitations Relevant to Financial Services

| Limitation | Impact for Financial |
|-----------|---------------------|
| S3 AP (pipeline reads only) | Cannot auto-archive expired documents via analytics pipeline |
| No S3 Event Notifications | Cannot trigger downstream compliance workflows via S3 events |
| Bedrock accuracy varies | Legal/regulatory document classification may need prompt tuning for specialized terms |
| FPolicy latency (~1–5ms) | Minimal impact for document management; test if trading systems share the volume |
| Lambda ephemeral access | File content passes through Lambda memory — acceptable for metadata extraction but review with InfoSec |
| S3 Tables maturity | Cross-platform Iceberg access (Snowflake, Databricks) still evolving |

---

## Customization Points

1. **Classification categories**: Add institution-specific document types (internal memos, board minutes, etc.)
2. **PII types**: Configure detection for jurisdiction-specific identifiers (My Number, SSN, etc.)
3. **Retention rules**: Map document types to retention policies per regulatory requirements
4. **Access control**: Lake Formation policies aligned with department-level data governance

---

## Iceberg Time Travel: Historical Comparison

One unique advantage of the Iceberg table format is time travel — querying metadata as it existed at any past point in time.

```sql
-- View snapshot history
SELECT * FROM s3_tables.metadata_catalog.file_metadata$snapshots
ORDER BY committed_at DESC LIMIT 10;

-- Query metadata as of 24 hours ago
SELECT ai_classification, COUNT(*) as file_count
FROM s3_tables.metadata_catalog.file_metadata
FOR TIMESTAMP AS OF (current_timestamp - interval '24' hour)
GROUP BY ai_classification;

-- Compare current vs. previous classification counts
WITH current_state AS (
  SELECT ai_classification, COUNT(*) as current_count
  FROM s3_tables.metadata_catalog.file_metadata
  GROUP BY ai_classification
),
previous_state AS (
  SELECT ai_classification, COUNT(*) as previous_count
  FROM s3_tables.metadata_catalog.file_metadata
  FOR TIMESTAMP AS OF (current_timestamp - interval '7' day)
  GROUP BY ai_classification
)
SELECT COALESCE(c.ai_classification, p.ai_classification) as category,
       COALESCE(c.current_count, 0) as now,
       COALESCE(p.previous_count, 0) as week_ago,
       COALESCE(c.current_count, 0) - COALESCE(p.previous_count, 0) as delta
FROM current_state c
FULL OUTER JOIN previous_state p ON c.ai_classification = p.ai_classification
ORDER BY delta DESC;
```

**Use cases for time travel in this industry**:
- Track how file classification distribution changes over time
- Audit what metadata looked like when a compliance decision was made
- Recover from accidental bulk reclassification or deletion
- Compare enrichment pipeline output across different AI model versions


---

*Related config: [`financial.yaml`](../sample-data/industry-configs/financial.yaml)*
*Pair document: [industry-financial-ja.md](./industry-financial-ja.md)*

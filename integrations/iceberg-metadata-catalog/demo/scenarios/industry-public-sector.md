# Public Sector Demo Scenario: Government Document AI Classification & Information Governance

> Demo scenario for improving document management, FOIA compliance, and records retention in government agencies.

---

## Business Context

### Challenge

Government agencies face:

- **Massive document accumulation**: Policy documents, citizen correspondence, internal memos, and regulatory filings grow continuously without systematic classification
- **FOIA/Information disclosure requests**: Finding responsive documents across decades of file shares takes weeks of manual search
- **Records retention complexity**: Different document types have different retention schedules (1 year to permanent) — manual compliance is error-prone
- **Cross-agency information sharing**: Related documents across departments are invisible to each other

### Solution Value

- Government documents auto-classified by type and sensitivity level
- Information disclosure requests answered in hours instead of weeks
- Retention schedules automatically applied based on document classification
- Cross-department document discovery without compromising access controls

---

## Demo Flow

### Step 1: Place Sample Government Documents on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry public-sector --target /vol/government/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `policy-draft-digital-transformation-2026.docx` | Policy Document | Digital transformation strategy draft |
| `citizen-inquiry-INQ-2026-4521.pdf` | Citizen Correspondence | Public inquiry about services |
| `budget-report-FY2026-Q1.xlsx` | Budget Report | Quarterly budget execution report |
| `internal-memo-security-review-20260115.docx` | Internal Memo | Security protocol review |
| `procurement-contract-PROC-2026-0089.pdf` | Procurement | Vendor contract for IT services |

**Talking points**:
- "Staff save documents to shared drives as usual — no process change"
- "Classification happens automatically in the background"
- "Sensitivity levels are assigned by AI — human review confirms before disclosure"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: policy-draft-digital-transformation-2026.docx
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Policy Document/Draft
   - Department: Digital Agency
   - Sensitivity: Internal (draft - not for public disclosure)
   - Retention: 10 years (policy records)
   - PII detected: No
   - FOIA relevant: Yes (after finalization)
✅ Classified in 40.5s | Cost: $0.07
```

**Talking points**:
- "AI distinguishes between drafts and final documents — important for disclosure decisions"
- "Sensitivity classification is assistive — final disclosure decisions remain with information officers"
- "Confidence: 0.94 average on PoC test dataset. Production accuracy varies by document type and language."

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       department, sensitivity_level, retention_years, foia_relevant
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'public-sector'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | sensitivity | retention | foia_relevant |
|-----------|------------------|:---------:|:----------:|:---------:|:-------------:|
| .../policy-draft-digital-transformation-2026.docx | Policy/Draft | 0.94 | Internal | 10 | Yes (after final) |
| .../citizen-inquiry-INQ-2026-4521.pdf | Citizen Correspondence | 0.96 | Restricted (PII) | 5 | Yes |
| .../budget-report-FY2026-Q1.xlsx | Budget Report | 0.95 | Public | 10 | Yes |
| .../internal-memo-security-review-20260115.docx | Internal Memo | 0.93 | Confidential | 3 | No |
| .../procurement-contract-PROC-2026-0089.pdf | Procurement Contract | 0.94 | Public (redacted) | 10 | Yes |

**Note**: Sensitivity classification is AI-assisted. Human information officers make final disclosure decisions.

---

### Step 4: Information Disclosure Queries

**Duration**: 5 minutes

**Scenario**: "Respond to FOIA request: all documents related to digital transformation policy"

```sql
-- Find all FOIA-relevant documents matching a topic
SELECT file_path, ai_classification, department, sensitivity_level,
       scan_timestamp, confidence_score
FROM s3_tables.metadata_catalog.file_metadata
WHERE foia_relevant = true
  AND (content_summary LIKE '%digital transformation%'
       OR content_summary LIKE '%デジタル・トランスフォーメーション%')
ORDER BY scan_timestamp DESC;

-- Retention compliance: documents past retention with no disposition
SELECT file_path, ai_classification, creation_date, retention_years,
       date_add('year', retention_years, creation_date) as disposal_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE date_add('year', retention_years, creation_date) < current_date
  AND disposition_status IS NULL;

-- Department document inventory by sensitivity
SELECT department, sensitivity_level, count(*) as doc_count
FROM s3_tables.metadata_catalog.file_metadata
GROUP BY department, sensitivity_level
ORDER BY department, sensitivity_level;
```

**Talking points**:
- "Information disclosure requests that took weeks can now be scoped in hours"
- "Note: AI classification assists the process — information officers still make final decisions"
- "First Athena query after idle: 3–5 seconds cold start"

---

### Step 5: Cross-Department Discovery

**Duration**: 5 minutes

**Scenario**: "Find all documents across agencies related to cybersecurity policy"

OpenSearch semantic search:
- Keyword: `"cybersecurity" OR "サイバーセキュリティ"` → exact matches
- Semantic: "information security policy government guidelines" → conceptually related documents

**Talking points**:
- "Cross-department visibility without changing access controls"
- "Lake Formation ensures each department only sees metadata they're authorized to access"
- "OpenSearch warm-up: 10–30 seconds after extended idle"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 90%+ (5 categories) | PoC result; legal/regulatory documents may need prompt tuning |
| Processing time | 42 seconds/file | Standard documents |
| Cost per file | $0.07 | 100KB–1MB documents |
| FOIA response scoping | Hours (from weeks) | Assumes good metadata coverage of relevant files |
| Athena query response | 2–3 seconds | After cold start (+3–5s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| FOIA response time | 5 days → 4 hours × 50 requests/year | **2,350 hours saved** |
| Records management | Manual review: 1 month/year → 1 week | **120 hours saved** |
| Cross-agency search | 2 hours/search → 5 min × 200 searches/year | **390 hours saved** |
| Audit preparation | 1 week → 1 day × 2 audits/year | **64 hours saved** |

**Conservative annual productivity value**: ~2,924 hours × ¥5,000/hr = **¥14,620,000** (~$97,500)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~7,027%

**Assumptions**: 50% adoption, conservative time estimates, FOIA volume of 50 requests/year.

---

## Limitations Relevant to Public Sector

| Limitation | Impact for Government |
|-----------|----------------------|
| AI classification is assistive | Not authoritative for disclosure decisions — human review required |
| Lambda ephemeral processing | Classified/sensitive content passes through Lambda memory — evaluate against security requirements |
| Bedrock accuracy varies | Legal/regulatory terminology and bilingual documents may reduce accuracy |
| S3 AP (pipeline reads only) | Cannot auto-apply retention disposition (delete/archive) via analytics pipeline |
| No S3 Event Notifications | Cannot trigger downstream records management workflows via S3 events |
| Cross-agency access | Requires careful Lake Formation policy design for multi-department visibility |

---

## Customization Points

1. **Classification categories**: Map to agency-specific document taxonomy
2. **Sensitivity levels**: Align with government classification scheme (Public/Internal/Confidential/Secret)
3. **Retention schedules**: Map document types to statutory retention requirements
4. **FOIA workflow**: Configure metadata fields to support disclosure review process
5. **Access control**: Multi-department access via Lake Formation with role-based policies

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

*Related config: [`public-sector.yaml`](../sample-data/industry-configs/public-sector.yaml)*
*Pair document: [industry-public-sector-ja.md](./industry-public-sector-ja.md)*

# Life Sciences & Pharma Demo Scenario: Clinical Trial Document & Regulatory Submission Intelligence

🌐 [日本語](industry-life-sciences-ja.md) | English

> Automated classification and search of clinical trial documents, FDA/PMDA submissions, lab reports, and SOP documents across pharma file shares.

---

## Business Context

### Challenge

Pharmaceutical companies face:

- **Regulatory document complexity**: Thousands of clinical trial protocols, adverse event reports, and regulatory submissions across therapeutic areas with inconsistent organization
- **Submission readiness gaps**: Finding specific documents for FDA/PMDA submissions requires weeks of manual assembly
- **SOP version chaos**: Standard Operating Procedures exist in multiple versions with unclear approval status
- **Cross-study visibility**: Identifying related findings across clinical trials requires deep domain expertise and manual searching

### Solution Value

- Clinical documents classified automatically by study phase, therapeutic area, and document type (ICH/eCTD)
- "Find all Phase 3 adverse event reports for oncology studies in 2026" answered in seconds via SQL
- SOP versions tracked with approval status and effective dates
- Cross-study findings discoverable through semantic search for signal detection

---

## Demo Flow

### Step 1: Place Sample Life Sciences Documents on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry life-sciences --target /vol/clinical-ops/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `protocol-ONCO-2026-P3-042.pdf` | Clinical Protocol | Phase 3 oncology study protocol |
| `ae-report-ONCO042-SAE-0087.pdf` | Adverse Event Report | Serious adverse event, Grade 3 |
| `lab-report-ONCO042-biomarker-wk24.pdf` | Lab Report | Week 24 biomarker analysis |
| `sop-GCP-monitoring-v4.2.pdf` | SOP Document | GCP monitoring procedures, v4.2 |
| `ectd-module5-clinical-overview.pdf` | Regulatory Submission | eCTD Module 5 clinical overview |

**Talking points**:
- "Clinical operations teams continue using validated file systems — no revalidation required"
- "Both GxP and non-GxP file shares supported via FPolicy"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: protocol-ONCO-2026-P3-042.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Clinical Protocol
   - Study ID: ONCO-2026-042
   - Phase: 3
   - Therapeutic area: Oncology
   - Indication: Non-small cell lung cancer
   - ICH classification: E6 (GCP)
   - eCTD module: Module 5.3.5.1
   - Version: 2.0, Approved
✅ Classified in 45.2s | Cost: $0.07
```

**Talking points**:
- "AI identifies study phase, therapeutic area, ICH classification, and eCTD module"
- "Document versions and approval status extracted automatically"
- "Classification confidence: PoC accuracy; production varies by document formatting"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       study_id, phase, therapeutic_area, ectd_module
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'life-sciences'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | study_id | phase | therapeutic_area |
|-----------|------------------|:---------:|:--------:|:-----:|:---------------:|
| /vol/clinical-ops/protocol-ONCO-2026-P3-042.pdf | Clinical Protocol | 0.96 | ONCO-042 | 3 | Oncology |
| /vol/clinical-ops/ae-report-ONCO042-SAE-0087.pdf | Adverse Event/SAE | 0.94 | ONCO-042 | 3 | Oncology |
| /vol/clinical-ops/lab-report-ONCO042-biomarker-wk24.pdf | Lab Report/Biomarker | 0.93 | ONCO-042 | 3 | Oncology |
| /vol/clinical-ops/sop-GCP-monitoring-v4.2.pdf | SOP/GCP | 0.97 | - | - | - |
| /vol/clinical-ops/ectd-module5-clinical-overview.pdf | Regulatory/eCTD M5 | 0.95 | ONCO-042 | 3 | Oncology |

**Talking points**:
- "Documents classified by ICH/eCTD taxonomy for regulatory alignment"
- "Study linkage maintained across protocols, reports, and submissions"
- "SOP versions tracked with approval status"

---

### Step 4: Life Sciences Queries

**Duration**: 5 minutes

```sql
-- Phase 3 adverse event reports by therapeutic area
SELECT file_path, study_id, ae_grade, ae_type, report_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Adverse Event/SAE'
  AND phase = 3
  AND therapeutic_area = 'Oncology'
ORDER BY report_date DESC;

-- eCTD submission readiness check
SELECT ectd_module, COUNT(*) as documents,
       COUNT(CASE WHEN status = 'Approved' THEN 1 END) as approved
FROM s3_tables.metadata_catalog.file_metadata
WHERE study_id = 'ONCO-042'
  AND ai_classification LIKE 'Regulatory%'
GROUP BY ectd_module
ORDER BY ectd_module;

-- SOP documents approaching review date
SELECT file_path, sop_id, current_version, effective_date, next_review_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'SOP%'
  AND next_review_date < current_date + interval '90' day
ORDER BY next_review_date ASC;
```

**Talking points**:
- "Regulatory affairs team tracks submission readiness in real time"
- "Safety team monitors adverse events across the portfolio"
- "Quality team ensures SOPs are reviewed before expiry"

---

### Step 5: Semantic Search for Cross-Study Signals

**Duration**: 5 minutes

**Scenario**: "Find similar adverse event patterns across studies"

Using OpenSearch:
1. **Keyword search**: `"hepatotoxicity" AND "Grade 3"` → exact AE matches
2. **Semantic search**: "liver enzyme elevation in combination therapy patients" → finds related signals
3. **Combined**: Filter by therapeutic area + phase + semantic similarity

**Talking points**:
- "Cross-study signal detection accelerated from weeks to minutes"
- "Semantic search finds related safety signals even with different MedDRA coding"
- "OpenSearch Serverless note: first search after extended idle may take 10–30 seconds for OCU warm-up"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 93%+ (5 categories) | PoC result; production varies |
| Processing time | 45 seconds/file | Single file; batch depends on concurrency |
| Cost per file | $0.07 | Clinical documents tend to be longer |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Submission document assembly | 3 weeks → 3 days per submission × 4/year | **480 hours saved** |
| Adverse event search | 1 hour/search × 200 searches/year → 5 min | **183 hours saved** |
| SOP management | 2 hours/week manual tracking → automated | **96 hours saved** |
| Cross-study signal detection | 2 weeks/review → 2 days × 4 reviews/year | **320 hours saved** |

**Conservative annual productivity value**: ~1,079 hours × ¥8,000/hr = **¥8,632,000** (~$57,500)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~4,105%

**Assumptions**: 50% adoption, mid-size pharma, no additional value from faster regulatory approval or earlier signal detection.

---

## Limitations Relevant to Life Sciences

| Limitation | Impact for Life Sciences |
|-----------|-------------------------|
| S3 AP (pipeline reads only) | Cannot trigger document workflow transitions via pipeline |
| No S3 Event Notifications | Cannot trigger submission compilation via S3 events |
| Bedrock accuracy varies | Specialized medical/scientific terminology may need domain-specific prompt tuning |
| GxP validation | AI classification is assistive; does not replace validated document management systems |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| 21 CFR Part 11 | Metadata catalog is supplementary; electronic signatures and audit trails managed by validated DMS |
| Data integrity | AI metadata is informational; source of truth remains the validated file system |

---

## Customization Points

1. **eCTD taxonomy**: Map classifications to company-specific eCTD structure and naming
2. **Therapeutic areas**: Configure domain-specific vocabularies (MedDRA, WHO Drug)
3. **Study phases**: Add pre-clinical and post-market surveillance document types
4. **Regulatory bodies**: Configure for FDA, EMA, PMDA, or multi-regional submissions

---

## Iceberg Time Travel: Historical Comparison

A notable capability of the Iceberg table format is time travel — querying metadata as it existed at any past point in time.

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

*Related: [use-cases/life-sciences/](../../use-cases/life-sciences/)*
*Pair document: [industry-life-sciences-ja.md](./industry-life-sciences-ja.md)*

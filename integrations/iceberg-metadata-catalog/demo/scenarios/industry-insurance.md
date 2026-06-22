# Insurance Demo Scenario: Claims Document & Damage Assessment Intelligence

🌐 [日本語](industry-insurance-ja.md) | English

> Automated classification and search of claims documents, medical reports, damage photos, and policy documents across insurance file shares.

---

## Business Context

### Challenge

Insurance companies face:

- **Claims document overload**: Thousands of claims forms, medical reports, police reports, and damage assessments filed daily with inconsistent naming
- **Fraud detection gaps**: Related claims documents scattered across systems make pattern detection difficult
- **Policy document sprawl**: Active policies, endorsements, and amendments stored without version tracking
- **Adjuster productivity loss**: Finding relevant precedent cases and supporting documents requires manual search across multiple repositories

### Solution Value

- Claims documents classified automatically by claim type, severity, and required action
- "Find all auto claims with damage above ¥1M pending adjuster review" answered via SQL
- Damage photos analyzed for severity estimation and potential fraud indicators
- Similar past claims discoverable through semantic search for faster adjudication

---

## Demo Flow

### Step 1: Place Sample Insurance Documents on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry insurance --target /vol/insurance-ops/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `claim-AUTO-2026-08421.pdf` | Claims Form | Auto collision claim, ¥2.3M estimate |
| `medical-report-CLM08421-injury.pdf` | Medical Report | Claimant injury assessment |
| `damage-photo-CLM08421-front.jpg` | Damage Photo | Vehicle front damage, high severity |
| `policy-AUT-P2026-44210.pdf` | Policy Document | Comprehensive auto policy |
| `adjuster-report-CLM08421-final.pdf` | Adjuster Report | Final assessment and recommendation |

**Talking points**:
- "Claims adjusters keep their existing file-save workflow — no training required"
- "Photos from field adjusters uploaded via mobile trigger the same pipeline"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: claim-AUTO-2026-08421.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Claims Form/Auto
   - Claim ID: CLM-08421
   - Claim type: Auto Collision
   - Estimated damage: ¥2,300,000
   - Severity: High
   - Status: Pending Review
   - PII detected: Yes (name, address, license number)
   - Fraud indicators: None detected
✅ Classified in 43.5s | Cost: $0.07
```

**Talking points**:
- "AI extracts claim type, severity, damage estimate, and fraud indicators automatically"
- "Damage photos analyzed for severity estimation matching claims documentation"
- "PII detection built-in for privacy compliance"
- "Classification confidence: PoC accuracy; production varies by document quality"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       claim_id, claim_type, severity, estimated_damage
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'insurance'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | claim_id | claim_type | severity |
|-----------|------------------|:---------:|:--------:|:----------:|:--------:|
| /vol/insurance-ops/claim-AUTO-2026-08421.pdf | Claims Form/Auto | 0.95 | CLM-08421 | Collision | High |
| /vol/insurance-ops/medical-report-CLM08421-injury.pdf | Medical Report | 0.93 | CLM-08421 | Injury | Medium |
| /vol/insurance-ops/damage-photo-CLM08421-front.jpg | Damage Photo/Vehicle | 0.91 | CLM-08421 | Collision | High |
| /vol/insurance-ops/policy-AUT-P2026-44210.pdf | Policy Document/Auto | 0.97 | - | - | - |
| /vol/insurance-ops/adjuster-report-CLM08421-final.pdf | Adjuster Report | 0.94 | CLM-08421 | Collision | High |

**Talking points**:
- "All claim-related documents linked by claim ID automatically"
- "Damage severity from photo analysis corroborates claims form estimate"
- "PII flagged for compliance with privacy regulations"

---

### Step 4: Insurance Operations Queries

**Duration**: 5 minutes

```sql
-- High-value claims pending adjuster review
SELECT file_path, claim_id, claim_type, estimated_damage, days_pending
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Claims Form/Auto'
  AND estimated_damage > 1000000
  AND status = 'Pending Review'
ORDER BY estimated_damage DESC;

-- Claims with fraud indicator flags
SELECT claim_id, file_path, fraud_indicator_type, confidence_score
FROM s3_tables.metadata_catalog.file_metadata
WHERE fraud_indicators = true
ORDER BY confidence_score DESC;

-- Claims document completeness check
SELECT claim_id,
       COUNT(CASE WHEN ai_classification LIKE 'Claims Form%' THEN 1 END) as forms,
       COUNT(CASE WHEN ai_classification LIKE 'Damage Photo%' THEN 1 END) as photos,
       COUNT(CASE WHEN ai_classification LIKE 'Medical Report%' THEN 1 END) as medical
FROM s3_tables.metadata_catalog.file_metadata
WHERE claim_type = 'Collision'
GROUP BY claim_id;
```

**Talking points**:
- "Claims managers prioritize high-value cases with complete documentation"
- "Fraud detection team gets automated flagging of suspicious patterns"
- "Document completeness tracking reduces back-and-forth with claimants"

---

### Step 5: Semantic Search for Precedent Cases

**Duration**: 5 minutes

**Scenario**: "Find similar collision claims for adjudication guidance"

Using OpenSearch:
1. **Keyword search**: `"collision" AND "front damage" AND "intersection"` → exact matches
2. **Semantic search**: "multi-vehicle intersection collision with pedestrian injury" → finds similar cases
3. **Combined**: Filter by claim type + damage range + semantic similarity

**Talking points**:
- "Adjusters find precedent cases in seconds for consistent adjudication"
- "Semantic search discovers similar claims even with different descriptions"
- "OpenSearch Serverless note: first search after extended idle may take 10–30 seconds for OCU warm-up"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 92%+ (5 categories) | PoC result; production varies |
| Processing time | 43 seconds/file | Single file; batch depends on concurrency |
| Cost per file | $0.05–$0.07 | Damage photos: ~$0.05 |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Claims document search | 15 min/claim × 2,000 claims/year → 2 min | **433 hours saved** |
| Fraud pattern detection | 5 cases/month × ¥500K avg. savings | **¥30M loss prevention** |
| Adjuster precedent search | 30 min/case × 500 cases/year → 5 min | **208 hours saved** |
| Document completeness tracking | 10 min/claim × 2,000 claims/year → automated | **333 hours saved** |

**Conservative annual productivity value**: ~974 hours × ¥5,000/hr = **¥4,870,000** (~$32,500)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~2,276%

**Assumptions**: 50% adoption, mid-size insurer, fraud prevention value stated separately from productivity.

---

## Limitations Relevant to Insurance

| Limitation | Impact for Insurance |
|-----------|---------------------|
| S3 AP (pipeline reads only) | Cannot auto-archive settled claims via pipeline |
| No S3 Event Notifications | Cannot trigger downstream claims workflow via S3 events |
| Bedrock accuracy varies | Medical terminology and legal language may need prompt tuning |
| Damage photo analysis | AI severity estimation is assistive signal only — not a replacement for adjuster judgment |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| PII handling | Claims documents contain extensive PII; verify data handling policies with compliance |
| Fraud detection | AI flags are indicators only — not determinations; human review required |

---

## Customization Points

1. **Claim types**: Add company-specific categories (life, property, liability, specialty lines)
2. **Severity thresholds**: Configure damage amount tiers matching internal escalation rules
3. **Fraud indicators**: Define custom patterns based on company-specific fraud experience
4. **Regulatory mapping**: Map document requirements by jurisdiction and line of business

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

*Related: [use-cases/insurance/](../../use-cases/insurance/)*
*Pair document: [industry-insurance-ja.md](./industry-insurance-ja.md)*

# Legal Industry Demo Scenario: Contract & Case Document AI Classification

> Demo scenario for improving document discovery, matter management, and retention in law firms and legal departments.

---

## Business Context

### Challenge

Legal teams face:

- **Document discovery burden**: Finding relevant documents for litigation or due diligence across years of case files takes weeks
- **Contract lifecycle gaps**: Thousands of contracts across file shares with no visibility into renewal dates, terms, or expiry
- **Privilege classification**: Difficulty identifying privileged documents quickly during discovery
- **Knowledge reuse**: Prior case research and opinions are lost in unstructured file systems

### Solution Value

- Legal documents auto-classified by type (contracts, pleadings, opinions, correspondence)
- Contract metadata extracted (parties, dates, key terms) for lifecycle management
- Document privilege indicators flagged automatically for review
- Prior case research discoverable via semantic search

---

## Demo Flow

### Step 1: Place Sample Legal Documents on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry legal --target /vol/legal/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `nda-acme-corp-2025-renewal.pdf` | Contract/NDA | Non-disclosure agreement with renewal clause |
| `litigation-brief-case-2026-0042.docx` | Pleading | Summary judgment brief |
| `legal-opinion-ip-transfer-20260115.pdf` | Legal Opinion | IP assignment analysis |
| `client-email-privilege-matter-789.msg` | Privileged Communication | Attorney-client privileged email |
| `due-diligence-checklist-MA-2026.xlsx` | Due Diligence | M&A transaction document checklist |

**Talking points**:
- "Attorneys and paralegals save documents normally — AI classification is invisible to them"
- "Works with both NFS (Linux/Mac) and SMB (Windows) access"
- "Note: file content passes through Lambda memory during processing (ephemeral, not persisted)"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: nda-acme-corp-2025-renewal.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Contract/NDA
   - Parties: [Our Client], Acme Corporation
   - Execution date: 2025-03-15
   - Expiry date: 2026-03-14
   - Auto-renewal: Yes (30 days notice required)
   - Key terms: Confidentiality, non-compete (2 years)
   - Privilege: No
✅ Classified in 44.2s | Cost: $0.07
```

**Talking points**:
- "AI extracts structured contract metadata — parties, dates, renewal terms"
- "Privilege indicators are flagged for review, not determined definitively"
- "Confidence: 0.94 average on PoC test dataset. Production accuracy varies — complex legal terminology and multi-language contracts may need prompt tuning."

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       document_parties, expiry_date, privilege_flag, matter_id
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'legal'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | privilege_flag | expiry_date |
|-----------|------------------|:---------:|:--------------:|:----------:|
| .../nda-acme-corp-2025-renewal.pdf | Contract/NDA | 0.95 | No | 2026-03-14 |
| .../litigation-brief-case-2026-0042.docx | Pleading/Brief | 0.94 | No | - |
| .../legal-opinion-ip-transfer-20260115.pdf | Legal Opinion | 0.93 | Work Product | - |
| .../client-email-privilege-matter-789.msg | Communication | 0.91 | Attorney-Client | - |
| .../due-diligence-checklist-MA-2026.xlsx | Due Diligence | 0.94 | No | - |

**Note**: Confidence scores are PoC results. Privilege classification is AI-assisted — human attorney review is required for privilege determinations.

---

### Step 4: Contract Lifecycle Queries

**Duration**: 5 minutes

```sql
-- Contracts expiring in next 60 days
SELECT file_path, document_parties, expiry_date, auto_renewal,
       renewal_notice_days
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Contract%'
  AND expiry_date BETWEEN current_date AND current_date + interval '60' day
ORDER BY expiry_date ASC;

-- Privileged documents for specific matter
SELECT file_path, ai_classification, privilege_flag, creation_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE matter_id = 'CASE-2026-0042'
  AND privilege_flag IS NOT NULL
ORDER BY creation_date DESC;

-- Due diligence document inventory
SELECT ai_classification, count(*) as doc_count,
       min(creation_date) as earliest, max(creation_date) as latest
FROM s3_tables.metadata_catalog.file_metadata
WHERE matter_id = 'MA-2026'
GROUP BY ai_classification;
```

**Talking points**:
- "Contract renewal tracking that previously required manual calendar management"
- "Privilege log preparation time reduced from days to hours"
- "Note: first Athena query after idle period: 3–5 seconds cold start"

---

### Step 5: Semantic Search for Prior Research

**Duration**: 5 minutes

**Scenario**: "Find prior legal opinions on IP assignment in cross-border transactions"

OpenSearch semantic search:
- "intellectual property transfer international jurisdiction" → finds relevant opinions
- Filter by `ai_classification = 'Legal Opinion'` + semantic relevance

**Talking points**:
- "Associates find relevant prior work without asking senior partners"
- "Semantic search finds conceptually related documents even with different terminology"
- "OpenSearch warm-up note: 10–30 seconds after extended idle"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 90%+ (5 categories) | PoC result; complex legal terminology may reduce accuracy |
| Processing time | 42 seconds/file | Standard documents |
| Cost per file | $0.07 | 100KB–1MB documents |
| Contract metadata extraction | Key fields in 85%+ of contracts | Complex multi-party contracts may have lower extraction rates |
| Privilege flagging | High recall (few misses) | False positives expected — human review required |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Document discovery | 2 weeks → 2 days × 10 matters/year | **800 hours saved** |
| Contract renewal tracking | 30 min/contract × 200 contracts | **100 hours saved** |
| Prior research discovery | 4 hours → 30 min × 100 searches/year | **350 hours saved** |
| Privilege log preparation | 3 days → 4 hours × 5 matters/year | **130 hours saved** |

**Conservative annual productivity value**: ~1,380 hours × ¥8,000/hr (legal rate) = **¥11,040,000** (~$73,600)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~5,280%

**Assumptions**: 50% adoption, conservative time estimates. Legal hourly rate reflects paralegal/associate blend.

---

## Limitations Relevant to Legal

| Limitation | Impact for Legal |
|-----------|-----------------|
| Privilege classification is AI-assisted | NOT determinative — attorney review required for all privilege assertions |
| Lambda ephemeral processing | Privileged/confidential content passes through Lambda memory — evaluate with IT security |
| Bedrock accuracy varies | Multi-language contracts, handwritten annotations, and specialized legal terms affect accuracy |
| S3 AP read-only | Cannot auto-apply hold notices or move documents to litigation hold storage |
| No S3 Event Notifications | Cannot auto-trigger matter management system updates via S3 events |
| Complex contracts | Multi-party, multi-jurisdictional contracts may have lower metadata extraction accuracy |

---

## Customization Points

1. **Classification categories**: Add firm-specific document types (engagement letters, billing memos, etc.)
2. **Contract fields**: Configure extraction for jurisdiction-specific terms (governing law, dispute resolution)
3. **Privilege indicators**: Tune prompt for firm's privilege classification approach
4. **Matter management**: Integrate matter IDs for document-to-case association
5. **Retention policies**: Map document types to professional responsibility retention requirements

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

*Related config: [`legal.yaml`](../sample-data/industry-configs/legal.yaml)*
*Pair document: [industry-legal-ja.md](./industry-legal-ja.md)*

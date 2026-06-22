# Education & Research Demo Scenario: Research Paper & Grant Proposal Intelligence

🌐 [日本語](industry-education-ja.md) | English

> Automated classification and search of research papers, thesis documents, lecture recording metadata, and grant proposals across academic institution file shares.

---

## Business Context

### Challenge

Academic institutions face:

- **Research output fragmentation**: Papers, datasets, and supplementary materials scattered across department shares with no unified discovery
- **Grant proposal chaos**: Proposals, budgets, review feedback, and award documents stored inconsistently across research groups
- **Thesis management gaps**: Draft versions, committee feedback, and final submissions lack systematic version tracking
- **Institutional knowledge loss**: Faculty departures leave behind unorganized research files with no context

### Solution Value

- Research documents classified automatically by department, topic, funding source, and publication status
- "Find all NSF-funded papers in machine learning from our department in 2026" answered via SQL
- Grant proposals tracked with deadlines, review status, and related publications
- Cross-departmental research discovery enabled through semantic search

---

## Demo Flow

### Step 1: Place Sample Education Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry education --target /vol/research/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `paper-ML-transformer-efficiency-2026.pdf` | Research Paper | Published paper on transformer optimization |
| `thesis-draft-PhD-tanaka-ch4-v3.pdf` | Thesis Document | PhD thesis chapter 4, third revision |
| `grant-proposal-JST-CREST-2026.pdf` | Grant Proposal | JST CREST funding application |
| `lecture-metadata-CS401-week12.json` | Lecture Metadata | Advanced ML lecture recording info |
| `dataset-readme-sentiment-analysis-v2.md` | Dataset Documentation | Research dataset description |

**Talking points**:
- "Researchers keep saving files their way — classification happens automatically"
- "Department NFS shares and individual research group shares both supported"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: paper-ML-transformer-efficiency-2026.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Research Paper
   - Department: Computer Science
   - Topic: Machine Learning / Transformer Architecture
   - Authors: 3
   - Funding: JST CREST
   - Publication status: Published
   - Venue: ICML 2026
   - Keywords: efficiency, attention mechanism, sparse
✅ Classified in 44.1s | Cost: $0.07
```

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       department, topic, funding_source, status
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'education'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | department | topic | status |
|-----------|------------------|:---------:|:----------:|:-----:|:------:|
| /vol/research/paper-ML-transformer-efficiency-2026.pdf | Research Paper | 0.95 | CS | ML/Transformer | Published |
| /vol/research/thesis-draft-PhD-tanaka-ch4-v3.pdf | Thesis/Draft | 0.94 | CS | ML | In Progress |
| /vol/research/grant-proposal-JST-CREST-2026.pdf | Grant Proposal | 0.96 | CS | ML | Submitted |
| /vol/research/lecture-metadata-CS401-week12.json | Lecture Metadata | 0.98 | CS | ML | Active |
| /vol/research/dataset-readme-sentiment-analysis-v2.md | Dataset Documentation | 0.93 | CS | NLP | Published |

---

### Step 4: Academic Queries

**Duration**: 5 minutes

```sql
-- Research output by department and funding source
SELECT department, funding_source, COUNT(*) as papers, publication_status
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Research Paper'
GROUP BY department, funding_source, publication_status;

-- Grant proposals approaching deadlines
SELECT file_path, funding_agency, proposal_title, deadline, days_remaining
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Grant Proposal'
  AND status = 'In Preparation'
  AND deadline < current_date + interval '60' day
ORDER BY deadline ASC;

-- Thesis progress tracking
SELECT student_name, chapter, version, last_modified, committee_feedback
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Thesis%'
ORDER BY student_name, chapter;
```

---

### Step 5: Semantic Search for Research Discovery

**Duration**: 5 minutes

**Scenario**: "Find research related to efficient attention mechanisms"

Using OpenSearch:
1. **Keyword search**: `"attention mechanism" AND "efficiency"` → exact matches
2. **Semantic search**: "reducing computational cost of self-attention in large language models" → finds related papers and datasets
3. **Combined**: Filter by department + year + semantic relevance

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 93%+ (5 categories) | PoC result; production varies |
| Processing time | 44 seconds/file | Academic papers tend to be longer |
| Cost per file | $0.07 | Research papers |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Research paper discovery | 30 min/search × 200 searches/year → 3 min | **90 hours saved** |
| Grant proposal preparation | 2 days saved per proposal × 10 proposals/year | **160 hours saved** |
| Thesis document management | 2 hours/week × 20 students → automated | **80 hours saved** |
| Institutional knowledge retention | Qualitative — prevents knowledge loss | **Risk mitigation** |

**Conservative annual productivity value**: ~330 hours × ¥6,000/hr = **¥1,980,000** (~$13,200)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~867%

---

## Limitations Relevant to Education

| Limitation | Impact for Education |
|-----------|---------------------|
| S3 AP (pipeline reads only) | Cannot trigger publication workflows via pipeline |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Copyright content | Research papers may contain copyrighted material; metadata-only extraction |
| Student privacy | FERPA-equivalent student data handling required for thesis documents |
| Multi-language | Research in multiple languages may reduce classification accuracy |
| Open access | Does not replace institutional repository systems |

---

## Customization Points

1. **Department taxonomy**: Configure for institution-specific department and lab structure
2. **Funding agencies**: Add relevant agencies (JST, JSPS, NSF, NIH, EU Horizon)
3. **Publication venues**: Track target venues by research group
4. **Thesis stages**: Configure milestone tracking per graduate program requirements

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

*Related: [use-cases/education/](../../use-cases/education/)*
*Pair document: [industry-education-ja.md](./industry-education-ja.md)*

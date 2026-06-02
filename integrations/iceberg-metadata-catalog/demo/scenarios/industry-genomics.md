# Genomics & Biotech Demo Scenario: Sequencing Data & Variant Analysis Intelligence

🌐 [日本語](industry-genomics-ja.md) | English

> Automated classification and search of sequencing reports, FASTQ quality logs, variant analysis files, and patient consent documents across genomics file shares.

---

## Business Context

### Challenge

Genomics organizations face:

- **Data scale explosion**: Each sequencing run generates hundreds of files (FASTQ, BAM, VCF) with complex naming and versioning
- **Quality tracking gaps**: QC reports and metrics scattered across run directories with no aggregated visibility
- **Variant interpretation delays**: Finding related variant analyses and clinical annotations requires searching across multiple projects
- **Consent management complexity**: Patient consent forms and data use agreements stored inconsistently across studies

### Solution Value

- Sequencing outputs classified automatically by sample, run, pipeline version, and quality status
- "Find all failed QC runs in the last month for panel sequencing" answered via SQL
- Variant analysis files linked to samples with clinical significance annotations
- Consent documents tracked with expiry dates and scope of permitted data use

---

## Demo Flow

### Step 1: Place Sample Genomics Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry genomics --target /vol/genomics-data/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `qc-report-RUN2026042-S001.html` | QC Report | Sequencing quality metrics, sample S001 |
| `variant-call-S001-germline.vcf` | Variant File | Germline variant calls, 42,847 variants |
| `fastq-metrics-RUN2026042.json` | FASTQ Metrics | Run-level quality statistics |
| `consent-form-PT8842-genomic-v2.pdf` | Consent Form | Patient genomic data consent, version 2 |
| `clinical-annotation-S001-pathogenic.tsv` | Clinical Annotation | Pathogenic variant annotations |

**Talking points**:
- "High-throughput NFS from FSx handles the I/O demands of bioinformatics pipelines"
- "FPolicy triggers on pipeline output files without impacting compute performance"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: qc-report-RUN2026042-S001.html
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: QC Report/Sequencing
   - Run ID: RUN2026042
   - Sample ID: S001
   - Sequencing type: WGS (Whole Genome)
   - Coverage: 30x mean
   - Quality: PASS (Q30 > 85%)
   - Pipeline: GATK 4.5.2
   - Instrument: NovaSeq 6000
✅ Classified in 39.8s | Cost: $0.07
```

**Talking points**:
- "AI identifies sequencing type, quality metrics, pipeline version, and pass/fail status"
- "Variant files classified by type (germline, somatic) and clinical significance"
- "Classification confidence: PoC accuracy; production varies by report format"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       run_id, sample_id, sequencing_type, quality_status
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'genomics'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | run_id | sample_id | quality_status |
|-----------|------------------|:---------:|:------:|:---------:|:--------------:|
| /vol/genomics-data/qc-report-RUN2026042-S001.html | QC Report/Sequencing | 0.96 | RUN2026042 | S001 | PASS |
| /vol/genomics-data/variant-call-S001-germline.vcf | Variant/Germline | 0.95 | RUN2026042 | S001 | - |
| /vol/genomics-data/fastq-metrics-RUN2026042.json | FASTQ Metrics | 0.98 | RUN2026042 | - | PASS |
| /vol/genomics-data/consent-form-PT8842-genomic-v2.pdf | Consent/Genomic | 0.94 | - | S001 | - |
| /vol/genomics-data/clinical-annotation-S001-pathogenic.tsv | Clinical Annotation | 0.93 | - | S001 | - |

**Talking points**:
- "Run and sample linkage maintained automatically across file types"
- "Quality pass/fail status extracted for pipeline monitoring"
- "Consent forms linked to patient/sample for data governance"

---

### Step 4: Genomics Operations Queries

**Duration**: 5 minutes

```sql
-- Failed QC runs in last 30 days
SELECT run_id, sample_id, quality_status, failure_reason, run_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'QC Report/Sequencing'
  AND quality_status = 'FAIL'
  AND scan_timestamp > current_date - interval '30' day
ORDER BY run_date DESC;

-- Samples with pathogenic variants requiring clinical review
SELECT sample_id, file_path, pathogenic_count, gene_list
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Clinical Annotation'
  AND pathogenic_count > 0
ORDER BY pathogenic_count DESC;

-- Consent expiry tracking
SELECT patient_id, sample_id, consent_scope, expiry_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Consent/Genomic'
  AND expiry_date < current_date + interval '180' day
ORDER BY expiry_date ASC;
```

**Talking points**:
- "Lab directors monitor QC trends and identify systematic issues"
- "Clinical geneticists prioritize samples with actionable findings"
- "Data governance team tracks consent coverage and expiry"

---

### Step 5: Semantic Search for Variant Discovery

**Duration**: 5 minutes

**Scenario**: "Find samples with similar variant profiles for cohort analysis"

Using OpenSearch:
1. **Keyword search**: `"BRCA1" AND "pathogenic"` → exact variant matches
2. **Semantic search**: "breast cancer predisposition variants in DNA repair pathway genes" → finds related annotations
3. **Combined**: Filter by variant significance + gene pathway + semantic similarity

**Talking points**:
- "Cohort identification for research studies accelerated from days to minutes"
- "Semantic search finds related variants across different annotation standards"
- "OpenSearch Serverless note: first search after extended idle may take 10–30 seconds for OCU warm-up"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 94%+ (5 categories) | PoC result; production varies |
| Processing time | 40 seconds/file | Metadata extraction; not variant calling |
| Cost per file | $0.05–$0.07 | Report files; large BAM/FASTQ by metadata only |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| QC monitoring | 30 min/day × 5 lab techs → automated dashboard | **~45 hours/year** |
| Sample tracking | 15 min/sample × 2,000 samples/year → 2 min | **433 hours saved** |
| Consent compliance | 4 hours/week manual tracking → automated | **192 hours saved** |
| Variant cohort search | 2 days/search × 50 searches/year → 30 min | **775 hours saved** |

**Conservative annual productivity value**: ~1,445 hours × ¥7,000/hr = **¥10,115,000** (~$67,400)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~4,793%

**Assumptions**: 50% adoption, mid-size genomics lab, no additional value from faster discovery or clinical turnaround.

---

## Limitations Relevant to Genomics

| Limitation | Impact for Genomics |
|-----------|---------------------|
| S3 AP (pipeline reads only) | Cannot trigger re-analysis pipelines via the catalog |
| No S3 Event Notifications | Cannot trigger downstream analysis via S3 events |
| Large binary files | BAM/CRAM files (10–100GB) processed by metadata only; not content-level analysis |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Clinical interpretation | AI classification is metadata-level; not clinical variant interpretation |
| Consent sensitivity | Patient data handling must comply with institutional ethics board requirements |
| Data sovereignty | Genomic data may have country-specific storage requirements (e.g., APPI in Japan) |

- **Binary file formats**: FASTQ, BAM, VCF, and other bioinformatics formats cannot be directly classified by Bedrock Claude. Use format-specific parsers (e.g., BioPython) in a pre-processing Lambda to extract headers and quality metrics before AI classification. See [AI Prompt Guide](ai-prompt-customization-guide.md) multimodal matrix.

---

## Customization Points

1. **Pipeline versions**: Track multiple bioinformatics pipeline versions (GATK, DRAGEN, custom)
2. **Panel types**: Configure for WGS, WES, targeted panels, RNA-seq, etc.
3. **Variant databases**: Link annotations to ClinVar, COSMIC, gnomAD versions
4. **Consent scopes**: Define permitted data use categories per institutional policy

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

*Related: [use-cases/genomics/](../../use-cases/genomics/)*
*Pair document: [industry-genomics-ja.md](./industry-genomics-ja.md)*

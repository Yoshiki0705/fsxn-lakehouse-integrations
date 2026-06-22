# Healthcare Demo Scenario: Medical Document AI Classification & Patient Data Governance

> Demo scenario for improving clinical document management and regulatory compliance in healthcare.

---

## Business Context

### Challenge

Healthcare organizations face:

- **Clinical document overload**: Radiology images, pathology reports, clinical notes, and consent forms accumulate without systematic classification
- **Patient data governance gaps**: Documents containing PHI (Protected Health Information) spread across file shares without visibility
- **Regulatory compliance burden**: Meeting medical record retention requirements (5–30 years depending on jurisdiction) is manual and error-prone
- **Research data discovery**: Researchers cannot find relevant clinical datasets for studies

### Solution Value

- Medical documents auto-classified by type (radiology, pathology, administrative, consent)
- PHI automatically detected and flagged for governance enforcement
- Retention policies applied based on document classification
- Research teams search for relevant clinical data via SQL/semantic query

---

## Demo Flow

### Step 1: Place Sample Medical Documents on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry healthcare --target /vol/medical-records/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `radiology-mri-brain-20260115.dcm` | DICOM Image | Brain MRI scan |
| `pathology-report-PAT-2026-0089.pdf` | Pathology Report | Tissue biopsy results |
| `clinical-note-dr-tanaka-20260120.docx` | Clinical Note | Patient consultation record |
| `consent-form-surgery-PT-4567.pdf` | Consent Form | Surgical procedure consent |
| `pharmacy-order-RX-2026-1234.pdf` | Prescription | Medication order |

**Talking points**:
- "Healthcare staff save documents as they normally do — no workflow change required"
- "DICOM files, PDFs, Word docs — all processed by the same pipeline"
- "Important: file content passes through Lambda memory during processing (ephemeral, not persisted). Review with your compliance team for PHI handling requirements."

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: pathology-report-PAT-2026-0089.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Pathology Report
   - Department: Pathology
   - Patient ID detected: Yes (PHI)
   - Study type: Tissue biopsy
   - Retention requirement: 10 years (medical record)
   - PHI elements: patient name, DOB, medical record number
✅ Classified in 43.2s | Cost: $0.07
```

**Talking points**:
- "AI identifies document type AND extracts structured metadata from medical content"
- "PHI detection is automatic — flagged for governance before anyone queries the data"
- "Classification confidence: 0.94 average on PoC test dataset. Production accuracy varies — medical terminology and image quality affect results."

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       department, phi_detected, retention_years
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'healthcare'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | department | phi_detected | retention_years |
|-----------|------------------|:---------:|:----------:|:------------:|:--------------:|
| .../radiology-mri-brain-20260115.dcm | Radiology/MRI | 0.93 | Radiology | Yes | 10 |
| .../pathology-report-PAT-2026-0089.pdf | Pathology Report | 0.95 | Pathology | Yes | 10 |
| .../clinical-note-dr-tanaka-20260120.docx | Clinical Note | 0.94 | Internal Medicine | Yes | 5 |
| .../consent-form-surgery-PT-4567.pdf | Consent Form | 0.96 | Surgery | Yes | 30 |
| .../pharmacy-order-RX-2026-1234.pdf | Prescription | 0.92 | Pharmacy | Yes | 3 |

**Note**: Confidence scores are PoC results. Production accuracy varies by file type, scan quality, and language mix.

---

### Step 4: Compliance & Governance Queries

**Duration**: 5 minutes

```sql
-- Documents with PHI requiring access control review
SELECT file_path, ai_classification, phi_elements, access_restricted
FROM s3_tables.metadata_catalog.file_metadata
WHERE phi_detected = true AND access_restricted = false
ORDER BY scan_timestamp DESC;

-- Retention compliance: documents past retention period
SELECT file_path, ai_classification, creation_date,
       retention_years,
       date_add('year', retention_years, creation_date) as expiry_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE date_add('year', retention_years, creation_date) < current_date;

-- Department document inventory
SELECT department, ai_classification, count(*) as doc_count,
       sum(case when phi_detected then 1 else 0 end) as phi_count
FROM s3_tables.metadata_catalog.file_metadata
GROUP BY department, ai_classification
ORDER BY department, doc_count DESC;
```

**Talking points**:
- "Compliance team can run these queries on demand — no IT ticket required"
- "PHI visibility enables proactive governance rather than reactive breach response"
- "Note: first Athena query after idle takes 3–5 seconds (cold start)"

---

### Step 5: Research Data Discovery

**Duration**: 5 minutes

**Scenario**: "Find all pathology reports related to liver biopsies from 2025–2026"

```sql
-- Structured search
SELECT file_path, study_type, creation_date, department
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Pathology Report'
  AND study_type LIKE '%liver%'
  AND creation_date >= date '2025-01-01';
```

OpenSearch semantic search:
- "liver biopsy fibrosis staging" → finds relevant reports even with different terminology

**Talking points**:
- "Researchers find relevant datasets without accessing PHI directly"
- "Semantic search finds documents using clinical concepts, not just exact keywords"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 90%+ (5 categories) | PoC result; medical images may have lower accuracy |
| Processing time | 42 seconds/file | DICOM files may take longer (larger size) |
| Cost per file | $0.07–$0.15 | Varies by file size (DICOM images: ~$0.15) |
| Athena query response | 2–3 seconds | After cold start (+3–5s first query) |
| PHI detection rate | 95%+ | English PHI well-detected; Japanese PHI accuracy varies |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Compliance audit prep | 3 days → 4 hours × 2 audits/year | **44 hours saved** |
| Document search (clinical staff) | 10 min/day × 30 staff × 50% adoption | **550 hours/year** |
| PHI breach risk reduction | Risk mitigation (not directly quantified) | **Risk reduction** |
| Research data discovery | 2 days/study → 1 hour/study × 20 studies/year | **300 hours saved** |

**Conservative annual productivity value**: ~894 hours × ¥5,000/hr = **¥4,470,000** (~$29,800)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~2,079%

---

## Limitations Relevant to Healthcare

| Limitation | Impact for Healthcare |
|-----------|----------------------|
| Lambda ephemeral processing | PHI passes through Lambda memory — review with compliance team for HIPAA/regulatory requirements |
| Bedrock accuracy varies | Medical terminology, handwritten notes, and low-quality scans reduce accuracy |
| S3 AP (pipeline reads only) | Cannot auto-quarantine or move flagged PHI documents via analytics pipeline |
| DICOM image processing | Large DICOM files (10MB+) cost ~$0.15/file and may have lower classification confidence |
| No write-back | Governance tags cannot be written back to original file metadata on FSx |
| Regulatory scope | Solution provides assistive classification — not a substitute for clinical data governance systems |

---

## Customization Points

1. **Classification categories**: Map to institution-specific document types (discharge summaries, nursing notes, etc.)
2. **PHI types**: Configure for jurisdiction (HIPAA, Japanese medical records law)
3. **Retention rules**: Hospital-specific retention policies by document category
4. **Access control**: Department-level access via Lake Formation

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

*Related config: [`healthcare.yaml`](../sample-data/industry-configs/healthcare.yaml)*
*Pair document: [industry-healthcare-ja.md](./industry-healthcare-ja.md)*

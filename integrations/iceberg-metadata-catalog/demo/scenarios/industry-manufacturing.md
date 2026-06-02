# Manufacturing Demo Scenario: Engineering Drawing AI Classification & Similar Design Search

> Demo scenario for improving design file utilization in engineering departments.

---

## Business Context

### Challenge

Engineering departments face:

- **CAD/PDF files accumulate without classification**: Design drawings, quality reports, meeting minutes generated daily with no systematic management
- **Low design reuse rate**: Similar prior designs exist but cannot be found, leading to redesign from scratch
- **Search takes too long**: 30+ minutes/day per engineer browsing deep folder hierarchies manually
- **Knowledge loss**: Veteran engineer expertise disappears on retirement

### Solution Value

- Files classified automatically the moment they are created/modified
- "Find all drawings for part number ABC-1234" answered with a single SQL query
- "Find designs similar to this drawing" via vector search
- 30 minutes/day search time reduction per engineer

---

## Demo Flow

### Step 1: Place CAD/PDF Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry manufacturing --target /vol/engineering/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `frame-assembly-ABC-1234-R3.pdf` | Design Drawing | Main frame assembly, SUS304 |
| `quality-report-L2026-001.pdf` | Quality Report | Lot L2026-001 inspection results |
| `bom-main-frame-v2.xlsx` | Bill of Materials | Main frame BOM (47 parts) |
| `design-review-20260120.docx` | Meeting Minutes | Design review meeting (8 attendees) |
| `shaft-bearing-DEF-5678.dwg` | CAD 3D Model | Shaft bearing 3D model |

**Talking points**:
- "Engineers save files as they normally do. No special action required."
- "Both NFS and SMB trigger the AI pipeline automatically."
- "Note: file content passes through Lambda memory during processing — ephemeral, not persisted outside the FSx volume."

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: frame-assembly-ABC-1234-R3.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - File type: CAD/Design Drawing
   - Part number: ABC-1234
   - Revision: R3
   - Material: SUS304
   - Project: PRJ-2026-042
   - Department: Engineering Dept. 1
✅ Classified in 42.1s | Cost: $0.07
```

**Talking points**:
- "FPolicy is filesystem-level event detection — no polling required"
- "Bedrock Claude reads PDF content and auto-extracts part numbers, revisions, and materials"
- "Japanese documents are processed accurately"
- "Confidence: 0.94 on PoC test dataset. Production accuracy varies by file type, language mix, and domain terminology."

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
-- Check classification results via Athena
SELECT file_path, ai_classification, confidence_score, part_number, revision, material
FROM s3_tables.metadata_catalog.file_metadata
WHERE department = 'Engineering Dept. 1'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | part_number | revision | material |
|-----------|------------------|:---------:|:-----------:|:--------:|:--------:|
| /vol/engineering/frame-assembly-ABC-1234-R3.pdf | CAD/Design Drawing | 0.94 | ABC-1234 | R3 | SUS304 |
| /vol/engineering/quality-report-L2026-001.pdf | Quality Report | 0.97 | - | - | - |
| /vol/engineering/bom-main-frame-v2.xlsx | BOM | 0.91 | - | v2 | - |
| /vol/engineering/design-review-20260120.docx | Meeting Minutes | 0.96 | - | - | - |
| /vol/engineering/shaft-bearing-DEF-5678.dwg | CAD 3D Model | 0.93 | DEF-5678 | - | - |

**Note**: Confidence scores shown are PoC results on test dataset. Production accuracy varies by file type, language mix, and domain terminology.

**Talking points**:
- "All 5 file types correctly classified"
- "Part numbers, materials, and revisions auto-extracted from document content"
- "No manual tagging required — save the file and it's cataloged"

---

### Step 4: Part Number and Quality Search

**Duration**: 5 minutes

**Scenario**: "Find all design documents for part ABC-1234"

```sql
-- All documents for parts starting with ABC
SELECT file_path, ai_classification, part_number, revision, last_modified
FROM s3_tables.metadata_catalog.file_metadata
WHERE part_number LIKE 'ABC%'
ORDER BY revision DESC;

-- Quality reports for specific lot
SELECT file_path, inspection_result, lot_number, inspection_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE lot_number = 'L2026-001'
ORDER BY inspection_date DESC;

-- Design changes in last 7 days
SELECT file_path, change_type, part_number, scan_timestamp
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification IN ('CAD/Design Drawing', 'CAD 3D Model')
  AND scan_timestamp > current_timestamp - interval '7' day
ORDER BY scan_timestamp DESC;
```

**Talking points**:
- "What used to require browsing folder hierarchies is now a single SQL query"
- "Part number, lot number, date — any dimension is searchable"
- "Note: first Athena query after idle period: 3–5 seconds (cold start)"

---

### Step 5: Vector Search for Similar Designs

**Duration**: 5 minutes

**Scenario**: "Are there any past designs similar to this frame assembly?"

OpenSearch Dashboards:
1. **Keyword search**: `"SUS304 frame assembly"` → displays related files
2. **Similarity search**: Select `frame-assembly-ABC-1234-R3.pdf` → "Find similar" → vector similarity discovers past designs
3. **Natural language**: "Design drawings using aluminum alloy with strength calculations" → semantic search

**Talking points**:
- "Vector search finds similar content even when file names are completely different"
- "Reusing past designs saves significant engineering time"
- "System complements veteran engineer tacit knowledge"
- "OpenSearch warm-up: 10–30 seconds after extended idle"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 90%+ (5 categories) | PoC result; production varies by file quality |
| Processing time | 42 seconds/file | Single file |
| Cost per file | $0.07 | 100KB–1MB documents |
| Athena query response | 2–3 seconds | After cold start (+3–5s first query) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |
| Vector similarity precision | Top 5 results contain relevant files | Depends on document diversity |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Search time reduction | 10 min/day × 50 engineers × 50% adoption × 250 days | **1,042 hours/year** |
| Design reuse improvement | 10% of new designs → reuse existing (conservative) | **Engineering time: ~5% reduction** |
| Quality traceability | Defect tracing: 2 hours → 5 min | **Immediate tracing** |
| Compliance | Manual classification → automated (audit effort reduced) | **Audit efficiency: 50% improvement** |

**Conservative annual productivity value**: ~1,042 hours × ¥5,000/hr = **¥5,210,000** (~$34,700)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~2,436%

**Assumptions**: 50% adoption, 10 min/day actual search reduction (not 30 min), conservative design reuse rate.

---

## Limitations Relevant to Manufacturing

| Limitation | Impact for Manufacturing |
|-----------|------------------------|
| Bedrock accuracy on CAD files | Binary CAD formats (DWG, STEP) classified by filename/metadata — limited content analysis of proprietary formats |
| FPolicy latency (~1–5ms) | Minimal for file saves; test if CAD applications perform frequent auto-saves on shared volumes |
| S3 AP (pipeline reads only) | Cannot auto-update PLM systems or write status back to file metadata |
| Lambda ephemeral access | Design file content passes through Lambda memory — evaluate IP protection requirements |
| Classification confidence varies | Handwritten notes, scanned old drawings, and mixed-language documents reduce accuracy |
| No S3 Event Notifications | Cannot trigger PLM/MES system updates via S3 events |

---

## Customization Points

1. **Classification categories**: Match customer's document taxonomy (customer-specific file types)
2. **Extraction fields**: Part numbers, project codes, department names, material specifications
3. **Language support**: Japanese + English mixed documents supported
4. **Security**: Lake Formation for department-level access control
5. **PLM integration**: Metadata export for downstream PLM system consumption

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

*Related config: [`manufacturing.yaml`](../sample-data/industry-configs/manufacturing.yaml)*
*Pair document: [industry-manufacturing-ja.md](./industry-manufacturing-ja.md)*

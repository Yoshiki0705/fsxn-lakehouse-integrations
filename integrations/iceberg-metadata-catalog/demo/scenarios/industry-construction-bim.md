# Construction & BIM Demo Scenario: BIM Model & Site Inspection Intelligence

🌐 [日本語](industry-construction-bim-ja.md) | English

> Automated classification and search of BIM models, site photos, safety inspection reports, and permit documents across construction project file shares.

---

## Business Context

### Challenge

Construction firms face:

- **BIM model version chaos**: Multiple revisions of IFC/RVT models across disciplines (structural, MEP, architectural) with no unified version tracking
- **Site documentation sprawl**: Daily progress photos, safety inspection reports, and RFIs scattered across project folders
- **Permit tracking gaps**: Building permits, environmental approvals, and municipal filings stored without expiry tracking
- **Cross-discipline coordination**: Finding related documents across architectural, structural, and MEP disciplines requires manual effort

### Solution Value

- BIM models and construction documents classified automatically by discipline, phase, and revision status
- "Find all structural RFIs pending response for Building A" answered via SQL
- Site photos tagged with location, progress stage, and safety compliance status
- Permit expiry dates tracked with automated deadline awareness

---

## Demo Flow

### Step 1: Place Sample Construction Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry construction-bim --target /vol/construction/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `model-BLDG-A-structural-rev08.ifc` | BIM Model | Structural model, revision 8 |
| `site-photo-BLDG-A-floor3-20260601.jpg` | Site Photo | Floor 3 progress, concrete pour |
| `safety-inspection-BLDG-A-20260601.pdf` | Safety Report | Daily safety inspection, 2 findings |
| `permit-building-BLDG-A-2026-renewal.pdf` | Permit Document | Building permit renewal |
| `rfi-STR-042-column-spacing.pdf` | RFI Document | Structural column spacing clarification |

**Talking points**:
- "Project teams continue using CDE (Common Data Environment) workflows — FPolicy adds intelligence without changing process"
- "Both BIM models and paper-scanned documents supported"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: model-BLDG-A-structural-rev08.ifc
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: BIM Model/Structural
   - Project: Building A
   - Discipline: Structural
   - Revision: 8
   - LOD: 350
   - Phase: Construction
   - Clash status: 3 unresolved
   - Format: IFC 4.0
✅ Classified in 40.2s | Cost: $0.07
```

**Talking points**:
- "AI identifies discipline, revision, LOD level, and project phase from model metadata"
- "Site photos analyzed for progress stage and safety compliance indicators"
- "Classification confidence: PoC accuracy; production varies by file format and metadata completeness"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       project, discipline, revision, phase
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'construction-bim'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | project | discipline | revision |
|-----------|------------------|:---------:|:-------:|:----------:|:--------:|
| /vol/construction/model-BLDG-A-structural-rev08.ifc | BIM Model/Structural | 0.95 | Building A | Structural | 8 |
| /vol/construction/site-photo-BLDG-A-floor3-20260601.jpg | Site Photo/Progress | 0.92 | Building A | - | - |
| /vol/construction/safety-inspection-BLDG-A-20260601.pdf | Safety Inspection | 0.96 | Building A | - | - |
| /vol/construction/permit-building-BLDG-A-2026-renewal.pdf | Permit/Building | 0.97 | Building A | - | - |
| /vol/construction/rfi-STR-042-column-spacing.pdf | RFI/Structural | 0.94 | Building A | Structural | - |

---

### Step 4: Construction Queries

**Duration**: 5 minutes

```sql
-- Latest BIM model revisions by discipline
SELECT project, discipline, MAX(revision) as latest_rev, file_path
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'BIM Model%'
GROUP BY project, discipline;

-- Open safety findings requiring action
SELECT file_path, project, finding_type, severity, action_due_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Safety Inspection'
  AND finding_status = 'Open'
ORDER BY severity DESC, action_due_date ASC;

-- Permits approaching expiry
SELECT file_path, project, permit_type, expiry_date, days_until_expiry
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Permit%'
  AND expiry_date < current_date + interval '90' day
ORDER BY expiry_date ASC;
```

---

### Step 5: Semantic Search for Cross-Discipline Coordination

**Duration**: 5 minutes

**Scenario**: "Find all documents related to Building A structural column issues"

Using OpenSearch:
1. **Keyword search**: `"Building A" AND "column" AND "structural"` → exact matches
2. **Semantic search**: "load-bearing column design modification impact on MEP routing" → finds cross-discipline impacts
3. **Combined**: Filter by project + discipline + semantic relevance

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 93%+ (5 categories) | PoC result; production varies |
| Processing time | 40 seconds/file | Metadata extraction from model headers |
| Cost per file | $0.05–$0.07 | Document files; BIM models by metadata |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Model version search | 15 min/search × 300 searches/year → 2 min | **65 hours saved** |
| RFI tracking | 20 min/RFI × 200 RFIs/year → automated | **57 hours saved** |
| Safety report retrieval | 10 min/day × 50 project days → 2 min | **7 hours/project** |
| Permit compliance | 4 hours/month manual tracking → automated | **44 hours saved** |

**Conservative annual productivity value**: ~173 hours × ¥5,000/hr = **¥865,000** (~$5,800)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~324% (per project, scales with portfolio)

---

## Limitations Relevant to Construction

| Limitation | Impact for Construction |
|-----------|------------------------|
| S3 AP read-only | Cannot trigger BIM workflow transitions via pipeline |
| Large BIM files | IFC/RVT files (100MB+) processed at metadata level |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| CDE integration | Supplements but does not replace dedicated Common Data Environment platforms |
| ISO 19650 | AI metadata is supplementary; does not replace formal information management processes |

---

## Customization Points

1. **Discipline mapping**: Configure for project-specific discipline codes (S, A, M, E, P)
2. **LOD levels**: Track Level of Development per project phase requirements
3. **Safety categories**: Map finding types to company safety classification system
4. **Permit types**: Configure per jurisdiction and project type

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

*Related: [use-cases/construction-bim/](../../use-cases/construction-bim/)*
*Pair document: [industry-construction-bim-ja.md](./industry-construction-bim-ja.md)*

# Media & VFX Demo Scenario: Production Asset AI Classification & Creative Search

> Demo scenario for improving asset management, project tracking, and creative reuse in media production and VFX studios.

---

## Business Context

### Challenge

Media and VFX studios face:

- **Asset sprawl**: Thousands of renders, composites, textures, and plate scans accumulate across project shares without systematic tagging
- **Re-rendering instead of reusing**: Artists create new assets because finding existing similar ones is impractical
- **Project handoff friction**: When projects transfer between teams, understanding what assets exist and their status takes days
- **Storage costs at scale**: VFX projects generate 10–100TB per production; finding and archiving completed work is manual

### Solution Value

- Production assets auto-classified by type (render, composite, texture, plate, reference)
- Project and shot metadata extracted automatically from file paths and content
- Similar asset discovery via vector search ("find textures like this one")
- Project inventory queries for production managers

---

## Demo Flow

### Step 1: Place Sample Media Assets on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry media-vfx --target /vol/production/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `shot_010_comp_v003_final.exr` | Final Composite | Hero shot composite, version 3 |
| `env_forest_hdri_8k.hdr` | HDRI Environment | 8K forest environment map |
| `char_dragon_texture_diffuse_4k.png` | Character Texture | Dragon character diffuse map |
| `plate_scan_shot010_cam_A.dpx` | Plate Scan | Original camera plate |
| `previs_sequence_act2_v05.mov` | Previs | Act 2 previs animatic |

**Talking points**:
- "Artists save to project shares as normal — render farm outputs, Nuke composites, Maya renders all trigger the pipeline"
- "Large files (EXR, DPX) work fine but cost more for Bedrock classification (~$0.15 for 10MB+)"
- "NFS access from Linux render nodes triggers FPolicy just like SMB from Windows workstations"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: shot_010_comp_v003_final.exr
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Asset type: Final Composite
   - Project: [Production Name]
   - Shot: 010
   - Version: v003
   - Status: Final
   - Resolution: 4096x2160
   - Color space: ACEScg
   - Department: Compositing
✅ Classified in 45.1s | Cost: $0.15 (large file)
```

**Talking points**:
- "AI extracts project/shot/version from both file naming conventions and content analysis"
- "Large media files (10MB+) cost ~$0.15 per file for classification"
- "Confidence: 0.94 on PoC test dataset. Production accuracy varies — non-standard naming conventions reduce extraction accuracy."

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       project, shot, version, status, department, resolution
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'media-vfx'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | project | shot | version | status |
|-----------|------------------|:---------:|:-------:|:----:|:-------:|:------:|
| .../shot_010_comp_v003_final.exr | Final Composite | 0.95 | PROD-2026 | 010 | v003 | Final |
| .../env_forest_hdri_8k.hdr | HDRI Environment | 0.93 | Library | - | - | Approved |
| .../char_dragon_texture_diffuse_4k.png | Character Texture | 0.94 | PROD-2026 | - | - | WIP |
| .../plate_scan_shot010_cam_A.dpx | Plate Scan | 0.96 | PROD-2026 | 010 | - | Source |
| .../previs_sequence_act2_v05.mov | Previs | 0.92 | PROD-2026 | Act2 | v05 | Review |

**Note**: Confidence scores are PoC results. Non-standard naming conventions and proprietary formats may reduce accuracy.

---

### Step 4: Production Management Queries

**Duration**: 5 minutes

```sql
-- Shot completion status
SELECT shot, 
       count(case when status = 'Final' then 1 end) as final_count,
       count(case when status = 'WIP' then 1 end) as wip_count,
       max(scan_timestamp) as last_activity
FROM s3_tables.metadata_catalog.file_metadata
WHERE project = 'PROD-2026'
GROUP BY shot
ORDER BY shot;

-- Latest versions per shot
SELECT file_path, shot, version, status, department, scan_timestamp
FROM s3_tables.metadata_catalog.file_metadata
WHERE project = 'PROD-2026' AND shot = '010'
ORDER BY version DESC;

-- Storage usage by department and status
SELECT department, status, 
       count(*) as file_count,
       sum(file_size_bytes) / (1024*1024*1024) as total_gb
FROM s3_tables.metadata_catalog.file_metadata
WHERE project = 'PROD-2026'
GROUP BY department, status
ORDER BY total_gb DESC;
```

**Talking points**:
- "Production managers get real-time shot status without asking each department"
- "Storage usage visibility enables informed archiving decisions"
- "Note: first Athena query after idle: 3–5 seconds cold start"

---

### Step 5: Creative Asset Reuse via Semantic Search

**Duration**: 5 minutes

**Scenario**: "Find HDRI environments similar to our forest scene"

OpenSearch semantic search:
1. **Keyword**: `"forest" "HDRI" "environment"` → exact matches
2. **Similar search**: Use embedding of `env_forest_hdri_8k.hdr` → find visually/conceptually similar environments
3. **Filter**: `ai_classification = 'HDRI Environment' AND resolution >= '4K'`

**Talking points**:
- "Artists find reusable assets instead of recreating from scratch"
- "Vector search finds conceptually similar assets even with different naming"
- "OpenSearch warm-up: 10–30 seconds after extended idle period"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 90%+ (5 categories) | PoC result; non-standard naming reduces accuracy |
| Processing time | 42–60 seconds/file | Large EXR/DPX may take longer |
| Cost per file | $0.07–$0.15 | Varies by file size (10MB+ = ~$0.15) |
| Shot metadata extraction | 85%+ | Depends on consistent naming conventions |
| Athena query response | 2–3 seconds | After cold start (+3–5s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Asset reuse (avoid re-renders) | 5% render savings × $500K render cost/year | **$25,000 saved** |
| Artist search time | 15 min/day × 30 artists × 50% adoption | **~1,370 hours/year** |
| Production manager reporting | 2 hours/week → 5 min/week | **100 hours/year** |
| Archiving efficiency | 1 week/project → 1 day | **160 hours/year** |

**Conservative annual productivity value**: ~1,630 hours × ¥5,000/hr + $25,000 render savings = **¥8,150,000 + $25,000** (~$79,300)
**Annual solution cost**: ~$2,000 (higher file sizes = higher Bedrock costs)
**Conservative ROI**: ~3,865%

**Assumptions**: 50% adoption, conservative time estimates, modest render reuse rate.

---

## Limitations Relevant to Media/VFX

| Limitation | Impact for Media |
|-----------|-----------------|
| Large file costs | 10MB+ files cost ~$0.15 each for Bedrock classification; VFX projects with millions of EXR frames can accumulate cost |
| Bedrock accuracy on media files | Binary formats (EXR, DPX) classified primarily by filename/path; actual image content analysis limited |
| FPolicy latency (~1–5ms) | Minimal for file saves; test with real-time render pipelines if volumes are shared |
| S3 AP read-only | Cannot auto-move finaled assets to archive storage |
| Lambda memory limits | Very large files (>500MB) may exceed Lambda memory; requires chunked processing |
| Naming convention dependency | Metadata extraction quality depends heavily on consistent file/folder naming |

---

## Customization Points

1. **Classification categories**: Map to studio pipeline stages (previs, layout, animation, lighting, comp, final)
2. **Metadata fields**: Project codes, shot numbers, frame ranges, color spaces
3. **Version tracking**: Configure version extraction patterns for studio naming conventions
4. **Status workflow**: Map file locations/names to production status (WIP/Review/Final/Approved)
5. **Cost management**: Configure FPolicy scope to only trigger on specific directories (avoid processing temp/cache files)

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

*Related config: [`media-vfx.yaml`](../sample-data/industry-configs/media-vfx.yaml)*
*Pair document: [industry-media-vfx-ja.md](./industry-media-vfx-ja.md)*

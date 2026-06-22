# Gaming Demo Scenario: Game Asset Pipeline & QA Report Intelligence

🌐 [日本語](industry-gaming-ja.md) | English

> Automated classification and discovery of game assets (textures, models, audio), build logs, QA reports, and player feedback across studio file shares.

---

## Business Context

### Challenge

Game studios face:

- **Asset management at scale**: Millions of textures, 3D models, audio files, and animation clips stored across project drives with inconsistent naming
- **Build artifact sprawl**: Nightly builds generate hundreds of logs, crash dumps, and performance reports that accumulate without systematic organization
- **QA report fragmentation**: Bug reports, test results, and player feedback scattered across tools and file shares
- **Version confusion**: Multiple versions of the same asset exist with no clear lineage or approved status

### Solution Value

- Game assets classified automatically by type, project, milestone, and quality tier
- "Find all uncompressed textures over 4K resolution in the current milestone" answered instantly
- QA reports and crash logs searchable by build version, severity, and component
- Asset reuse across projects enabled through semantic search

---

## Demo Flow

### Step 1: Place Sample Game Studio Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry gaming --target /vol/game-studio/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `tex_env_forest_ground_01_4k.png` | Texture Asset | 4K ground texture, forest biome |
| `mdl_character_hero_v12.fbx` | 3D Model | Hero character model, version 12 |
| `build-log-v2.4.1-nightly-20260601.log` | Build Log | Nightly build output, 342 warnings |
| `qa-report-sprint42-combat-system.pdf` | QA Report | Sprint 42 combat system test results |
| `audio_sfx_explosion_large_01.wav` | Audio Asset | Sound effect, explosion category |

**Talking points**:
- "Artists and developers keep their existing file-save workflows — no tool migration required"
- "High-performance NFS from FSx handles the throughput game studios need"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: tex_env_forest_ground_01_4k.png
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Asset type: Texture/Environment
   - Resolution: 4096x4096
   - Biome: Forest
   - Element: Ground
   - Compression: None (raw)
   - LOD tier: High
   - Project: Current (inferred)
✅ Classified in 38.7s | Cost: $0.05
```

**Talking points**:
- "AI identifies asset type, resolution, project context, and quality tier"
- "Build logs are parsed for error counts, warning categories, and failure modes"
- "Classification confidence: PoC accuracy; production varies by asset naming conventions"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
-- Check classification results via Athena
SELECT file_path, ai_classification, confidence_score,
       asset_type, resolution, project, milestone
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'gaming'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | asset_type | resolution | project |
|-----------|------------------|:---------:|:----------:|:----------:|:-------:|
| /vol/game-studio/tex_env_forest_ground_01_4k.png | Texture/Environment | 0.96 | Texture | 4096x4096 | ProjectX |
| /vol/game-studio/mdl_character_hero_v12.fbx | 3D Model/Character | 0.94 | Model | - | ProjectX |
| /vol/game-studio/build-log-v2.4.1-nightly-20260601.log | Build Log/Nightly | 0.98 | Log | - | ProjectX |
| /vol/game-studio/qa-report-sprint42-combat-system.pdf | QA Report | 0.95 | Report | - | ProjectX |
| /vol/game-studio/audio_sfx_explosion_large_01.wav | Audio/SFX | 0.93 | Audio | - | ProjectX |

**Talking points**:
- "Five different asset types classified with high confidence"
- "Resolution and quality tier extracted for pipeline optimization"
- "Build version and sprint linkage maintained automatically"

---

### Step 4: Game Studio Queries

**Duration**: 5 minutes

```sql
-- Uncompressed textures above 4K that need optimization
SELECT file_path, resolution, file_size_mb, compression_status
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Texture/Environment'
  AND resolution_x >= 4096
  AND compression_status = 'None'
ORDER BY file_size_mb DESC;

-- Build failures by component in last 7 days
SELECT build_version, error_category, error_count, build_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Build Log/Nightly'
  AND error_count > 0
  AND scan_timestamp > current_date - interval '7' day
ORDER BY error_count DESC;

-- QA reports with critical severity bugs
SELECT file_path, sprint, component, critical_bug_count
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'QA Report'
  AND critical_bug_count > 0
ORDER BY critical_bug_count DESC;
```

**Talking points**:
- "Tech artists can instantly find textures that need compression for target platform"
- "Build engineers identify recurring failure patterns across nightly builds"
- "QA leads track critical bug density by component and sprint"

---

### Step 5: Semantic Search for Asset Reuse

**Duration**: 5 minutes

**Scenario**: "Find explosion-related assets across all projects for reuse"

Using OpenSearch:
1. **Keyword search**: `"explosion" AND "sfx"` → exact audio matches
2. **Semantic search**: "particle effects for large detonation" → finds related VFX, textures, and audio
3. **Combined**: Filter by asset type + semantic similarity score

**Talking points**:
- "Asset reuse across projects saves weeks of artist time per milestone"
- "Semantic search finds related assets even with different naming conventions across teams"
- "OpenSearch Serverless note: first search after extended idle may take 10–30 seconds for OCU warm-up"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 92%+ (5 categories) | PoC result; production varies |
| Processing time | 40 seconds/file | Metadata extraction only; not rendering |
| Cost per file | $0.05–$0.07 | Varies by file type and content |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Asset search time | 20 min/day × 40 artists × 50% adoption | **~730 hours/year** |
| Build log analysis | 30 min/day × 5 build engineers → automated | **~45 hours/year** |
| Asset reuse discovery | 2 days/milestone × 6 milestones → 2 hours | **84 hours saved** |
| QA report aggregation | 1 hour/sprint × 26 sprints → automated | **26 hours saved** |

**Conservative annual productivity value**: ~885 hours × ¥6,000/hr = **¥5,310,000** (~$35,400)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~2,488%

**Assumptions**: 50% adoption, mid-size studio (40 artists, 5 build engineers), no additional value from faster time-to-market.

---

## Limitations Relevant to Gaming

| Limitation | Impact for Gaming |
|-----------|-------------------|
| S3 AP (pipeline reads only) | Cannot auto-convert or compress assets via pipeline |
| No S3 Event Notifications | Cannot trigger build pipeline steps via S3 events |
| Bedrock accuracy varies | Custom asset naming conventions may need prompt tuning |
| Large file sizes | Game assets (100MB+ models) increase Lambda processing time |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Binary file analysis | AI classification works on metadata/filename patterns for binary formats |

---

## Customization Points

1. **Asset categories**: Add studio-specific types (concept art, storyboards, cutscene scripts)
2. **Pipeline integration**: Connect classification to asset pipeline status (WIP, Review, Approved, Published)
3. **Platform tags**: Tag assets by target platform (PC, Console, Mobile) for build filtering
4. **LOD tiers**: Map quality levels to LOD requirements per target hardware

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

*Related: [use-cases/gaming/](../../use-cases/gaming/)*
*Pair document: [industry-gaming-ja.md](./industry-gaming-ja.md)*

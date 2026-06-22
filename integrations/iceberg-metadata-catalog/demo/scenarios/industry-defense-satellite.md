# Defense & Satellite Demo Scenario: Satellite Imagery Metadata & Mission Log Intelligence

🌐 [日本語](industry-defense-satellite-ja.md) | English

> Automated classification and search of satellite imagery metadata, mission logs, and classified document indices across defense and space organization file shares.

---

## Business Context

### Challenge

Defense and satellite organizations face:

- **Imagery metadata overload**: Thousands of satellite captures daily generate metadata files without systematic classification by region, resolution, or purpose
- **Mission log fragmentation**: Telemetry downloads, command logs, and anomaly reports scattered across mission-specific directories
- **Document index complexity**: Multi-classification-level documents require careful tracking of access levels and distribution restrictions
- **Cross-mission correlation**: Finding related observations across different satellite passes and time periods requires manual expertise

### Solution Value

- Satellite imagery metadata classified automatically by region, spectral band, resolution tier, and observation purpose
- "Find all sub-meter resolution captures of coastal region in the last 72 hours" answered via SQL
- Mission logs correlated with satellite health metrics and anomaly events
- Cross-temporal observation patterns discoverable through semantic search

---

## Demo Flow

### Step 1: Place Sample Defense/Satellite Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry defense-satellite --target /vol/satellite-ops/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `img-meta-SAT04-PASS2026060142-COASTAL.json` | Imagery Metadata | Coastal observation metadata, 0.5m resolution |
| `mission-log-SAT04-20260601-telemetry.csv` | Mission Log | Satellite telemetry, 86,400 data points |
| `anomaly-report-SAT04-thermal-20260601.pdf` | Anomaly Report | Thermal subsystem warning |
| `doc-index-classified-REGION-A-2026Q2.json` | Document Index | Classified document registry for region A |
| `orbit-plan-SAT04-20260602-maneuver.pdf` | Orbit Plan | Station-keeping maneuver schedule |

**Talking points**:
- "Satellite ground station writes downlinked data to FSx — FPolicy triggers classification automatically"
- "Metadata-only processing — imagery content stays in secure storage, only metadata is cataloged"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: img-meta-SAT04-PASS2026060142-COASTAL.json
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Imagery Metadata
   - Satellite: SAT-04
   - Pass ID: PASS2026060142
   - Region: Coastal-A
   - Resolution: 0.5m (sub-meter)
   - Spectral: Multispectral (8-band)
   - Cloud cover: 12%
   - Observation type: Maritime surveillance
   - Classification level: Restricted
✅ Classified in 39.2s | Cost: $0.05
```

**Talking points**:
- "Only metadata is processed — actual imagery stays in its original secure storage"
- "AI identifies region, resolution, spectral characteristics, and observation purpose"
- "Classification confidence: PoC accuracy; production varies by metadata format"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       satellite_id, region, resolution, observation_type
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'defense-satellite'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | satellite_id | region | resolution |
|-----------|------------------|:---------:|:------------:|:------:|:----------:|
| /vol/satellite-ops/img-meta-SAT04-PASS2026060142-COASTAL.json | Imagery Meta/Maritime | 0.96 | SAT-04 | Coastal-A | 0.5m |
| /vol/satellite-ops/mission-log-SAT04-20260601-telemetry.csv | Mission Log/Telemetry | 0.98 | SAT-04 | - | - |
| /vol/satellite-ops/anomaly-report-SAT04-thermal-20260601.pdf | Anomaly Report | 0.95 | SAT-04 | - | - |
| /vol/satellite-ops/doc-index-classified-REGION-A-2026Q2.json | Document Index | 0.97 | - | Region-A | - |
| /vol/satellite-ops/orbit-plan-SAT04-20260602-maneuver.pdf | Orbit Plan/Maneuver | 0.94 | SAT-04 | - | - |

---

### Step 4: Satellite Operations Queries

**Duration**: 5 minutes

```sql
-- Recent sub-meter imagery by region
SELECT satellite_id, pass_id, region, resolution, cloud_cover, capture_time
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Imagery Meta%'
  AND resolution_m <= 1.0
  AND capture_time > current_timestamp - interval '72' hour
ORDER BY capture_time DESC;

-- Satellite health anomalies
SELECT satellite_id, anomaly_type, severity, subsystem, event_time
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Anomaly Report'
  AND scan_timestamp > current_date - interval '30' day
ORDER BY severity DESC, event_time DESC;

-- Observation coverage by region and time
SELECT region, COUNT(*) as passes, MIN(cloud_cover) as best_cloud_cover,
       MAX(capture_time) as latest_capture
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Imagery Meta%'
GROUP BY region
ORDER BY latest_capture DESC;
```

---

### Step 5: Semantic Search for Cross-Temporal Analysis

**Duration**: 5 minutes

**Scenario**: "Find historical observations of the same coastal area for change detection"

Using OpenSearch:
1. **Keyword search**: `"Coastal-A" AND "maritime"` → exact region matches
2. **Semantic search**: "vessel movement patterns in restricted maritime zone during nighttime" → finds related observations
3. **Combined**: Filter by region + time range + resolution + semantic similarity

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 95%+ (5 categories) | PoC result; production varies |
| Processing time | 39 seconds/file | Metadata-only processing |
| Cost per file | $0.05 | JSON metadata files |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Imagery search | 30 min/search × 500 searches/year → 3 min | **225 hours saved** |
| Mission anomaly correlation | 2 hours/event × 50 events/year → 15 min | **88 hours saved** |
| Cross-temporal analysis | 4 hours/analysis × 100 analyses/year → 30 min | **350 hours saved** |
| Coverage reporting | 4 hours/week manual → automated | **192 hours saved** |

**Conservative annual productivity value**: ~855 hours × ¥7,000/hr = **¥5,985,000** (~$39,900)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~3,274%

---

## Limitations Relevant to Defense & Satellite

| Limitation | Impact for Defense |
|-----------|-------------------|
| S3 AP (pipeline reads only) | Cannot trigger tasking requests via pipeline |
| Classification levels | Metadata catalog must be deployed within appropriate security boundary |
| Lambda ephemeral access | File content passes through Lambda memory — verify against security requirements |
| ITAR/EAR considerations | Ensure no controlled technical data flows outside authorized environment |
| Imagery content | Only metadata processed — actual imagery analysis requires specialized tools |
| Air-gapped environments | Solution requires network access; verify connectivity requirements |
| Audit requirements | All access must be logged per security compliance requirements |

- **GovCloud requirement**: ITAR/EAR-controlled workloads may require AWS GovCloud (US) regions. This solution has been validated in commercial regions (ap-northeast-1) only. GovCloud validation is separate — verify Bedrock model availability, S3 Tables support, and FedRAMP authorization status before deployment.

---

## Customization Points

1. **Region taxonomy**: Configure observation regions per operational requirements
2. **Classification levels**: Map access restrictions to Lake Formation policies
3. **Satellite constellation**: Add sensors and spectral bands per satellite platform
4. **Mission types**: Configure observation purpose categories per operational doctrine

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

*Related: [use-cases/defense-satellite/](../../use-cases/defense-satellite/)*
*Pair document: [industry-defense-satellite-ja.md](./industry-defense-satellite-ja.md)*

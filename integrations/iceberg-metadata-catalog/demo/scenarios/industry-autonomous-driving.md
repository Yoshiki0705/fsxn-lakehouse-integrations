# Autonomous Driving & Mobility Demo Scenario: Sensor Data & Driving Log Intelligence

🌐 [日本語](industry-autonomous-driving-ja.md) | English

> Automated classification and search of sensor data, driving logs, annotation files, and calibration data across autonomous vehicle development file shares.

---

## Business Context

### Challenge

Autonomous driving teams face:

- **Massive data volumes**: Each test vehicle generates terabytes of LiDAR, camera, radar, and IMU data per day with inconsistent organization
- **Annotation tracking gaps**: Millions of labeled frames scattered across annotation team outputs with no unified search
- **Calibration file chaos**: Sensor calibration files and vehicle configuration versions stored without systematic tracking
- **Scenario discovery difficulty**: Finding specific driving scenarios (rain, highway merge, pedestrian crossing) requires manual log review

### Solution Value

- Sensor data and driving logs classified automatically by scenario type, weather, road type, and event category
- "Find all rainy highway merge scenarios with pedestrian near-miss" answered in seconds via SQL
- Annotation completeness tracked per scenario and sensor modality
- Calibration file versions linked to test sessions for reproducibility

---

## Demo Flow

### Step 1: Place Sample Autonomous Driving Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry autonomous-driving --target /vol/av-data/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `drive-log-VH042-20260601-route7.json` | Driving Log | Vehicle 042, route 7, 847 events |
| `lidar-pointcloud-VH042-frame08421.pcd` | Sensor Data | LiDAR point cloud, intersection scene |
| `annotation-VH042-frame08421-3dbox.json` | Annotation File | 3D bounding boxes, 23 objects labeled |
| `calibration-VH042-20260601-sensors.yaml` | Calibration Data | Multi-sensor calibration parameters |
| `scenario-report-nearmiss-PED-20260601.pdf` | Scenario Report | Pedestrian near-miss event analysis |

**Talking points**:
- "High-performance NFS from FSx handles the throughput AV data pipelines require"
- "FPolicy triggers without adding latency to the data recording pipeline"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: drive-log-VH042-20260601-route7.json
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Driving Log
   - Vehicle ID: VH042
   - Route: Route 7 (Urban arterial)
   - Date: 2026-06-01
   - Duration: 2h 14min
   - Weather: Rain (light)
   - Events: 847 (12 safety-critical)
   - Scenarios: Highway merge, pedestrian crossing, construction zone
✅ Classified in 44.3s | Cost: $0.07
```

**Talking points**:
- "AI extracts scenario types, weather conditions, and safety-critical events from log metadata"
- "Point cloud files classified by scene type using filename patterns and associated metadata"
- "Classification confidence: PoC accuracy; production varies by log format and sensor configuration"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       vehicle_id, scenario_type, weather, safety_events
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'autonomous-driving'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | vehicle_id | scenario_type | weather |
|-----------|------------------|:---------:|:----------:|:-------------:|:-------:|
| /vol/av-data/drive-log-VH042-20260601-route7.json | Driving Log/Urban | 0.95 | VH042 | Multi-scenario | Rain |
| /vol/av-data/lidar-pointcloud-VH042-frame08421.pcd | Sensor/LiDAR | 0.97 | VH042 | Intersection | Rain |
| /vol/av-data/annotation-VH042-frame08421-3dbox.json | Annotation/3D Box | 0.98 | VH042 | Intersection | - |
| /vol/av-data/calibration-VH042-20260601-sensors.yaml | Calibration/Multi-Sensor | 0.99 | VH042 | - | - |
| /vol/av-data/scenario-report-nearmiss-PED-20260601.pdf | Scenario Report/Safety | 0.94 | VH042 | Pedestrian | Rain |

**Talking points**:
- "Driving scenarios extracted and categorized for training data selection"
- "Weather conditions tagged for scenario diversity analysis"
- "Safety-critical events flagged for priority review"

---

### Step 4: Autonomous Driving Queries

**Duration**: 5 minutes

```sql
-- Find rainy scenarios with pedestrian events for model training
SELECT file_path, vehicle_id, scenario_type, safety_events, duration_min
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Driving Log%'
  AND weather = 'Rain'
  AND scenario_type LIKE '%pedestrian%'
ORDER BY safety_events DESC;

-- Annotation completeness by scenario type
SELECT scenario_type, 
       COUNT(CASE WHEN ai_classification LIKE 'Annotation%' THEN 1 END) as annotated,
       COUNT(CASE WHEN ai_classification LIKE 'Sensor%' THEN 1 END) as total_frames
FROM s3_tables.metadata_catalog.file_metadata
WHERE vehicle_id = 'VH042'
GROUP BY scenario_type;

-- Calibration files by vehicle and date for reproducibility
SELECT file_path, vehicle_id, sensor_config_version, calibration_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Calibration/Multi-Sensor'
ORDER BY vehicle_id, calibration_date DESC;
```

**Talking points**:
- "ML engineers find specific scenarios for model training in seconds instead of hours"
- "Annotation teams track completeness across the dataset"
- "Test reproducibility ensured through calibration version tracking"

---

### Step 5: Semantic Search for Scenario Mining

**Duration**: 5 minutes

**Scenario**: "Find similar near-miss events for safety analysis"

Using OpenSearch:
1. **Keyword search**: `"near-miss" AND "pedestrian"` → exact event matches
2. **Semantic search**: "vehicle approaching crosswalk with occluded pedestrian in rain" → finds similar scenarios
3. **Combined**: Filter by weather + scenario type + semantic similarity

**Talking points**:
- "Scenario mining across millions of recorded miles becomes searchable"
- "Semantic search finds similar safety events even with different logging formats"
- "OpenSearch Serverless note: first search after extended idle may take 10–30 seconds for OCU warm-up"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 94%+ (5 categories) | PoC result; production varies |
| Processing time | 44 seconds/file | Metadata extraction; not full point cloud processing |
| Cost per file | $0.05–$0.07 | Log/metadata files; large binary files by filename pattern |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Scenario search for training | 2 hours/search × 200 searches/year → 5 min | **393 hours saved** |
| Calibration tracking | 30 min/session × 500 sessions/year → automated | **240 hours saved** |
| Safety event investigation | 1 hour/event × 100 events/year → 10 min | **83 hours saved** |
| Annotation tracking | 2 hours/week manual → automated | **96 hours saved** |

**Conservative annual productivity value**: ~812 hours × ¥7,000/hr = **¥5,684,000** (~$37,900)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~2,671%

**Assumptions**: 50% adoption, single AV development team, no additional value from faster model iteration or reduced safety review cycles.

---

## Limitations Relevant to Autonomous Driving

| Limitation | Impact for AV |
|-----------|---------------|
| S3 AP (pipeline reads only) | Cannot trigger reprocessing or re-annotation via pipeline |
| No S3 Event Notifications | Cannot trigger ML training pipelines via S3 events |
| Large binary files | Point clouds (100MB+) processed by metadata/filename; not full content analysis |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Real-time constraints | Not designed for real-time vehicle data; batch/near-real-time metadata cataloging |
| Data sovereignty | Driving data may have geographic restrictions; verify cross-region replication policies |

- **Sensor data formats**: LiDAR point clouds (.pcd, .las), radar data, and raw camera feeds cannot be directly processed by Bedrock Claude. Extract metadata (timestamp, sensor ID, GPS coordinates) via format-specific parsers before classification. Image frames (JPEG/PNG) extracted from video can be classified. See [AI Prompt Guide](ai-prompt-customization-guide.md) multimodal matrix.

---

## Customization Points

1. **Scenario taxonomy**: Configure scenario types matching internal ODD (Operational Design Domain) definitions
2. **Sensor modalities**: Add company-specific sensor types (thermal, ultrasonic, V2X messages)
3. **Safety classification**: Map event severity levels to internal safety assessment frameworks
4. **Annotation standards**: Track annotation format versions and labeling guideline compliance

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

*Related: [use-cases/autonomous-driving/](../../use-cases/autonomous-driving/)*
*Pair document: [industry-autonomous-driving-ja.md](./industry-autonomous-driving-ja.md)*

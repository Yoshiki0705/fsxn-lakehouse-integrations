# Smart City & Telecom Demo Scenario: IoT Sensor & Urban Data Intelligence

🌐 [日本語](industry-smart-city-ja.md) | English

> Automated classification and search of IoT sensor logs, traffic camera images, citizen complaint forms, and urban planning documents across smart city file shares.

---

## Business Context

### Challenge

Smart city operators face:

- **IoT data fragmentation**: Millions of sensor readings from traffic, environmental, and infrastructure monitors stored without unified classification
- **Incident documentation gaps**: Traffic camera captures, citizen reports, and maintenance records disconnected from each other
- **Urban planning silos**: Zoning documents, environmental assessments, and infrastructure plans scattered across departments
- **Cross-agency coordination**: Finding related data across transportation, environment, and public works requires inter-department requests

### Solution Value

- IoT data and urban documents classified automatically by sensor type, location, and event category
- "Find all traffic anomaly events in district 7 during morning rush hour" answered via SQL
- Citizen complaints linked to geographic areas and infrastructure maintenance records
- Cross-departmental document discovery enabled through semantic search

---

## Demo Flow

### Step 1: Place Sample Smart City Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry smart-city --target /vol/smart-city/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `iot-traffic-sensor-D7-INT042-20260601.json` | IoT Sensor Log | Traffic flow data, intersection 042 |
| `camera-capture-D7-INT042-anomaly-0842.jpg` | Traffic Camera | Anomaly detection capture, vehicle stopped |
| `citizen-complaint-CC-2026-08842.pdf` | Citizen Complaint | Road surface damage report, district 7 |
| `infrastructure-plan-water-D7-2026.pdf` | Infrastructure Plan | Water main replacement plan |
| `env-sensor-air-quality-D7-20260601.csv` | Environmental Data | Air quality readings, 1,440 measurements |

**Talking points**:
- "IoT gateways write sensor data to FSx — FPolicy triggers classification without impacting data collection"
- "Citizen-submitted documents and sensor data processed through the same pipeline"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: iot-traffic-sensor-D7-INT042-20260601.json
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: IoT Sensor/Traffic
   - District: 7
   - Intersection: INT-042
   - Date: 2026-06-01
   - Anomalies: 3 (vehicle count spike)
   - Peak hour: 08:15-08:45
   - Sensor health: Normal
   - Data completeness: 99.8%
✅ Classified in 38.5s | Cost: $0.05
```

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       district, location, event_type, data_quality
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'smart-city'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | district | location | event_type |
|-----------|------------------|:---------:|:--------:|:--------:|:----------:|
| /vol/smart-city/iot-traffic-sensor-D7-INT042-20260601.json | IoT/Traffic | 0.97 | D7 | INT-042 | Anomaly |
| /vol/smart-city/camera-capture-D7-INT042-anomaly-0842.jpg | Camera/Traffic Anomaly | 0.93 | D7 | INT-042 | Vehicle Stop |
| /vol/smart-city/citizen-complaint-CC-2026-08842.pdf | Citizen Complaint | 0.95 | D7 | Road-7A | Damage |
| /vol/smart-city/infrastructure-plan-water-D7-2026.pdf | Infrastructure Plan | 0.96 | D7 | - | Planned |
| /vol/smart-city/env-sensor-air-quality-D7-20260601.csv | IoT/Environmental | 0.98 | D7 | Station-A7 | Normal |

---

### Step 4: Smart City Queries

**Duration**: 5 minutes

```sql
-- Traffic anomalies by district and time period
SELECT district, location, event_type, event_time, anomaly_count
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'IoT/Traffic'
  AND anomaly_count > 0
  AND scan_timestamp > current_date - interval '7' day
ORDER BY anomaly_count DESC;

-- Citizen complaints correlated with infrastructure issues
SELECT cc.district, cc.complaint_type, ip.plan_type, ip.status
FROM s3_tables.metadata_catalog.file_metadata cc
JOIN s3_tables.metadata_catalog.file_metadata ip
  ON cc.district = ip.district
WHERE cc.ai_classification = 'Citizen Complaint'
  AND ip.ai_classification = 'Infrastructure Plan';

-- Environmental sensor alerts
SELECT location, measurement_type, max_value, alert_threshold, alert_time
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'IoT/Environmental'
  AND alert_triggered = true
ORDER BY alert_time DESC;
```

---

### Step 5: Semantic Search for Urban Issue Investigation

**Duration**: 5 minutes

**Scenario**: "Find all data related to traffic congestion in district 7"

Using OpenSearch:
1. **Keyword search**: `"district 7" AND "traffic" AND "congestion"` → exact matches
2. **Semantic search**: "road construction causing vehicle backup near school zone" → finds related complaints, camera captures, and plans
3. **Combined**: Filter by district + date range + semantic relevance

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 94%+ (5 categories) | PoC result; production varies |
| Processing time | 38 seconds/file | Structured IoT data processes faster |
| Cost per file | $0.05 | Structured sensor data |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Cross-department data search | 30 min/request × 500 requests/year → 3 min | **225 hours saved** |
| Citizen complaint routing | 15 min/complaint × 2,000/year → automated | **475 hours saved** |
| Infrastructure planning | 2 days/plan × 12 plans/year → 4 hours | **176 hours saved** |
| Sensor anomaly investigation | 20 min/event × 500 events/year → 5 min | **125 hours saved** |

**Conservative annual productivity value**: ~1,001 hours × ¥4,500/hr = **¥4,505,000** (~$30,000)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~2,193%

---

## Limitations Relevant to Smart City

| Limitation | Impact for Smart City |
|-----------|----------------------|
| S3 AP read-only | Cannot trigger automated responses to sensor alerts via pipeline |
| Real-time streaming | Not designed for real-time IoT streaming; batch metadata cataloging |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Data privacy | Citizen complaint PII must be handled per municipal privacy regulations |
| Camera footage | Full video not processed; still captures and metadata only |
| Multi-agency governance | Data sharing policies between agencies must be configured per local regulations |

---

## Customization Points

1. **Sensor types**: Configure for city-specific IoT infrastructure (traffic, environment, water, energy)
2. **Geographic zones**: Map districts and zones to municipal administrative boundaries
3. **Complaint categories**: Align with citizen service request taxonomy
4. **Alert thresholds**: Configure per sensor type and regulatory requirements

---

*Related: [use-cases/smart-city/](../../use-cases/smart-city/)*
*Pair document: [industry-smart-city-ja.md](./industry-smart-city-ja.md)*

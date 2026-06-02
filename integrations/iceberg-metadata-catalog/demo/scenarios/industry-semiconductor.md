# Semiconductor Demo Scenario: Wafer Map & Process Log Intelligence

🌐 [日本語](industry-semiconductor-ja.md) | English

> Automated classification and search of wafer maps, process logs, defect images, and design rule check reports across semiconductor fab file shares.

---

## Business Context

### Challenge

Semiconductor manufacturers face:

- **Wafer data explosion**: Each lot generates hundreds of wafer maps, metrology reports, and process logs with complex naming hierarchies
- **Defect tracking fragmentation**: SEM/optical defect images scattered across inspection tools with no unified classification
- **Process recipe management**: Recipe versions, split conditions, and excursion logs stored without systematic correlation
- **Yield analysis delays**: Finding root cause data across multiple process steps requires deep expertise and manual search

### Solution Value

- Wafer data classified automatically by process step, lot, tool, and quality status
- "Find all wafer maps with yield below 85% at lithography step in the last week" answered via SQL
- Defect images classified by type, size, and process layer with automatic kill-probability estimation
- Process excursions linked to affected lots and downstream impact assessment

---

## Demo Flow

### Step 1: Place Sample Semiconductor Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry semiconductor --target /vol/fab-data/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `wafermap-LOT2026A042-W08-litho.klarf` | Wafer Map | Lithography defect map, wafer 08 |
| `process-log-LOT2026A042-etch-step7.csv` | Process Log | Etch chamber log, 1,247 parameters |
| `defect-image-W08-D0042-sem50k.tiff` | Defect Image | SEM image at 50,000x, particle defect |
| `drc-report-CHIP-A42-rev3.pdf` | DRC Report | Design rule check, 3 violations |
| `excursion-log-TOOL-ETCH04-20260601.pdf` | Excursion Log | Process excursion, temperature drift |

**Talking points**:
- "FSx high-performance NFS handles fab data throughput requirements"
- "FPolicy integrates without impacting tool-to-host communication latency"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: wafermap-LOT2026A042-W08-litho.klarf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Wafer Map/Defect
   - Lot ID: LOT2026A042
   - Wafer: 08
   - Process step: Lithography
   - Defect count: 142
   - Yield estimate: 82.3%
   - Kill ratio: 0.31
   - Tool: LITHO-ASML04
✅ Classified in 41.5s | Cost: $0.07
```

**Talking points**:
- "AI identifies lot, process step, tool, defect count, and yield estimate from wafer map metadata"
- "Defect images classified by type (particle, scratch, pattern) and layer"
- "Classification confidence: PoC accuracy; production varies by KLARF format version"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       lot_id, wafer, process_step, yield_estimate
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'semiconductor'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | lot_id | process_step | yield_estimate |
|-----------|------------------|:---------:|:------:|:------------:|:--------------:|
| /vol/fab-data/wafermap-LOT2026A042-W08-litho.klarf | Wafer Map/Defect | 0.96 | LOT2026A042 | Lithography | 82.3% |
| /vol/fab-data/process-log-LOT2026A042-etch-step7.csv | Process Log/Etch | 0.98 | LOT2026A042 | Etch | - |
| /vol/fab-data/defect-image-W08-D0042-sem50k.tiff | Defect Image/Particle | 0.91 | LOT2026A042 | Lithography | - |
| /vol/fab-data/drc-report-CHIP-A42-rev3.pdf | DRC Report | 0.97 | - | Design | - |
| /vol/fab-data/excursion-log-TOOL-ETCH04-20260601.pdf | Excursion Log | 0.95 | LOT2026A042 | Etch | - |

**Talking points**:
- "Lot-level traceability maintained across wafer maps, process logs, and defect images"
- "Yield estimates extracted for real-time monitoring"
- "Excursion events linked to affected lots"

---

### Step 4: Semiconductor Fab Queries

**Duration**: 5 minutes

```sql
-- Low-yield wafers by process step
SELECT lot_id, wafer, process_step, yield_estimate, defect_count, tool_id
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Wafer Map/Defect'
  AND yield_estimate < 85.0
  AND scan_timestamp > current_date - interval '7' day
ORDER BY yield_estimate ASC;

-- Defect density trending by tool
SELECT tool_id, process_step, AVG(defect_count) as avg_defects,
       COUNT(*) as wafer_count
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Wafer Map/Defect'
  AND scan_timestamp > current_date - interval '30' day
GROUP BY tool_id, process_step
ORDER BY avg_defects DESC;

-- Excursion events and affected lots
SELECT file_path, tool_id, excursion_type, affected_lots, event_time
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Excursion Log'
  AND scan_timestamp > current_date - interval '7' day
ORDER BY event_time DESC;
```

**Talking points**:
- "Yield engineers identify problematic tools and process steps instantly"
- "Defect trending reveals systematic issues before they impact full lots"
- "Excursion impact assessment automated for faster containment decisions"

---

### Step 5: Semantic Search for Root Cause Analysis

**Duration**: 5 minutes

**Scenario**: "Find similar defect patterns for yield excursion root cause"

Using OpenSearch:
1. **Keyword search**: `"particle" AND "lithography" AND "ASML04"` → exact tool/defect matches
2. **Semantic search**: "random particle contamination after chamber maintenance on litho tool" → finds similar past events
3. **Combined**: Filter by tool + defect type + time range + semantic similarity

**Talking points**:
- "Root cause investigation accelerated by finding similar historical excursions"
- "Semantic search identifies related patterns across different tool types and nodes"
- "OpenSearch Serverless note: first search after extended idle may take 10–30 seconds for OCU warm-up"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 94%+ (5 categories) | PoC result; production varies |
| Processing time | 41 seconds/file | Metadata extraction from map files |
| Cost per file | $0.05–$0.07 | KLARF/map files; SEM images by metadata |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Yield excursion investigation | 4 hours/excursion × 50 excursions/year → 1 hour | **150 hours saved** |
| Defect classification | 10 min/wafer × 10,000 wafers/year → automated | **1,633 hours saved** |
| Process correlation analysis | 2 days/analysis × 24 analyses/year → 4 hours | **368 hours saved** |
| Yield improvement | 0.5% yield gain × ¥100M/year revenue impact | **¥500K incremental** |

**Conservative annual productivity value**: ~2,151 hours × ¥8,000/hr = **¥17,208,000** (~$114,700)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~8,384%

**Assumptions**: 50% adoption, single fab line, yield improvement value stated separately.

---

## Limitations Relevant to Semiconductor

| Limitation | Impact for Semiconductor |
|-----------|--------------------------|
| S3 AP (pipeline reads only) | Cannot trigger recipe adjustments or lot holds via pipeline |
| No S3 Event Notifications | Cannot trigger MES actions via S3 events |
| Proprietary formats | KLARF, SINF formats processed at metadata level; not full spatial analysis |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Fab security | Ensure pipeline does not transmit process IP outside controlled environment |
| Real-time requirements | Not suitable for real-time SPC; designed for batch metadata cataloging |
| Tool integration | FPolicy on FSx supplements but does not replace tool-native data systems |

---

## Customization Points

1. **Process flow**: Configure steps matching specific technology node (7nm, 5nm, 3nm)
2. **Defect taxonomy**: Map to company-specific defect classification system
3. **Tool groups**: Group tools by type and bay for aggregated analysis
4. **Yield targets**: Set per-step yield thresholds matching product specifications

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

*Related: [use-cases/semiconductor/](../../use-cases/semiconductor/)*
*Pair document: [industry-semiconductor-ja.md](./industry-semiconductor-ja.md)*

# Energy & Utilities Demo Scenario: Inspection Report & SCADA Log Intelligence

🌐 [日本語](industry-energy-ja.md) | English

> Automated classification and search of inspection reports, SCADA logs, turbine/equipment photos, and compliance filings across energy utility file shares.

---

## Business Context

### Challenge

Energy and utility companies face:

- **Inspection document sprawl**: Thousands of field inspection reports, maintenance logs, and safety assessments scattered across regional operations centers
- **SCADA data silos**: Operational logs from distributed control systems stored without correlation to maintenance events
- **Equipment photo chaos**: Drone and field inspection images stored without systematic tagging of equipment ID, condition, or defect type
- **Compliance reporting burden**: Regulatory filings (NERC, FERC, local equivalents) require manual assembly from multiple sources

### Solution Value

- Inspection reports classified automatically by equipment type, condition severity, and required action
- "Find all turbine inspections with critical defects in the last quarter" answered via SQL
- Equipment photos linked to asset IDs with automatic defect detection and severity rating
- Compliance filings tracked with submission deadlines and completeness status

---

## Demo Flow

### Step 1: Place Sample Energy Documents on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry energy --target /vol/energy-ops/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `inspection-WTG042-blade-20260601.pdf` | Inspection Report | Wind turbine blade inspection, minor crack |
| `scada-log-substation-A7-20260601.csv` | SCADA Log | Substation operational data, 86,400 records |
| `drone-photo-WTG042-blade3-defect.jpg` | Equipment Photo | Drone inspection image, blade defect |
| `compliance-filing-NERC-CIP-Q2-2026.pdf` | Compliance Filing | NERC CIP quarterly submission |
| `maintenance-wo-WTG042-20260605.pdf` | Work Order | Corrective maintenance, blade repair |

**Talking points**:
- "Field technicians upload inspection reports from tablets — pipeline triggers automatically"
- "SCADA exports and drone imagery processed through the same pipeline"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: inspection-WTG042-blade-20260601.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Inspection Report/Wind Turbine
   - Equipment ID: WTG-042
   - Component: Blade
   - Condition: Defect detected (minor crack)
   - Severity: Medium
   - Action required: Scheduled maintenance
   - Next inspection: 90 days
   - Compliance tag: IEC 61400
✅ Classified in 42.8s | Cost: $0.07
```

**Talking points**:
- "AI identifies equipment, component, defect type, and required action automatically"
- "Drone photos analyzed for defect indicators and condition assessment"
- "Classification confidence: PoC accuracy; production varies by report format and image quality"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       equipment_id, component, severity, action_required
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'energy'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | equipment_id | component | severity |
|-----------|------------------|:---------:|:------------:|:---------:|:--------:|
| /vol/energy-ops/inspection-WTG042-blade-20260601.pdf | Inspection/Wind Turbine | 0.95 | WTG-042 | Blade | Medium |
| /vol/energy-ops/scada-log-substation-A7-20260601.csv | SCADA Log/Substation | 0.98 | SUB-A7 | - | - |
| /vol/energy-ops/drone-photo-WTG042-blade3-defect.jpg | Equipment Photo/Defect | 0.92 | WTG-042 | Blade 3 | Medium |
| /vol/energy-ops/compliance-filing-NERC-CIP-Q2-2026.pdf | Compliance Filing/NERC | 0.96 | - | - | - |
| /vol/energy-ops/maintenance-wo-WTG042-20260605.pdf | Work Order/Corrective | 0.94 | WTG-042 | Blade | - |

**Talking points**:
- "Equipment-level document linkage maintained across inspections, photos, and work orders"
- "Defect severity from inspection report corroborated by drone photo analysis"
- "Compliance filings tracked with deadline awareness"

---

### Step 4: Energy Operations Queries

**Duration**: 5 minutes

```sql
-- Critical equipment defects requiring immediate action
SELECT equipment_id, component, severity, action_required, inspection_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Inspection%'
  AND severity IN ('High', 'Critical')
  AND action_required != 'Completed'
ORDER BY severity DESC, inspection_date ASC;

-- SCADA anomaly events correlated with inspection findings
SELECT s.equipment_id, s.anomaly_type, s.event_time, i.severity
FROM s3_tables.metadata_catalog.file_metadata s
JOIN s3_tables.metadata_catalog.file_metadata i
  ON s.equipment_id = i.equipment_id
WHERE s.ai_classification LIKE 'SCADA%' AND i.ai_classification LIKE 'Inspection%';

-- Compliance filing status by regulation
SELECT regulation, filing_period, status, deadline, days_until_deadline
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Compliance Filing%'
ORDER BY deadline ASC;
```

**Talking points**:
- "Operations team prioritizes maintenance based on defect severity"
- "SCADA data correlated with physical inspections for predictive maintenance"
- "Compliance team tracks filing deadlines across regulatory frameworks"

---

### Step 5: Semantic Search for Equipment History

**Duration**: 5 minutes

**Scenario**: "Find all historical issues related to WTG-042 blade degradation"

Using OpenSearch:
1. **Keyword search**: `"WTG-042" AND "blade"` → exact equipment matches
2. **Semantic search**: "wind turbine leading edge erosion progressive deterioration" → finds similar defect patterns
3. **Combined**: Filter by equipment type + severity + semantic similarity

**Talking points**:
- "Complete equipment history assembled in seconds for maintenance planning"
- "Semantic search finds similar defect patterns across the fleet"
- "OpenSearch Serverless note: first search after extended idle may take 10–30 seconds for OCU warm-up"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 93%+ (5 categories) | PoC result; production varies |
| Processing time | 42 seconds/file | Single file; batch depends on concurrency |
| Cost per file | $0.05–$0.07 | Drone photos: ~$0.05 |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Inspection report retrieval | 20 min/search × 500 searches/year → 2 min | **150 hours saved** |
| Compliance filing assembly | 5 days/quarter → 1 day × 4 filings/year | **128 hours saved** |
| Equipment history lookup | 30 min/lookup × 300 lookups/year → 3 min | **135 hours saved** |
| Predictive maintenance savings | 2 prevented failures/year × ¥5M avg. cost | **¥10M cost avoidance** |

**Conservative annual productivity value**: ~413 hours × ¥5,000/hr = **¥2,065,000** (~$13,800)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~909% (excluding failure prevention)

**Assumptions**: 50% adoption, single wind farm or substation district, failure prevention value stated separately.

---

## Limitations Relevant to Energy

| Limitation | Impact for Energy |
|-----------|-------------------|
| S3 AP read-only | Cannot trigger work order creation via pipeline |
| No S3 Event Notifications | Cannot trigger maintenance workflows via S3 events |
| Bedrock accuracy varies | Technical inspection terminology may need domain-specific prompt tuning |
| SCADA data volume | Large SCADA exports processed at summary level; not real-time streaming |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Safety-critical decisions | AI classification is informational; does not replace qualified inspector judgment |
| OT/IT separation | Ensure FPolicy does not impact operational technology network performance |

---

## Customization Points

1. **Equipment taxonomy**: Configure asset hierarchy matching CMMS (Computerized Maintenance Management System)
2. **Defect codes**: Map AI classifications to standard defect coding systems
3. **Compliance frameworks**: Configure for NERC CIP, FERC, local regulations as applicable
4. **Severity thresholds**: Align defect severity with company risk matrices

---

*Related: [use-cases/energy/](../../use-cases/energy/)*
*Pair document: [industry-energy-ja.md](./industry-energy-ja.md)*

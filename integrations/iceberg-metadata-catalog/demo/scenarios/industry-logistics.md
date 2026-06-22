# Logistics & Supply Chain Demo Scenario: Shipping Document & Delivery Proof Intelligence

🌐 [日本語](industry-logistics-ja.md) | English

> Automated classification and search of shipping documents, delivery photos, customs forms, and tracking logs across logistics file shares.

---

## Business Context

### Challenge

Logistics companies face:

- **Document volume explosion**: Thousands of bills of lading, customs declarations, delivery receipts, and invoices generated daily across regional offices
- **Delivery proof fragmentation**: Driver-captured photos and signatures stored inconsistently across mobile uploads and office shares
- **Customs compliance delays**: Finding specific trade documents for customs audits requires searching across multiple systems
- **Shipment visibility gaps**: Tracking logs and exception reports scattered with no unified search capability

### Solution Value

- Shipping documents classified automatically by type, route, carrier, and status upon upload
- "Find all customs declarations pending approval for Japan-origin shipments" answered via SQL
- Delivery proof photos linked to shipment IDs with automatic damage detection flagging
- Exception reports and delay patterns searchable across historical data

---

## Demo Flow

### Step 1: Place Sample Logistics Documents on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry logistics --target /vol/logistics-ops/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `bol-SHP2026060142-JPNLAX.pdf` | Bill of Lading | Japan to LA, container MSKU7234561 |
| `customs-decl-IMP-2026-08821.pdf` | Customs Declaration | Import declaration, HS code 8471.30 |
| `delivery-photo-DEL88421-front.jpg` | Delivery Photo | Proof of delivery, customer signature |
| `tracking-log-SHP2026060142.csv` | Tracking Log | GPS waypoints, 847 entries |
| `exception-report-20260601.pdf` | Exception Report | Daily delay and damage summary |

**Talking points**:
- "Drivers upload delivery photos from mobile — pipeline triggers on file arrival automatically"
- "Regional offices use SMB shares; headquarters uses NFS — both trigger FPolicy"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: bol-SHP2026060142-JPNLAX.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Bill of Lading
   - Shipment ID: SHP2026060142
   - Route: Tokyo → Los Angeles
   - Container: MSKU7234561
   - Carrier: Ocean Line Co.
   - Status: In Transit
   - Weight: 18,450 kg
✅ Classified in 42.1s | Cost: $0.07
```

**Talking points**:
- "AI extracts shipment ID, route, carrier, and container details automatically"
- "Delivery photos analyzed for damage indicators and signature presence"
- "Classification confidence: PoC accuracy; production varies by document quality and language"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       shipment_id, route, carrier, status
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'logistics'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | shipment_id | route | status |
|-----------|------------------|:---------:|:-----------:|:-----:|:------:|
| /vol/logistics-ops/bol-SHP2026060142-JPNLAX.pdf | Bill of Lading | 0.96 | SHP2026060142 | TYO→LAX | In Transit |
| /vol/logistics-ops/customs-decl-IMP-2026-08821.pdf | Customs Declaration | 0.95 | SHP2026060142 | TYO→LAX | Pending |
| /vol/logistics-ops/delivery-photo-DEL88421-front.jpg | Delivery Proof/Photo | 0.92 | DEL88421 | - | Delivered |
| /vol/logistics-ops/tracking-log-SHP2026060142.csv | Tracking Log | 0.98 | SHP2026060142 | TYO→LAX | In Transit |
| /vol/logistics-ops/exception-report-20260601.pdf | Exception Report | 0.94 | - | Multiple | - |

**Talking points**:
- "Documents linked to shipment IDs automatically for end-to-end visibility"
- "Delivery photos confirmed for signature presence"
- "All five document types classified with high accuracy"

---

### Step 4: Logistics Operations Queries

**Duration**: 5 minutes

```sql
-- Pending customs declarations by origin country
SELECT file_path, shipment_id, origin_country, hs_code, submission_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Customs Declaration'
  AND status = 'Pending'
ORDER BY submission_date ASC;

-- Delivery photos flagged for potential damage
SELECT file_path, shipment_id, damage_detected, delivery_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Delivery Proof/Photo'
  AND damage_detected = true
ORDER BY delivery_date DESC;

-- Shipments with exception events in last 48 hours
SELECT shipment_id, exception_type, exception_count, last_event_time
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Tracking Log'
  AND exception_count > 0
  AND last_event_time > current_timestamp - interval '48' hour
ORDER BY exception_count DESC;
```

**Talking points**:
- "Customs team gets immediate visibility into pending declarations"
- "Claims team identifies damaged deliveries through AI photo analysis"
- "Operations team tracks exception patterns across the network"

---

### Step 5: Semantic Search for Shipment Investigation

**Duration**: 5 minutes

**Scenario**: "Find all documents related to shipment SHP2026060142"

Using OpenSearch:
1. **Keyword search**: `"SHP2026060142"` → all documents referencing this shipment
2. **Semantic search**: "container delay customs hold Pacific route" → finds similar delay patterns
3. **Combined**: Filter by route + date range + semantic relevance

**Talking points**:
- "Complete shipment document package assembled in seconds for customer inquiries"
- "Semantic search identifies similar past incidents for root cause analysis"
- "OpenSearch Serverless note: first search after extended idle may take 10–30 seconds for OCU warm-up"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 93%+ (5 categories) | PoC result; production varies |
| Processing time | 42 seconds/file | Single file; batch depends on concurrency |
| Cost per file | $0.05–$0.07 | Delivery photos: ~$0.05 |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Customs document retrieval | 20 min/search × 500 searches/year | **167 hours saved** |
| Delivery dispute resolution | 30 min/case × 200 cases/year → 5 min | **83 hours saved** |
| Shipment tracking investigation | 15 min/inquiry × 1,000 inquiries/year | **208 hours saved** |
| Exception pattern analysis | 2 hours/week manual → automated | **96 hours saved** |

**Conservative annual productivity value**: ~554 hours × ¥4,500/hr = **¥2,493,000** (~$16,600)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~1,114%

**Assumptions**: 50% adoption, mid-size logistics operation, no additional value from reduced customs penalties or faster claims resolution.

---

## Limitations Relevant to Logistics

| Limitation | Impact for Logistics |
|-----------|---------------------|
| S3 AP (pipeline reads only) | Cannot auto-archive completed shipment documents via pipeline |
| No S3 Event Notifications | Cannot trigger downstream routing workflows via S3 events |
| Bedrock accuracy varies | Multi-language trade documents (EN/JA/CN) may need prompt tuning |
| Delivery photo quality | Mobile photos in poor conditions may reduce damage detection accuracy |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Real-time requirements | Not suitable for real-time GPS tracking; designed for document processing |

---

## Customization Points

1. **Document categories**: Add carrier-specific types (carrier invoices, detention notices, rate confirmations)
2. **Route mapping**: Configure origin/destination extraction for company-specific trade lanes
3. **Compliance rules**: Map document requirements by country pair for customs compliance
4. **Damage classification**: Train detection categories for packaging, water, impact damage types

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

*Related: [use-cases/logistics/](../../use-cases/logistics/)*
*Pair document: [industry-logistics-ja.md](./industry-logistics-ja.md)*

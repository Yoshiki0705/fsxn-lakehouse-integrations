# Travel & Hospitality Demo Scenario: Guest Document & Property Management Intelligence

🌐 [日本語](industry-travel-hospitality-ja.md) | English

> Automated classification and search of guest documents, property photos, maintenance logs, and booking confirmations across hospitality group file shares.

---

## Business Context

### Challenge

Hospitality companies face:

- **Guest document sprawl**: Passport copies, booking confirmations, and special requests scattered across properties without unified retrieval
- **Property asset management**: Thousands of property photos, room layouts, and renovation documents stored inconsistently across hotels
- **Maintenance tracking gaps**: Work orders, inspection reports, and equipment logs disconnected from room/facility records
- **Brand compliance**: Marketing photos and brand guideline compliance across hundreds of properties tracked manually

### Solution Value

- Guest and property documents classified automatically by type, property, and status
- "Find all rooms with pending maintenance requests at Property Tokyo-01" answered via SQL
- Property photos tagged by room type, amenity, and renovation status
- Brand compliance and asset freshness tracked across the portfolio

---

## Demo Flow

### Step 1: Place Sample Hospitality Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry travel-hospitality --target /vol/hospitality/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `booking-confirm-RES2026-088421.pdf` | Booking Confirmation | Suite reservation, 3-night stay |
| `property-photo-TKY01-suite-801-main.jpg` | Property Photo | Suite 801 main view, post-renovation |
| `maintenance-log-TKY01-HVAC-20260601.pdf` | Maintenance Log | HVAC inspection, floor 8 |
| `guest-request-RES088421-dietary.pdf` | Guest Request | Dietary requirements, allergen info |
| `brand-audit-TKY01-Q2-2026.pdf` | Brand Audit | Quarterly brand standards compliance |

**Talking points**:
- "Property staff upload photos and documents through existing workflows — no process change"
- "Multiple properties share a central FSx file system for portfolio-wide intelligence"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: property-photo-TKY01-suite-801-main.jpg
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Property Photo/Room
   - Property: Tokyo-01
   - Room: Suite 801
   - View: Main (wide angle)
   - Renovation status: Completed
   - Brand compliance: Meets standards
   - Quality: Publication-ready
   - Amenities visible: Desk, sofa, minibar
✅ Classified in 40.5s | Cost: $0.05
```

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       property_id, room, document_status
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'travel-hospitality'
ORDER BY scan_timestamp DESC;
```

---

### Step 4: Hospitality Queries

**Duration**: 5 minutes

```sql
-- Rooms with pending maintenance at a property
SELECT room, maintenance_type, priority, request_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Maintenance%'
  AND property_id = 'TKY01'
  AND status = 'Pending'
ORDER BY priority DESC;

-- Property photos needing refresh (older than 1 year)
SELECT property_id, room, photo_type, last_modified
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Property Photo%'
  AND last_modified < current_date - interval '365' day
ORDER BY last_modified ASC;

-- Guest dietary/allergen requests for upcoming stays
SELECT reservation_id, guest_request_type, details, check_in_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Guest Request'
  AND check_in_date BETWEEN current_date AND current_date + interval '7' day
ORDER BY check_in_date;
```

---

### Step 5: Semantic Search for Property Operations

**Duration**: 5 minutes

**Scenario**: "Find all suite renovation photos for marketing update"

Using OpenSearch:
1. **Keyword search**: `"suite" AND "renovation" AND "Tokyo"` → exact matches
2. **Semantic search**: "luxury room interior design modern Japanese aesthetic" → finds matching property photos
3. **Combined**: Filter by property + room type + quality rating

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 93%+ (5 categories) | PoC result; production varies |
| Processing time | 40 seconds/file | Photos process slightly faster |
| Cost per file | $0.05–$0.07 | Photos: ~$0.05, documents: ~$0.07 |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Property photo management | 10 min/search × 500 searches/year → 1 min | **75 hours saved** |
| Maintenance coordination | 15 min/request × 1,000 requests/year → 3 min | **200 hours saved** |
| Guest request retrieval | 5 min/booking × 5,000 bookings/year → 30 sec | **375 hours saved** |
| Brand audit preparation | 2 days/quarter → 4 hours × 4 audits/year | **48 hours saved** |

**Conservative annual productivity value**: ~698 hours × ¥4,000/hr = **¥2,792,000** (~$18,600)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~941%

---

## Limitations Relevant to Travel & Hospitality

| Limitation | Impact for Hospitality |
|-----------|------------------------|
| S3 AP read-only | Cannot trigger PMS workflows or room status updates |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Guest PII | Guest documents contain extensive PII; verify data handling per privacy regulations |
| Multi-property scale | Performance at portfolio scale (100+ properties) needs capacity planning |
| Photo quality assessment | AI quality rating is assistive signal — not a replacement for professional review |
| Real-time operations | Not designed for real-time check-in/out; batch document processing |

---

## Customization Points

1. **Property hierarchy**: Configure brand → property → building → floor → room structure
2. **Room categories**: Map to company-specific room type taxonomy
3. **Maintenance types**: Align with property management system categories
4. **Brand standards**: Configure brand compliance checklist items per brand tier

---

*Related: [use-cases/travel-hospitality/](../../use-cases/travel-hospitality/)*
*Pair document: [industry-travel-hospitality-ja.md](./industry-travel-hospitality-ja.md)*

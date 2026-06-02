# Retail & Consumer Goods Demo Scenario: Product Catalog & Supply Chain Document Intelligence

🌐 [日本語](industry-retail-ja.md) | English

> Automated classification and search of product images, POS data exports, supplier contracts, and planogram documents across retail file shares.

---

## Business Context

### Challenge

Retail organizations face:

- **Product content sprawl**: Product images, planograms, marketing assets, and supplier contracts spread across regional file shares with no unified catalog
- **Supplier document chaos**: Thousands of contracts, invoices, and compliance certificates filed inconsistently across buyer teams
- **Seasonal planning delays**: Finding last year's planogram or promotional assets requires manual searching through folder hierarchies
- **Compliance gaps**: Supplier certifications and food safety documents lack expiry tracking

### Solution Value

- Product images and documents classified automatically by category, season, and brand upon upload
- "Show all expired supplier certifications" answered in seconds via SQL
- Planogram version history and seasonal asset retrieval becomes instant
- Supplier compliance tracking becomes data-driven with automated expiry alerts

---

## Demo Flow

### Step 1: Place Sample Retail Documents on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry retail --target /vol/retail-ops/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `planogram-electronics-2026Q2-v3.pdf` | Planogram | Electronics floor layout, revision 3 |
| `product-image-SKU88421-front.jpg` | Product Image | SKU 88421 front-facing product photo |
| `supplier-contract-VND-2026-0187.pdf` | Supplier Contract | Fresh produce supplier agreement |
| `pos-daily-export-20260601.csv` | POS Export | Daily transaction summary, 12,400 records |
| `food-safety-cert-VND0187-2026.pdf` | Compliance Certificate | Supplier food safety certification |

**Talking points**:
- "Store operations teams keep saving files the same way — no process change required"
- "Works with both headquarters NFS shares and store-level SMB mounts"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: planogram-electronics-2026Q2-v3.pdf
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Planogram/Floor Layout
   - Department: Electronics
   - Season: Q2 2026
   - Version: 3
   - Store format: Standard (1,200 sqm)
   - Compliance: Accessibility checked
✅ Classified in 43.2s | Cost: $0.07
```

**Talking points**:
- "AI identifies document type, department, season, and version automatically"
- "Product images are analyzed for category, brand positioning, and quality"
- "Classification confidence: PoC accuracy; production varies by image quality and document format"

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
-- Check classification results via Athena
SELECT file_path, ai_classification, confidence_score,
       department, season, document_version
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'retail'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | department | season | version |
|-----------|------------------|:---------:|:----------:|:------:|:-------:|
| /vol/retail-ops/planogram-electronics-2026Q2-v3.pdf | Planogram/Floor Layout | 0.95 | Electronics | Q2-2026 | 3 |
| /vol/retail-ops/product-image-SKU88421-front.jpg | Product Image/Front | 0.93 | Electronics | - | - |
| /vol/retail-ops/supplier-contract-VND-2026-0187.pdf | Supplier Contract | 0.94 | Procurement | - | - |
| /vol/retail-ops/pos-daily-export-20260601.csv | POS Data Export | 0.97 | Sales | 2026-06-01 | - |
| /vol/retail-ops/food-safety-cert-VND0187-2026.pdf | Compliance Certificate | 0.96 | Procurement | 2026 | - |

**Talking points**:
- "Five different document types classified with high accuracy"
- "Season and department extracted automatically for filtering"
- "Supplier compliance certificates get expiry dates tracked"

---

### Step 4: Retail Operations Queries

**Duration**: 5 minutes

```sql
-- Find all planograms for upcoming season
SELECT file_path, department, document_version, last_modified
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Planogram/Floor Layout'
  AND season = 'Q2-2026'
ORDER BY department, document_version DESC;

-- Expired supplier certifications
SELECT file_path, supplier_id, certification_type, expiry_date
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification = 'Compliance Certificate'
  AND expiry_date < current_date
ORDER BY expiry_date ASC;

-- Product images missing for active SKUs
SELECT sku_id, COUNT(*) as image_count
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Product Image%'
GROUP BY sku_id
HAVING COUNT(*) < 3;
```

**Talking points**:
- "Merchandising teams can find the latest planogram version instantly"
- "Procurement gets automatic alerts on expiring supplier certifications"
- "E-commerce teams identify SKUs missing product photography"

---

### Step 5: Semantic Search for Seasonal Planning

**Duration**: 5 minutes

**Scenario**: "Find all promotional assets from last holiday season"

Using OpenSearch:
1. **Keyword search**: `"holiday 2025" OR "Christmas promotion"` → exact matches
2. **Semantic search**: "winter seasonal display layouts for electronics" → finds related planograms and assets
3. **Combined**: Filter by department + season + semantic relevance

**Talking points**:
- "Seasonal planning no longer requires remembering exact folder paths from last year"
- "Vector search finds related assets even across different naming conventions"
- "OpenSearch Serverless note: first search after extended idle may take 10–30 seconds for OCU warm-up"

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 90%+ (6 categories) | PoC result; production varies |
| Processing time | 42 seconds/file | Single file; batch depends on concurrency |
| Cost per file | $0.07 | Text documents. Product images: ~$0.05 |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Planogram search time | 15 min/search × 200 searches/year | **50 hours saved** |
| Supplier compliance tracking | 2 days/quarter manual review → automated | **64 hours saved** |
| Product image retrieval | 5 min/day × 30 merchandisers × 50% adoption | **~275 hours/year** |
| Seasonal asset reuse | 3 days/season searching → 30 min × 4 seasons | **90 hours saved** |

**Conservative annual productivity value**: ~479 hours × ¥4,000/hr = **¥1,916,000** (~$12,800)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~836%

**Assumptions**: 50% user adoption, conservative time savings, no additional value from reduced stockouts or improved planogram compliance.

---

## Limitations Relevant to Retail

| Limitation | Impact for Retail |
|-----------|-------------------|
| S3 AP read-only | Cannot auto-archive obsolete planograms or expired assets via pipeline |
| No S3 Event Notifications | Cannot trigger downstream inventory workflows via S3 events |
| Bedrock accuracy varies | Product image classification accuracy depends on image quality and lighting |
| FPolicy latency (~1–5ms) | Negligible for document management; no impact on POS operations |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Image file size | Large product photography (>20MB) may increase processing time |

---

## Customization Points

1. **Classification categories**: Add retailer-specific types (loyalty program assets, store layouts by format)
2. **SKU mapping**: Connect product images to SKU master data for completeness tracking
3. **Seasonal tags**: Configure season definitions matching the retailer's merchandising calendar
4. **Supplier tiers**: Map certification requirements by supplier risk tier

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

*Related: [use-cases/retail/](../../use-cases/retail/)*
*Pair document: [industry-retail-ja.md](./industry-retail-ja.md)*

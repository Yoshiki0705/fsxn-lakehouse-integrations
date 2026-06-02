# Advertising & Marketing Demo Scenario: Creative Asset & Campaign Intelligence

🌐 [日本語](industry-advertising-marketing-ja.md) | English

> Automated classification and search of creative assets, campaign briefs, media plans, and brand guidelines across agency file shares.

---

## Business Context

### Challenge

Advertising and marketing organizations face:

- **Creative asset chaos**: Thousands of images, videos, copy documents, and design files scattered across campaign folders with inconsistent naming
- **Campaign brief fragmentation**: Briefs, revisions, client feedback, and approval documents disconnected across project drives
- **Brand guideline drift**: Multiple versions of brand guidelines and asset templates exist with unclear current status
- **Asset reuse failure**: Finding approved creative from past campaigns for reuse requires manual searching through years of archives

### Solution Value

- Creative assets classified automatically by campaign, format, approval status, and usage rights
- "Find all approved hero images for Brand X from Q1 campaigns" answered via SQL
- Campaign documents linked by project with revision history and approval chain tracking
- Cross-campaign creative discovery enabled through semantic search

---

## Demo Flow

### Step 1: Place Sample Advertising Files on FSx

**Duration**: 2 minutes

```bash
./demo/scripts/upload-sample-data.sh --industry advertising-marketing --target /vol/creative-ops/
```

**Sample files**:

| File Name | Type | Description |
|-----------|------|-------------|
| `creative-hero-brandX-summer2026-v3-approved.psd` | Creative Asset | Hero image, approved final |
| `campaign-brief-brandX-summer2026.pdf` | Campaign Brief | Summer campaign strategy and requirements |
| `media-plan-brandX-Q3-digital.xlsx` | Media Plan | Q3 digital media allocation |
| `brand-guidelines-brandX-v4.2.pdf` | Brand Guidelines | Current brand standards document |
| `performance-report-brandX-summer-week4.pdf` | Performance Report | Week 4 campaign metrics |

**Talking points**:
- "Creative teams keep using Dropbox/Drive synced to FSx — no workflow change"
- "Both raster/vector creative and documents processed through the same pipeline"

---

### Step 2: FPolicy Detection → AI Classification

**Duration**: ~42 seconds per file (automatic)

```
📄 Processing: creative-hero-brandX-summer2026-v3-approved.psd
🔍 FPolicy event: CREATE detected
🤖 Bedrock analysis:
   - Document type: Creative Asset/Hero Image
   - Brand: Brand X
   - Campaign: Summer 2026
   - Version: 3
   - Approval status: Approved
   - Format: PSD (print-ready)
   - Dimensions: 3000x2000px
   - Usage rights: Owned (worldwide)
   - Expiry: None
✅ Classified in 41.2s | Cost: $0.05
```

---

### Step 3: Review Classification Results

**Duration**: 3 minutes

```sql
SELECT file_path, ai_classification, confidence_score,
       brand, campaign, version, approval_status
FROM s3_tables.metadata_catalog.file_metadata
WHERE industry = 'advertising-marketing'
ORDER BY scan_timestamp DESC;
```

**Expected results**:

| file_path | ai_classification | confidence | brand | campaign | approval_status |
|-----------|------------------|:---------:|:-----:|:--------:|:---------------:|
| /vol/creative-ops/creative-hero-brandX-summer2026-v3-approved.psd | Creative/Hero Image | 0.95 | Brand X | Summer 2026 | Approved |
| /vol/creative-ops/campaign-brief-brandX-summer2026.pdf | Campaign Brief | 0.96 | Brand X | Summer 2026 | Final |
| /vol/creative-ops/media-plan-brandX-Q3-digital.xlsx | Media Plan | 0.94 | Brand X | Q3 2026 | Active |
| /vol/creative-ops/brand-guidelines-brandX-v4.2.pdf | Brand Guidelines | 0.98 | Brand X | - | Current |
| /vol/creative-ops/performance-report-brandX-summer-week4.pdf | Performance Report | 0.93 | Brand X | Summer 2026 | - |

---

### Step 4: Advertising Queries

**Duration**: 5 minutes

```sql
-- Approved creative assets by campaign
SELECT file_path, brand, campaign, asset_type, format, usage_rights
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Creative%'
  AND approval_status = 'Approved'
  AND brand = 'Brand X'
ORDER BY campaign DESC, asset_type;

-- Campaign documents completeness
SELECT brand, campaign,
       COUNT(CASE WHEN ai_classification = 'Campaign Brief' THEN 1 END) as briefs,
       COUNT(CASE WHEN ai_classification LIKE 'Creative%' THEN 1 END) as assets,
       COUNT(CASE WHEN ai_classification = 'Media Plan' THEN 1 END) as plans
FROM s3_tables.metadata_catalog.file_metadata
GROUP BY brand, campaign;

-- Assets with expiring usage rights
SELECT file_path, brand, usage_rights_expiry, license_type
FROM s3_tables.metadata_catalog.file_metadata
WHERE ai_classification LIKE 'Creative%'
  AND usage_rights_expiry < current_date + interval '90' day
ORDER BY usage_rights_expiry ASC;
```

---

### Step 5: Semantic Search for Creative Reuse

**Duration**: 5 minutes

**Scenario**: "Find lifestyle photography with summer outdoor theme for new campaign"

Using OpenSearch:
1. **Keyword search**: `"summer" AND "outdoor" AND "lifestyle"` → exact matches
2. **Semantic search**: "young professionals enjoying outdoor activities in urban park setting" → finds matching creative
3. **Combined**: Filter by approval status + usage rights + semantic similarity

---

## Expected Results

| Metric | Target | Caveat |
|--------|--------|--------|
| Classification accuracy | 93%+ (5 categories) | PoC result; production varies |
| Processing time | 41 seconds/file | Creative files by metadata/filename |
| Cost per file | $0.05–$0.07 | Documents: $0.07, images: $0.05 |
| Athena query response | 2–3 seconds | After cold start (first query: +3–5s) |
| OpenSearch response | <1 second | After warm-up (idle recovery: 10–30s) |

---

## ROI Narrative (Conservative Estimate)

| Item | Calculation | Annual Value |
|------|------------|:------------:|
| Asset search time | 20 min/search × 1,000 searches/year → 2 min | **300 hours saved** |
| Creative reuse | 5 reused assets/month × ¥200K production savings | **¥12M savings** |
| Campaign reporting | 2 hours/week × 50 weeks → automated | **100 hours saved** |
| Brand guideline compliance | 4 hours/month tracking → automated | **44 hours saved** |

**Conservative annual productivity value**: ~444 hours × ¥5,500/hr = **¥2,442,000** (~$16,300)
**Annual solution cost**: ~$1,368
**Conservative ROI**: ~1,091%

---

## Limitations Relevant to Advertising

| Limitation | Impact for Advertising |
|-----------|------------------------|
| S3 AP read-only | Cannot trigger creative approval workflows via pipeline |
| Large creative files | PSD/AI files (100MB+) processed at metadata/filename level |
| Lambda ephemeral access | File content passes through Lambda memory — zero-copy storage with ephemeral processing |
| Usage rights | AI extraction of rights metadata is assistive; verify with legal |
| Creative judgment | AI cannot assess creative quality or brand fit — human review required |
| Client confidentiality | Ensure client creative does not leak across account boundaries |

- **Minimum scale**: This industry may have smaller file volumes than manufacturing or financial services. Validate that daily file change rate exceeds 100/day to justify the AI pipeline overhead vs simpler alternatives.

---

## Customization Points

1. **Brand hierarchy**: Configure client → brand → sub-brand → campaign structure
2. **Asset formats**: Map file types to creative production stages (brief, comp, final)
3. **Usage rights**: Configure license type categories and expiry tracking
4. **Approval workflow**: Map status values to company approval process stages

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

*Related: [use-cases/advertising-marketing/](../../use-cases/advertising-marketing/)*
*Pair document: [industry-advertising-marketing-ja.md](./industry-advertising-marketing-ja.md)*

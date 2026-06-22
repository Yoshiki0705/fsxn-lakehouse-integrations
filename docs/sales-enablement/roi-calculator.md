🌐 **English** | [日本語](./roi-calculator-ja.md)

# ROI Calculator: FSx for ONTAP AI Metadata Catalog

> Use this calculator to build customer-specific cost justification with conservative, moderate, and optimistic scenarios.

---

## Inputs

| Parameter | Description | Example |
|-----------|-------------|---------|
| Total files | Files currently on FSx for ONTAP | 100,000 |
| Daily new/modified files | Files created or modified per day | 1,000 |
| Number of search users | Users who search for files daily | 50 |
| Current search time/day | Minutes per user per day spent searching | 30 min |
| Total storage | Current FSx for ONTAP capacity | 100 TB |
| Average file size | Typical file size for cost estimation | 100 KB |

---

## Cost Components

### AI Metadata Catalog Monthly Cost (1,000 files/day)

| Component | Pricing Basis | Monthly Cost |
|-----------|--------------|-------------|
| AWS Lambda | $0.20/1M invocations + compute | ~$6 |
| Amazon Bedrock (Claude) | See file-size cost table below | ~$65 |
| Amazon Titan Embeddings | $0.0001/1K tokens | ~$1 |
| S3 Tables (Iceberg metadata) | $0.01/GB/month | ~$0.05 |
| OpenSearch Serverless | $0.24/OCU/hr (scale-to-zero capable) | ~$42 |
| **Total** | | **~$114/month** |

### File-Size-Dependent Bedrock Cost

Bedrock classification cost varies significantly by file size. Use this table for estimation:

| File Size | Approx. Cost per File | Typical Content |
|-----------|----------------------|-----------------|
| 1 KB text | ~$0.01 | Short text files, configs |
| 100 KB document | ~$0.05 | Standard business documents |
| 1 MB PDF | ~$0.07 | Multi-page reports, contracts |
| 10 MB image | ~$0.15 | High-res images, scanned PDFs |

**Note:** Actual cost depends on prompt complexity, output token count, and whether vision (image) or text-only processing is used. The $0.07/file estimate in this document assumes a mix of 100KB–1MB documents.

### Idle Cost

When no files are being processed:
- Lambda: $0
- Bedrock: $0
- S3 Tables: ~$0.05/month (metadata storage only)
- OpenSearch Serverless: ~$5/month (minimum with scale-to-zero)

**Idle total: ~$5/month**

---

## ROI Scenarios

### Assumptions & Limitations

Before reviewing ROI numbers, note:

1. **Search time savings are estimates** — actual savings depend on current search behavior, folder structure, and whether users adopt the new search interface
2. **Productivity value uses hourly rate × time saved** — this assumes freed time is productively reused (not always the case)
3. **Storage savings assume the alternative is full S3 copy** — if the customer wouldn't copy to S3 anyway, this saving is theoretical
4. **Conservative scenario should be used as default** in customer conversations
5. **Bedrock accuracy**: PoC accuracy on test dataset; production accuracy varies by file type, language mix, and domain terminology
6. **Athena cold start**: First query after idle period takes 3–5s (affects perceived search speed)
7. **OpenSearch Serverless**: OCU warm-up may take 10–30s after extended idle

---

### Scenario Parameters

| Parameter | Conservative | Moderate | Optimistic |
|-----------|:----------:|:-------:|:---------:|
| Search time reduction per user | 10 min/day | 20 min/day | 30 min/day |
| Adoption rate (users actually using search) | 50% | 75% | 100% |
| Hourly rate (engineer) | ¥4,000 ($27) | ¥5,000 ($33) | ¥6,000 ($40) |
| Storage savings applicable | 50% (partial S3 avoidance) | 75% | 95% (full S3 avoidance) |
| Design reuse / additional value | Not included | 10% uplift | 20% uplift |

---

### Conservative Scenario (Default)

**Use this as the primary estimate in customer conversations.**

| Category | Monthly | Annual |
|----------|---------|--------|
| **Costs** | | |
| AI Metadata Catalog operation | $114 | $1,368 |
| **Benefits** | | |
| Search productivity (50 users × 50% adoption × 10 min/day × ¥4,000/hr) | $2,500 | $30,000 |
| Storage cost avoidance (50% of 100TB S3 copy avoided) | $1,150 | $13,800 |
| **Net benefit** | **$3,536** | **$42,432** |
| **ROI** | | **3,002%** |
| **Payback period** | | **~10 days** |

---

### Moderate Scenario

| Category | Monthly | Annual |
|----------|---------|--------|
| **Costs** | | |
| AI Metadata Catalog operation | $114 | $1,368 |
| **Benefits** | | |
| Search productivity (50 users × 75% adoption × 20 min/day × ¥5,000/hr) | $9,167 | $110,000 |
| Storage cost avoidance (75% of 100TB S3 copy avoided) | $1,725 | $20,700 |
| Additional value (10% uplift) | $1,089 | $13,070 |
| **Net benefit** | **$11,867** | **$142,402** |
| **ROI** | | **10,309%** |

---

### Optimistic Scenario

| Category | Monthly | Annual |
|----------|---------|--------|
| **Costs** | | |
| AI Metadata Catalog operation | $114 | $1,368 |
| **Benefits** | | |
| Search productivity (50 users × 100% adoption × 30 min/day × ¥6,000/hr) | $18,333 | $220,000 |
| Storage cost avoidance (95% of 100TB S3 copy avoided) | $2,185 | $26,220 |
| Additional value (20% uplift) | $4,104 | $49,244 |
| **Net benefit** | **$24,508** | **$294,096** |
| **ROI** | | **21,394%** |

---

## Cost Comparison: Metadata-Only vs Full Copy

| Approach | Monthly Storage | Data Movement | Total Monthly |
|----------|:--------------:|:------------:|:------------:|
| **This solution (metadata only)** | $0.05 (5GB) | $0 (zero-copy storage) | **$114** |
| S3 Standard (full copy) | $2,300 (100TB) | $90/month (sync) | **$2,390** |
| S3 + Glue Crawler | $2,300 + $44 | $90/month (sync) | **$2,434** |

**Note:** Storage savings are only realized if the alternative was actually copying data to S3. If the customer has no plan to copy data to S3, the savings comparison is theoretical.

---

## Scaling Examples

| Environment | Files | Daily Changes | Users | Monthly Cost | Monthly Benefit (Conservative) |
|-------------|:-----:|:------------:|:----:|:-----------:|:----------------------------:|
| Small | 10,000 | 100 | 10 | ~$25 | ~$500 |
| Medium | 100,000 | 1,000 | 50 | ~$114 | ~$3,650 |
| Large | 1,000,000 | 10,000 | 200 | ~$1,050 | ~$15,000 |
| Enterprise | 10,000,000 | 50,000 | 500 | ~$5,200 | ~$38,000 |

---

## Assumptions & Limitations

| Assumption | Reality Check |
|-----------|--------------|
| Users adopt the new search interface | Requires change management; adoption takes 2–4 weeks typically |
| Freed search time is productively reused | Not guaranteed — discount by adoption rate |
| Classification accuracy is sufficient | PoC accuracy on test dataset; production accuracy varies |
| All file types are classifiable | Some binary/proprietary formats may not classify well |
| OpenSearch remains responsive | Cold start after idle: 10–30s warm-up time |
| Athena queries are fast | First query after idle: 3–5s cold start |
| S3 Tables pricing is stable | S3 Tables GA Dec 2024; pricing may evolve |

---

## Formula Reference

```
Monthly Pipeline Cost =
  (daily_changes × 30 × cost_per_file)     # Bedrock classification (see file-size table)
  + (daily_changes × 30 × $0.001)           # Titan embeddings
  + (daily_changes × 30 × $0.0002)          # Lambda
  + (metadata_gb × $0.01)                    # S3 Tables
  + (opensearch_ocu_hours × $0.24)           # OpenSearch

Monthly Productivity Savings (Conservative) =
  users × adoption_rate × time_saved_min/day × 22 days × hourly_rate / 60

Monthly Storage Avoidance =
  total_storage_tb × $23/TB/month × storage_savings_applicable_rate

ROI = (Annual Benefits - Annual Costs) / Annual Costs × 100%
```

---

## Presenting to Customers

1. **Start with their numbers**: Ask for file count, daily changes, user count, and current search behavior
2. **Use Conservative scenario by default**: "Your environment would save approximately $X/month in the conservative case"
3. **Show range**: "Depending on adoption, benefits range from $X (conservative) to $Y (optimistic)"
4. **Be transparent about assumptions**: Call out what must be true for savings to materialize
5. **Acknowledge limitations**: S3 AP is used read-only in this pipeline (writes supported), classification accuracy varies, cold start delays exist
6. **Payback framing**: Even the conservative scenario shows payback in under 2 weeks

---

*All costs based on `ap-northeast-1` pricing as of 2026-06. Actual costs vary by region, file size mix, and usage patterns.*

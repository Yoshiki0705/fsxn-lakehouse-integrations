🌐 **English** | [日本語](./cost-estimation-ja.md)

# Cost Estimation: FSx for ONTAP AI Metadata Catalog

> Component-level cost breakdown and scaling formulas for capacity planning.

---

## Cost Components

### Monthly Operating Cost (1,000 files/day change rate)

| Component | Pricing Basis | Monthly Cost |
|-----------|--------------|-------------|
| AWS Lambda | $0.20/1M invocations + compute | ~$6 |
| Amazon Bedrock (Claude) | Per-token (see file-size table below) | ~$65 |
| Amazon Titan Embeddings | $0.0001/1K tokens | ~$1 |
| S3 Tables (Iceberg metadata) | $0.01/GB/month | ~$0.05 |
| OpenSearch Serverless | $0.24/OCU/hr (scale-to-zero capable) | ~$42 |
| **Total** | | **~$114/month** |

### File-Size-Dependent Bedrock Cost

Bedrock classification cost varies significantly by file size:

| File Size | Approx. Cost per File | Typical Content |
|-----------|:--------------------:|-----------------|
| 1 KB text | ~$0.01 | Short text files, configs |
| 100 KB document | ~$0.05 | Standard business documents |
| 1 MB PDF | ~$0.07 | Multi-page reports, contracts |
| 10 MB image | ~$0.15 | High-res images, scanned PDFs |

**Note:** Actual cost depends on prompt complexity, output token count, and whether vision (image) or text-only processing is used. The $0.07/file estimate assumes a mix of 100KB–1MB documents.

### Idle Cost

When no files are being processed:
- Lambda: $0
- Bedrock: $0
- S3 Tables: ~$0.05/month (metadata storage only)
- OpenSearch Serverless: ~$5/month (minimum with scale-to-zero)

**Idle total: ~$5/month**

---

## Scaling Estimates

| Environment | Files | Daily Changes | Monthly Cost |
|-------------|:-----:|:------------:|:-----------:|
| Small | 10,000 | 100 | ~$25 |
| Medium | 100,000 | 1,000 | ~$114 |
| Large | 1,000,000 | 10,000 | ~$1,050 |
| Enterprise | 10,000,000 | 50,000 | ~$5,200 |

---

## Cost Comparison: Metadata-Only vs Full Copy

| Approach | Monthly Storage | Data Movement | Total Monthly |
|----------|:--------------:|:------------:|:------------:|
| **This solution (metadata only)** | $0.05 (5 GB) | $0 (zero-copy storage) | **$114** |
| S3 Standard (full copy of 100 TB) | $2,300 | $90/month (sync) | **$2,390** |
| S3 + Glue Crawler | $2,300 + $44 | $90/month (sync) | **$2,434** |

**Note:** Storage savings comparison is only valid if the alternative is actually copying full data to S3. If there is no plan to replicate all NAS data to S3, this comparison is theoretical.

---

## Formula Reference

```
Monthly Pipeline Cost =
  (daily_changes × 30 × cost_per_file)     # Bedrock classification (see file-size table)
  + (daily_changes × 30 × $0.001)           # Titan embeddings
  + (daily_changes × 30 × $0.0002)          # Lambda
  + (metadata_gb × $0.01)                   # S3 Tables
  + (opensearch_ocu_hours × $0.24)          # OpenSearch
```

---

## Assumptions & Caveats

| Assumption | Reality Check |
|-----------|--------------|
| File sizes average 100KB–1MB | Larger files (images, videos) increase Bedrock cost significantly |
| Classification uses default prompt | Custom prompts with more output tokens increase per-file cost |
| OpenSearch uses scale-to-zero | Minimum OCU allocation applies (~$5/month even when idle) |
| S3 Tables pricing is stable | S3 Tables GA Dec 2024; pricing may evolve |
| Single region deployment | Multi-region adds SnapMirror + duplicate pipeline costs |
| Standard concurrency | High concurrency may require Lambda reserved concurrency (additional cost) |

---

## Related Documents

| Document | Content |
|----------|---------|
| [Technical Overview](./technical-overview.md) | Architecture and verified metrics |
| [Technical FAQ](./technical-faq.md) | Detailed Q&A including cost-related questions |
| [Architecture Comparison](./architecture-comparison.md) | Trade-offs between different approaches |
| [PoC Execution Guide](../implementation-guide/poc-execution-guide.md) | Step-by-step implementation checklist |

---

*All costs based on `ap-northeast-1` pricing as of 2026-06. Actual costs vary by region, file size mix, and usage patterns.*

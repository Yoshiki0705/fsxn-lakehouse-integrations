# ROI Calculator: FSx for ONTAP AI Metadata Catalog

> Use this calculator to build customer-specific cost justification.

---

## Inputs / 入力パラメータ

| Parameter | Description | Example |
|-----------|-------------|---------|
| Total files (既存ファイル数) | Files currently on FSx for ONTAP | 100,000 |
| Daily new/modified files (日次変更数) | Files created or modified per day | 1,000 |
| Number of users searching (検索ユーザー数) | Users who search for files daily | 50 |
| Current search time/day (現在の検索時間) | Minutes per user per day spent searching | 30 min |
| Total storage (総ストレージ) | Current FSx for ONTAP capacity | 100 TB |

---

## Cost Components / コスト構成

### AI Metadata Catalog Monthly Cost / AI メタデータカタログ月額コスト

| Component | Pricing | Calculation (1000 files/day) | Monthly Cost |
|-----------|---------|------------------------------|-------------|
| AWS Lambda | $0.20 per 1M invocations + compute | 1000/day × 30 days × ~$0.0002/invocation | ~$6 |
| Amazon Bedrock (Claude) | ~$0.003/1K input tokens + $0.015/1K output tokens | 1000 files/day × ~$0.065/file × 30 days | ~$65 |
| Amazon Bedrock (Titan Embeddings) | $0.0001/1K tokens | 1000/day × 30 days × ~$0.001/file | ~$1 |
| S3 Tables (Iceberg metadata) | $0.01/GB/month | ~5GB metadata for 100K files | ~$0.05 |
| OpenSearch Serverless | Scale-to-zero + $0.24/OCU/hr when active | 2 OCU avg × $0.24 × 720hr × 25% utilization | ~$42 |
| **Total** | | | **~$114/month** |

### Idle Cost / アイドル時コスト

When no files are being processed:
- Lambda: $0 (no invocations)
- Bedrock: $0 (no API calls)
- S3 Tables: ~$0.05/month (metadata storage only)
- OpenSearch Serverless: scales to minimum (~$5/month with scale-to-zero)

**Idle total: ~$5/month** — ほぼゼロコスト

---

## Cost Comparison / コスト比較

### vs Full Data Copy to S3 / S3 フルコピーとの比較

| Approach | Monthly Storage Cost | Data Movement | Total Monthly |
|----------|---------------------|---------------|---------------|
| **Our solution (metadata only)** | $0.05 (5GB metadata) | $0 (zero-copy) | **$114** |
| S3 Standard (full copy) | $2,300 (100TB) | $90/month (sync) | **$2,390** |
| S3 + Glue Crawler | $2,300 (100TB) + $44 (crawl) | $90/month (sync) | **$2,434** |
| Databricks (S3 copy + UC) | $2,300 (100TB) + $200 (DBU) | $90/month (sync) | **$2,590** |

**Savings: 95%** — ストレージコスト 95% 削減

---

## Time Savings / 時間削減効果

### Search Time Reduction / 検索時間削減

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Time per search | 5–15 min (manual folder browsing) | 2–5 sec (SQL/semantic search) | ~99% |
| Searches per user per day | 6 (give up on some) | Unlimited | — |
| Total search time per user/day | 30 min | ~2 min | **28 min/day** |

### Productivity Calculation / 生産性計算

```
Daily time saved = 28 min/user × 50 users = 1,400 min = 23.3 hours/day
Monthly time saved = 23.3 hours × 22 working days = 513 hours/month
Annual time saved = 513 hours × 12 months = 6,156 hours/year

Value (at ¥5,000/hour engineer rate):
  Monthly = 513 hours × ¥5,000 = ¥2,565,000/month (~$17,100)
  Annual  = 6,156 hours × ¥5,000 = ¥30,780,000/year (~$205,000)
```

---

## ROI Calculation / ROI 計算

### Example: 100K Files, 50 Users / 計算例: 10 万ファイル、50 ユーザー

| Category | Monthly | Annual |
|----------|---------|--------|
| **Costs** | | |
| AI Metadata Catalog operation | $114 | $1,368 |
| **Benefits** | | |
| Storage savings (vs S3 copy) | $2,276 | $27,312 |
| Productivity savings | $17,100 | $205,200 |
| **Net benefit** | **$19,262** | **$231,144** |
| **ROI** | | **16,792%** |

---

## Scaling Examples / スケーリング例

| Environment | Files | Daily Changes | Users | Monthly Cost | Monthly Benefit |
|-------------|-------|---------------|-------|-------------|-----------------|
| Small (中小) | 10,000 | 100 | 10 | ~$25 | ~$3,800 |
| Medium (中規模) | 100,000 | 1,000 | 50 | ~$114 | ~$19,400 |
| Large (大規模) | 1,000,000 | 10,000 | 200 | ~$1,050 | ~$82,000 |
| Enterprise (エンタープライズ) | 10,000,000 | 50,000 | 500 | ~$5,200 | ~$210,000 |

---

## Additional Value Drivers / その他の定量効果

### Compliance & Risk / コンプライアンス・リスク

| Benefit | Value Estimate |
|---------|---------------|
| Auto PII detection (vs manual review) | ¥500,000/month (audit labor saved) |
| Instant compliance reporting | ¥200,000/audit (time saved) |
| Reduced data breach risk | Risk mitigation (not quantified) |

### Design Reuse (Manufacturing) / 設計再利用（製造業）

| Benefit | Value Estimate |
|---------|---------------|
| Similar design discovery | 20% of new designs → reuse existing |
| Reduced design time | 15% engineering hours saved |
| Quality improvement | Fewer re-designs from missed prior art |

---

## Formula Reference / 計算式リファレンス

```
Monthly Pipeline Cost =
  (daily_changes × 30 × $0.065)          # Bedrock classification
  + (daily_changes × 30 × $0.001)         # Titan embeddings
  + (daily_changes × 30 × $0.0002)        # Lambda
  + (metadata_gb × $0.01)                  # S3 Tables
  + (opensearch_ocu_hours × $0.24)         # OpenSearch

Monthly Storage Savings =
  (total_storage_tb × $23/TB/month)        # Avoided S3 Standard cost
  - (metadata_gb × $0.01)                  # Actual metadata cost

Monthly Productivity Savings =
  (users × time_saved_min/day × 22 days × hourly_rate / 60)

ROI = (Monthly Benefits - Monthly Costs) / Monthly Costs × 100%

Payback Period = Monthly Costs / Monthly Benefits (typically < 1 month)
```

---

## Presenting to Customers / お客様への提示方法

1. **Start with their numbers**: Ask for file count, daily changes, user count, and search time
2. **Show the cost**: "Your environment would cost approximately $X/month"
3. **Show the savings**: "vs copying to S3, you save $Y/month in storage alone"
4. **Show the productivity**: "Your 50 engineers recovering 30 min/day = $Z/month in value"
5. **Close with ROI**: "Payback is less than one month. The solution pays for itself in the first week."

---

*All costs based on `ap-northeast-1` pricing as of 2026-06. Actual costs vary by region and usage patterns.*

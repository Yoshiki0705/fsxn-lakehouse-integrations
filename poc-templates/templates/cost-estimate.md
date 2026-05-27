🌐 **English** | [日本語](ja/cost-estimate.md)

# PoC Cost Estimate Calculator

## Instructions

Fill in the "Your estimate" column based on customer requirements. Use the reference costs from our validation.

---

## Base Infrastructure (Required)

| Component | Reference cost | Your estimate | Notes |
|-----------|---------------|---------------|-------|
| FSx for ONTAP (existing) | $0 incremental | $_______ | Use existing file system |
| S3 Access Point | $0 | $0 | No additional charge |
| IAM roles/policies | $0 | $0 | No charge |
| Sample data upload | $0 | $0 | Via S3 AP PutObject |

## Per-Engine Costs

### Athena (Serverless SQL)

| Component | Unit cost | PoC usage | Estimated cost |
|-----------|-----------|-----------|---------------|
| Query (data scanned) | $5/TB | ___ GB scanned | $_______ |
| Glue Catalog | $1/100K objects/month | < 100 objects | ~$0 |
| Lake Formation | $0 | — | $0 |
| **Athena total** | | | **$_______** |

Reference: Our validation scanned ~103 MB (5M rows) = $0.0005/query

### DuckDB Lambda (Cheapest)

| Component | Unit cost | PoC usage | Estimated cost |
|-----------|-----------|-----------|---------------|
| Lambda invocations | $0.20/1M | ___ invocations | $_______ |
| Lambda compute (1024MB) | $0.0000133/GB-s | ___ seconds | $_______ |
| **DuckDB Lambda total** | | | **$_______** |

Reference: ~$0.00001/query, $1.10/month for 1000 queries/day

### EMR Serverless (Spark ETL)

| Component | Unit cost | PoC usage | Estimated cost |
|-----------|-----------|-----------|---------------|
| vCPU-hour | $0.052624 | ___ hours | $_______ |
| Memory GB-hour | $0.0057785 | ___ GB-hours | $_______ |
| Storage GB-hour | $0.000111 | ___ GB-hours | $_______ |
| **EMR total** | | | **$_______** |

Reference: ~$0.05/job (37s job with 4 vCPU, 16 GB)

### Redshift Serverless (DWH)

| Component | Unit cost | PoC usage | Estimated cost |
|-----------|-----------|-----------|---------------|
| RPU-hour | $0.375/RPU-hour | ___ RPU-hours | $_______ |
| **Redshift total** | | | **$_______** |

Reference: 8 RPU × 5s/query × 100 queries = ~$0.40/day

### Snowflake (External Table + Cortex AI)

| Component | Unit cost | PoC usage | Estimated cost |
|-----------|-----------|-----------|---------------|
| Warehouse credits (XS) | ~$2/credit | ___ credits | $_______ |
| Cortex AI functions | Per-token pricing | ___ queries | $_______ |
| Storage (if COPY INTO) | $23/TB/month | ___ GB | $_______ |
| **Snowflake total** | | | **$_______** |

Reference: ~$5 for 1-day validation (XS warehouse, ~2.5 credits)

### Databricks (DataSync → UC)

| Component | Unit cost | PoC usage | Estimated cost |
|-----------|-----------|-----------|---------------|
| DataSync transfer | $0.0125/GB | ___ GB | $_______ |
| S3 storage (synced copy) | $0.023/GB/month | ___ GB | $_______ |
| Databricks DBU | Varies by SKU | ___ DBU | $_______ |
| **Databricks total** | | | **$_______** |

Reference: ~$10 for 1-day validation (1 TB sync + compute)

---

## Total PoC Cost Summary

| Scenario | Engines | Estimated total |
|----------|---------|----------------|
| Minimum (AWS-native only) | Athena + DuckDB | ~$0.06 |
| Standard (+ EMR write-back) | Athena + EMR + LF | ~$0.55 |
| With Snowflake | + Snowflake External Table + Cortex | ~$5.55 |
| With Databricks | + DataSync + UC | ~$10.55 |
| Full validation (all engines) | All of the above | ~$16 |

---

## Ongoing Monthly Cost (Post-PoC Production)

| Pattern | Monthly cost | Notes |
|---------|-------------|-------|
| Athena ad-hoc (100 queries/day) | ~$15/month | $5/TB × data scanned |
| DuckDB Lambda (1000 queries/day) | ~$1.10/month | Cheapest ongoing |
| EMR batch ETL (10 jobs/day) | ~$15/month | Per-job pricing |
| Redshift Serverless (100 queries/day) | ~$12/month | RPU-seconds |
| Snowflake (XS, 8h/day) | ~$480/month | Credit-based |
| Databricks (DataSync + compute) | ~$50-200/month | Sync + DBU |

---

## Cost Comparison: Current State vs FSx S3 AP

| Metric | Current (with copy pipeline) | With FSx S3 AP | Savings |
|--------|------------------------------|----------------|---------|
| S3 storage (duplicate) | $___/month | $0 (no copy) | $___/month |
| DataSync/ETL pipeline | $___/month | $0 (direct query) | $___/month |
| Pipeline maintenance (hours) | ___h/month | 0h | ___h/month |
| Data freshness lag | ___hours | Near-zero | ___hours |
| **Total monthly savings** | | | **$___/month** |

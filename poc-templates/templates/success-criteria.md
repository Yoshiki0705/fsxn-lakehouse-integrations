# PoC Success Criteria & Go/No-Go Framework

## How to Use

Fill in this template before starting the PoC. Review with the customer at the end to make the Go/No-Go decision.

---

## PoC Scope

| Field | Value |
|-------|-------|
| Customer | _______________ |
| Partner | _______________ |
| Start date | _______________ |
| End date | _______________ |
| Primary engine | Athena / Snowflake / Databricks / EMR / DuckDB |
| Data type | Structured / Unstructured / Both |
| Data volume (PoC) | ___ GB |
| Regulated data? | Yes / No |

---

## Success Criteria

### Tier 1: Technical Validation (Must Pass)

| # | Criterion | Target | Actual | Pass? |
|---|-----------|--------|--------|:---:|
| 1 | S3 Access Point lifecycle | AVAILABLE | | ☐ |
| 2 | ListObjectsV2 returns expected files | File count matches | | ☐ |
| 3 | Query returns correct results | Row count + values match | | ☐ |
| 4 | NFS/SMB access unaffected | Latency within baseline ±10% | | ☐ |
| 5 | Query latency acceptable | < ___s (customer-defined) | | ☐ |

### Tier 2: Operational Validation (Should Pass)

| # | Criterion | Target | Actual | Pass? |
|---|-----------|--------|--------|:---:|
| 6 | IAM policy scoped to minimum privilege | No wildcard resources | | ☐ |
| 7 | FSx throughput impact measured | < ___% of provisioned capacity | | ☐ |
| 8 | Cost per query measured | < $___/query | | ☐ |
| 9 | Governance controls applied | Tags / LF / Snowflake RBAC | | ☐ |
| 10 | Refresh/sync latency measured | < ___ minutes | | ☐ |

### Tier 3: Business Validation (Nice to Have)

| # | Criterion | Target | Actual | Pass? |
|---|-----------|--------|--------|:---:|
| 11 | Data freshness improvement | From ___h to ___h | | ☐ |
| 12 | Pipeline elimination | ___ pipelines removed | | ☐ |
| 13 | Storage cost reduction | ___% reduction | | ☐ |
| 14 | Time-to-insight improvement | From ___days to ___hours | | ☐ |
| 15 | AI/ML capability demonstrated | Function works on NAS data | | ☐ |

---

## Go / No-Go Decision

### Go Conditions (ALL must be true)

- [ ] Tier 1 criteria ALL pass
- [ ] No unresolved security concerns
- [ ] Customer confirms business value
- [ ] Cost is within acceptable range
- [ ] Operational model is sustainable

### No-Go Conditions (ANY triggers No-Go)

- [ ] Query fails after correct configuration (platform limitation)
- [ ] FSx throughput impact exceeds acceptable threshold
- [ ] Security/governance requirements cannot be met
- [ ] Cost exceeds budget by > 2x
- [ ] Customer's required table format (Delta/Iceberg write) is not supported on S3 AP

### Adjust Conditions (Partial success — redesign needed)

- [ ] Works for read but not write → Use hybrid pattern (FSx read + S3 write)
- [ ] Works but governance insufficient → Add Lake Formation or Snowflake governance layer
- [ ] Works but latency too high → Increase FSx throughput or use caching layer
- [ ] Works but sync needed → Add DataSync for platforms requiring S3 (Databricks)

---

## Decision Record

| Field | Value |
|-------|-------|
| Decision | Go / No-Go / Adjust |
| Decision date | _______________ |
| Decision maker | _______________ |
| Rationale | _______________ |
| Next steps | _______________ |
| Review date | _______________ |

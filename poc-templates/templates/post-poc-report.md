# Post-PoC Report

## Customer: [Name]
## Partner: [Name]
## Date: [YYYY-MM-DD]
## Duration: [X days]

---

## Executive Summary

[1-2 sentences: What was tested, what was the result, what is the recommendation]

---

## PoC Scope

| Dimension | Value |
|-----------|-------|
| Engine(s) tested | |
| Data volume | |
| File types | |
| Governance level | |
| AI/ML tested | |

---

## Results

### Technical Validation

| Criterion | Target | Actual | Pass? |
|-----------|--------|--------|:---:|
| S3 AP available | AVAILABLE | | ☐ |
| Query returns correct results | Match expected | | ☐ |
| Query latency | < ___s | ___s | ☐ |
| Write-back (if tested) | Success | | ☐ |
| NFS/SMB impact | < 10% degradation | ___% | ☐ |

### Performance

| Metric | Value | Notes |
|--------|-------|-------|
| Query latency (cold) | ___ms | |
| Query latency (warm) | ___ms | |
| Throughput (MB/s) | ___ | |
| Cost per query | $___ | |
| FSx throughput utilization during query | ___% | |

### Governance

| Capability | Tested | Result |
|-----------|:---:|--------|
| Table-level access control | ☐ | |
| Column-level masking | ☐ | |
| Row-level filtering | ☐ | |
| Tag-based classification | ☐ | |
| Audit trail | ☐ | |

### AI/ML (if tested)

| Capability | Tested | Result | Latency |
|-----------|:---:|--------|---------|
| Text summarization | ☐ | | ___s |
| Sentiment analysis | ☐ | | ___s |
| Document OCR | ☐ | | ___s |
| Semantic search (RAG) | ☐ | | ___ms |
| Vision AI | ☐ | | ___s |

---

## Decision

| | |
|---|---|
| **Decision** | Go / No-Go / Adjust |
| **Rationale** | |
| **Conditions** | |
| **Next steps** | |

---

## Recommended Production Architecture

```
[Insert architecture diagram based on PoC results]
```

| Component | PoC | Production | Change needed |
|-----------|-----|-----------|---------------|
| FSx throughput | 128 MB/s | ___ MB/s | |
| S3 AP network origin | Internet | VPC / Internet | |
| Governance | IAM only | + Lake Formation / Snowflake | |
| Monitoring | Manual | CloudWatch alarms | |
| DR | None | SnapMirror + AP in DR region | |

---

## Cost Projection (Production)

| Component | Monthly cost | Notes |
|-----------|-------------|-------|
| FSx for ONTAP (existing) | $0 incremental | |
| Analytics engine | $___ | |
| Governance (Lake Formation) | $0 | |
| Monitoring | $___ | |
| **Total** | **$___/month** | |

### Savings vs Current State

| Metric | Current | After | Monthly savings |
|--------|---------|-------|----------------|
| Duplicate S3 storage | $___ | $0 | $___ |
| Pipeline maintenance | ___h | 0h | $___ (labor) |
| Data freshness | ___h lag | Near-zero | — |

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|:---:|:---:|-----------|
| | | | |

---

## Appendix

- [ ] Evidence artifacts (screenshots, query results, CloudTrail samples)
- [ ] Configuration used (IAM policies, AP policies, stage definitions)
- [ ] Benchmark raw data
- [ ] Approval records (if regulated)

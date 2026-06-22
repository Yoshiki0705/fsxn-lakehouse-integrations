🌐 **English** | [日本語](./technical-overview-ja.md)

# FSx for ONTAP × AI Metadata Catalog: Technical Overview

> Architecture and verified metrics for the zero-copy metadata catalog pipeline.

---

## Problem Context

- **NAS data visibility**: Unstructured files on enterprise file servers are not searchable or discoverable by analytics platforms.
- **Data copy overhead**: Copying terabytes of NAS data to S3 for analytics duplicates storage costs and introduces ongoing sync complexity.
- **Manual classification at scale**: Human file tagging cannot keep pace with thousands of daily file changes across departments.

---

## Solution Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  FSx for ONTAP  │────▶│  S3 Access   │────▶│  AI Pipeline    │────▶│  S3 Tables   │────▶│  Analytics      │
│  (NFS/SMB)      │     │  Point       │     │  (Bedrock/      │     │  (Iceberg)   │     │  (Athena/EMR/   │
│                 │     │  (read-only) │     │   Lambda)       │     │              │     │   OpenSearch)   │
│  File originals │     │  Zero-copy   │     │  Classify +     │     │  Metadata    │     │  Search +       │
│                 │     │  storage     │     │  embed          │     │  only        │     │  query          │
└─────────────────┘     └──────────────┘     └─────────────────┘     └──────────────┘     └─────────────────┘
        │                                                                                          │
        └──────────────── Files do not move (zero-copy storage principle) ──────────────────────────┘
```

**Zero-copy storage**: S3 Access Point reads files in-place from FSx for ONTAP volumes. Processing requires ephemeral file content access in Lambda memory. File bytes are not persisted outside the source FSx for ONTAP volume.

---

## Verified Metrics (PoC)

| Metric | Value | Caveat |
|--------|-------|--------|
| End-to-end pipeline time | **42 seconds** (detect → classify → register → searchable) | Single file; batch throughput depends on concurrency |
| Cost per file | **$0.07** (Lambda + Bedrock + S3 Tables) | Based on ~100KB–1MB documents; varies by file size |
| Monthly cost (100K files, 1K/day changes) | **$114/month** (idle: ~$5/month) | Assumes default OpenSearch OCU allocation |
| Storage overhead vs full S3 copy | **~95% less** | Applicable only when alternative is full S3 copy |
| Classification confidence | **0.94** (PoC average) | Test dataset only; production accuracy varies by file type, language, and domain |

---

## Platform Integration Status

| Platform | Status | Notes |
|----------|--------|-------|
| Amazon Athena | ✅ Verified | Direct S3 Tables Iceberg query; 3–5s cold start after idle |
| Amazon EMR (Spark) | ✅ Verified | Native Iceberg table read/write |
| Amazon OpenSearch | ✅ Verified | Vector + keyword search; 10–30s warm-up after idle |
| Snowflake | ✅ Cortex File AI verified | Direct Iceberg catalog query pending Snowflake feature support |
| Databricks | Under evaluation | Via DataSync or Foreign Catalog (evolving as of 2026-06) |

---

## Limitations & Constraints

| Item | Detail |
|------|--------|
| S3 AP read-only in this pipeline | Analytics services cannot write back to FSx for ONTAP volumes via S3 AP (writes are supported at the API level) |
| No S3 Event Notifications via S3 AP | Cannot trigger Snowpipe, EventBridge, or bucket notifications |
| FPolicy latency | Adds ~1–5ms per file operation to NAS clients |
| Lambda ephemeral processing | File content passes through Lambda memory — not persisted, but not "zero data movement" at the processing layer |
| Bedrock accuracy varies | File type, language mix, and domain terminology affect classification quality |
| S3 Tables maturity | GA Dec 2024; some cross-platform integrations still evolving |
| Athena cold start | 3–5s for first query after idle period |
| OpenSearch warm-up | Serverless OCU allocation: 10–30s after extended idle |

---

## When This Pattern Does NOT Apply

| Scenario | Alternative | Reason |
|----------|-------------|--------|
| Data born in S3 (no NAS origin) | S3-native + Glue | No benefit from zero-copy if data is already in S3 |
| Small file sets (<5K files, infrequent changes) | DataSync + S3 | Simpler operations; event-driven detection is unnecessary |
| S3 Event Notifications required | S3 Standard | S3 AP does not support Event Notifications |
| Write-back from analytics to storage | S3 Standard | S3 AP is read-only in this pipeline |
| No existing FSx for ONTAP deployment | Evaluate adoption cost first | Solution assumes FSx for ONTAP is in place or planned |

See [Architecture Comparison](./architecture-comparison.md) for the full decision framework.

---

## Industry Classification Templates

20 pre-configured classification templates are available for common enterprise file patterns:
Manufacturing, Financial Services, Healthcare, Construction, Legal, Media, Public Sector, Education, Logistics, Retail, Real Estate, Energy, Telecommunications, Pharmaceutical, Insurance, Agriculture, Automotive, Aerospace, Government, Research/Academia.

Each template includes AI classification categories, sample Athena queries, and expected file patterns.

---

## Related Documents

| Document | Content |
|----------|---------|
| [Architecture Comparison](./architecture-comparison.md) | Decision framework for choosing the right approach |
| [Technical FAQ](./technical-faq.md) | Detailed Q&A on limitations, integrations, and design |
| [Cost Estimation](./cost-estimation.md) | Component-level cost breakdown and scaling formulas |
| [PoC Execution Guide](../implementation-guide/poc-execution-guide.md) | Step-by-step PoC implementation checklist |

---

*Last updated: 2026-06. Based on publicly available documentation and PoC testing in this repository.*

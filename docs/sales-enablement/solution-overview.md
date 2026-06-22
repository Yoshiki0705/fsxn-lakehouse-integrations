🌐 **English** | [日本語](./solution-overview-ja.md)

# FSx for ONTAP × AI Metadata Catalog: Solution Overview

> Technical overview for field engineers and solutions architects

---

## Problem Statement

- **NAS data is dark data**: Unstructured files on file servers cannot be searched or analyzed. No one knows what exists or where.
- **Data copy is costly**: Copying to S3 for analytics doubles storage costs. 100TB = ~$2,280+/month in S3 Standard alone.
- **Manual classification doesn't scale**: Human file tagging cannot keep up with thousands of daily file changes.

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

## Verified Metrics

| Metric | Value | Caveat |
|--------|-------|--------|
| End-to-end pipeline time | **42 seconds** (detect → classify → register → searchable) | Single file; batch throughput depends on concurrency |
| Cost per file | **$0.07** (Lambda + Bedrock + S3 Tables) | Based on ~100KB–1MB documents; see file-size cost table |
| Monthly cost (100K files, 1K/day changes) | **$114/month** (idle: ~$5/month) | Assumes default OpenSearch OCU allocation |
| Storage cost vs full S3 copy | **95% less** | Only applicable when alternative is S3 full copy |
| Classification confidence | **0.94** (PoC average) | PoC accuracy on test dataset; production accuracy varies by file type, language mix, and domain terminology |

---

## Platform Integration Status

| Platform | Status | Notes |
|----------|--------|-------|
| Amazon Athena | ✅ Verified | Direct S3 Tables Iceberg query; 3–5s cold start after idle |
| Amazon EMR (Spark) | ✅ Verified | Native Iceberg table read/write |
| Amazon OpenSearch | ✅ Verified | Vector + keyword search; 10–30s warm-up after idle |
| Snowflake | ✅ Cortex File AI verified | Direct Iceberg catalog query pending Snowflake feature support |
| Databricks | Pending | Via DataSync or Foreign Catalog (evolving) |

---

## Limitations & Considerations

| Item | Detail |
|------|--------|
| S3 AP is used read-only in this pipeline (writes are supported) | Analytics services cannot write back to FSx for ONTAP volumes |
| No S3 Event Notifications via S3 AP | Cannot trigger Snowpipe, EventBridge, or bucket notifications |
| FPolicy latency | Adds ~1–5ms per file operation to NAS clients |
| Lambda ephemeral processing | File content passes through Lambda memory — not persisted, but not "zero data movement" at the processing layer |
| Bedrock accuracy varies | File type, language mix, and domain terminology affect classification quality |
| S3 Tables maturity | GA Dec 2024; some cross-platform integrations still evolving |
| Athena cold start | 3–5s for first query after idle period |
| OpenSearch warm-up | Serverless OCU allocation: 10–30s after extended idle |

---

## When NOT to Use This Solution

- Data is born in S3 with no NAS access requirements → use S3-native + Glue
- Small file sets (<5,000 files) with infrequent changes → DataSync is simpler
- Need S3 Event Notifications for downstream automation → S3 AP does not support them
- Need write-back from analytics to storage → S3 AP is used read-only in this pipeline (writes supported)
- No existing FSx for ONTAP deployment → evaluate FSx for ONTAP adoption cost first

See [Architecture Comparison](./architecture-comparison.md) for full decision framework.

---

## Industry Templates

20 industry classification templates available out of the box:
Manufacturing, Financial Services, Healthcare, Construction, Legal, Media, Public Sector, Education, Logistics, Retail, Real Estate, Energy, Telecommunications, Pharmaceutical, Insurance, Agriculture, Automotive, Aerospace, Government, Research/Academia.

Each template includes pre-configured AI classification categories, sample queries, and ROI narrative.

---

## Next Steps

1. **30-minute Quick Demo**: CloudFormation single deploy → 42-second end-to-end experience
2. **PoC (1–2 weeks)**: Validate AI classification accuracy on customer's actual files
3. **Production deployment**: Phased rollout with SI partner support

**GitHub Repository**: [fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations)

---

*This document is for field use. Customize for specific customer context before distribution.*

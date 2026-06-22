🌐 **English** | [日本語](./architecture-comparison-ja.md)

# Architecture Comparison: Approaches to Unstructured Data Analytics

> A factual comparison of approaches for making NAS-resident unstructured data queryable via analytics platforms.

---

## Overview

This document compares architectural approaches for connecting unstructured file data (NAS) to analytics and AI services. Each approach has legitimate tradeoffs — the best choice depends on data origin, access patterns, file volume, and existing tooling.

---

## Approach Summary

| Approach | Data Movement | Event-Driven | Multi-Protocol | Best For |
|----------|:------------:|:------------:|:--------------:|----------|
| FSx for ONTAP + S3 Access Point | Zero-copy storage* | FPolicy | NFS/SMB/S3 | Existing NAS workloads, dual-access needs |
| S3-native + Glue | Born-in-S3 | S3 Events | S3 only | Cloud-native data, new applications |
| DataSync + S3 | Full copy | Scheduled | Source NAS → S3 | Small file sets, simple one-way sync |
| Databricks Unity Catalog | S3 copy required | — | S3/ADLS | Structured/semi-structured lakehouse |

*Zero-copy storage: S3 Access Point reads files in-place from FSx for ONTAP volumes. Processing requires ephemeral file content access in Lambda memory. File bytes are not persisted outside the source FSx for ONTAP volume.

---

## Detailed Comparison

### FSx for ONTAP + S3 Access Point (This Solution)

**How it works:**
- Files remain on FSx for ONTAP volumes
- S3 Access Point provides read access to analytics services
- FPolicy detects file create/modify/delete events
- Lambda processes files via S3 AP, Bedrock classifies, metadata stored in S3 Tables (Iceberg)

**Strengths:**
- No data duplication for storage — metadata-only external footprint
- Users continue NFS/SMB access; analytics access same data via S3 AP
- FPolicy provides real-time event detection (no polling)
- Native integration with AWS analytics stack (Athena, EMR, OpenSearch)
- ONTAP features (SnapMirror, FlexClone, storage efficiency) remain available

**Limitations & Considerations:**
- S3 AP is used read-only in this pipeline (**writes are supported**) — no write-back from analytics tools to FSx for ONTAP volumes
- S3 Access Point does **not support S3 Event Notifications** (cannot auto-trigger Snowpipe, EventBridge rules, etc.)
- FPolicy adds latency overhead (~1–5ms per file operation) to NAS clients
- Lambda processing: file content passes through Lambda memory (ephemeral, not persisted, but not "zero data movement" at the processing layer)
- Bedrock classification accuracy varies by file type, language mix, and domain terminology (PoC accuracy on test dataset; production accuracy varies)
- Requires FSx for ONTAP as the storage platform

---

### S3-Native + Glue Crawlers

**How it works:**
- Data resides in S3 from the start (born-in-cloud)
- Glue crawlers discover schema; Athena/EMR query directly
- S3 Event Notifications trigger processing pipelines

**Strengths:**
- Simplest architecture for data already in S3
- Full S3 Event Notifications support (Snowpipe, EventBridge, Lambda triggers)
- No file system overhead — pure object storage
- Broadest ecosystem support (every analytics tool reads S3)

**When this is the better choice:**
- Data is born in cloud (application logs, IoT streams, exports)
- No existing NAS access requirements
- Need S3 Event Notifications for downstream automation
- Object-native workloads (large files, append-only, no random access)

**Limitations:**
- Requires full data migration for existing NAS workloads
- No file-system semantics (permissions, directory structure, file locks)
- Glue crawlers are batch-oriented (not real-time)
- Ongoing sync complexity if NAS is still the primary data source

---

### DataSync + S3

**How it works:**
- AWS DataSync copies files from NAS to S3 on a schedule
- Standard S3 processing pipeline (Glue, Athena, etc.) operates on the copy

**Strengths:**
- Simple one-way sync with minimal configuration
- Works with any NFS/SMB source (not limited to FSx for ONTAP)
- Good for small-to-medium file sets with infrequent changes

**When this is the better choice:**
- Small file counts (<10,000 files) where event-driven detection is overkill
- Infrequent changes (batch updates, nightly sync is acceptable)
- Need write-back capability to S3 (analytics can write output to S3)
- Source NAS is not FSx for ONTAP

**Limitations:**
- Full data duplication (doubles storage cost)
- Sync delay — not real-time (scheduled or manual trigger)
- No event-driven detection of individual file changes
- Ongoing data transfer costs

---

### Databricks Unity Catalog

**How it works:**
- Data must reside in cloud object storage (S3, ADLS, GCS)
- Unity Catalog provides governance over structured/semi-structured lakehouse tables
- NAS files must be copied to S3 first

**Strengths:**
- Excellent for structured analytics and ML workloads
- Strong governance (row/column-level security, lineage, audit)
- Large ecosystem of Spark-based tools and connectors

**Limitations:**
- Requires S3 copy for NAS-resident files
- Focused on tabular data — limited native support for unstructured file classification
- Foreign Catalog integration for S3 Tables is still evolving
- Additional DBU costs for compute

---

## When NOT to Use the FSx for ONTAP + S3 AP Approach

This solution is **not the best fit** when:

| Scenario | Better Alternative | Reason |
|----------|-------------------|--------|
| Data is born in S3 (no NAS origin) | S3-native + Glue | No benefit from zero-copy storage if data is already in S3 |
| Object-native workloads (large media, append-only logs) | S3 + S3 Events | S3 Event Notifications enable Snowpipe/EventBridge triggers |
| Small file counts (<5,000 files, infrequent changes) | DataSync + S3 | DataSync is simpler to operate; event-driven detection is unnecessary |
| Need write-back from analytics to storage | S3 Standard | S3 AP is used read-only in this pipeline (writes supported); cannot write results back to FSx for ONTAP |
| Structured/tabular data only | Databricks / Glue | Unity Catalog or Glue Data Catalog handles tabular data without AI classification |
| No existing FSx for ONTAP deployment | Evaluate cost of FSx for ONTAP adoption first | Solution assumes FSx for ONTAP is already in place or planned |

---

## ONTAP Platform Features Used by This Solution

| Feature | Role in Solution |
|---------|-----------------|
| S3 Access Point | Read-only file access from Lambda/analytics services (zero-copy storage) |
| FPolicy | Real-time file event detection (create/modify/delete/rename); adds ~1–5ms latency |
| SnapMirror | Cross-region replication for DR and multi-region deployments |
| FlexClone | Space-efficient copies for testing/dev environments |
| Storage Efficiency | Deduplication + compression reduce effective storage costs |
| Multi-Protocol | NFS + SMB + S3 on same data — users and analytics coexist |

---

## Decision Framework

```
Is data already born in S3 with no NAS access needs?
  → Yes: Use S3-native + Glue (simplest)
  → No: Continue

Is the file count small (<5K) with infrequent changes?
  → Yes: Consider DataSync + S3 (simpler operations)
  → No: Continue

Do you need S3 Event Notifications (Snowpipe, EventBridge triggers)?
  → Yes: S3-native is required; S3 AP does not support Event Notifications
  → No: Continue

Is FSx for ONTAP already deployed (or planned)?
  → Yes: FSx for ONTAP + S3 AP approach — zero-copy storage, FPolicy-driven
  → No: Evaluate whether FSx for ONTAP adoption is justified for other reasons first

Do analytics tools need to write results back to storage?
  → Yes: S3 Standard (S3 AP is used read-only in this pipeline (writes supported))
  → No: FSx for ONTAP + S3 AP is compatible
```

---

## Limitations & Considerations (This Solution)

| Item | Detail |
|------|--------|
| S3 AP read-only | Analytics services cannot write back to FSx for ONTAP volumes via S3 AP |
| No S3 Event Notifications | Cannot trigger Snowpipe, EventBridge rules, or S3 bucket notifications via S3 AP |
| FPolicy latency | ~1–5ms added per file operation on NAS clients |
| Lambda ephemeral access | File content passes through Lambda memory during processing; not persisted but not "zero data movement" |
| Bedrock accuracy | PoC accuracy on test dataset; production accuracy varies by file type, language mix, and domain terminology |
| S3 Tables maturity | GA Dec 2024 — some cross-platform integrations (Snowflake Iceberg catalog, Databricks Foreign Catalog) still evolving |
| Athena cold start | First query after idle period: 3–5s additional latency |
| OpenSearch warm-up | Serverless OCU allocation may take 10–30s after idle period |

---

*Last updated: 2026-06. All comparisons based on publicly available documentation and PoC testing.*

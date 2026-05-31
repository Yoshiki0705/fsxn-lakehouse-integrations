# Iceberg Metadata Catalog for Unstructured Data: Bridging FSx for ONTAP and Modern Data Platforms

🌐 [日本語](../ja/iceberg-metadata-catalog.md) | English

## Executive Summary

This document defines an architecture pattern that uses **Apache Iceberg as a metadata catalog** for unstructured data stored on FSx for ONTAP. Rather than moving raw files into a data platform, we keep the actual data on ONTAP (preserving deduplication, multi-protocol access, and Snapshot capabilities) while managing metadata — file paths, tags, AI-generated classifications, and vector embeddings — in managed Iceberg tables accessible from any analytics engine.

**Key Technologies**:
- **Amazon S3 Tables** — Fully managed Apache Iceberg tables with automatic compaction, 3x query performance, Iceberg REST endpoint
- **FSx for ONTAP S3 Access Points** — S3-compatible access to ONTAP volumes (read path for AI/analytics)
- **S3 Metadata** — Automatic Iceberg table generation from S3 object metadata (alternative path via DataSync)
- **Iceberg REST Catalog** — Cross-platform access from Databricks, Snowflake, Spark, and other engines

## Core Concept: Hot Metadata × Cold Data Separation

```
┌─────────────────────────────────────────────────────────────────────┐
│  HOT: Metadata Layer (Apache Iceberg on S3 Tables)                   │
│  - File path, tags, classification, embeddings                       │
│  - Fast SQL queries (Athena, Redshift, EMR)                          │
│  - Vector similarity search (OpenSearch)                             │
│  - Cross-platform access via Iceberg REST endpoint                   │
│  - Governed by Lake Formation / Horizon Catalog                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ file_path reference
┌──────────────────────────────▼──────────────────────────────────────┐
│  COLD: Data Layer (FSx for ONTAP)                                    │
│  - Actual files: PDF, images, CAD, video, audio, logs                │
│  - Deduplication (50-70% storage reduction)                          │
│  - Multi-protocol: NFS/SMB (existing workflows) + S3 AP (AI/analytics)│
│  - Snapshot: consistent point-in-time for batch AI processing        │
│  - FabricPool: automatic tiering to lower-cost storage               │
└─────────────────────────────────────────────────────────────────────┘
```

**Why this separation?**

| Concern | Metadata Layer (S3 Tables) | Data Layer (FSx for ONTAP) |
|---------|---------------------------|---------------------------|
| Query speed | Sub-second (Iceberg optimized) | N/A (not queryable) |
| Storage efficiency | Minimal (~1GB per 100K files) | Dedup + compression (50-70% savings) |
| Multi-engine access | ✅ Iceberg REST endpoint | ✅ S3 AP + NFS/SMB |
| Governance | Lake Formation / Horizon | S3 AP policy + ONTAP ACLs |
| AI processing | Embeddings stored here | Raw files read from here |
| Cost | ~$5-15/month (metadata only) | Depends on data volume |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Governance Layer                                   │
│                                                                      │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │Lake Formation│  │Snowflake Horizon │  │Databricks Unity      │  │
│  │LF-Tags       │  │Row Access Policy │  │Catalog (External)    │  │
│  │Column/Row    │  │Dynamic Masking   │  │                      │  │
│  └──────────────┘  └──────────────────┘  └──────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              Metadata Layer (Apache Iceberg)                          │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ S3 Tables (table bucket) — Primary Metadata Store             │   │
│  │                                                               │   │
│  │ Schema:                                                       │   │
│  │   file_id, file_path, file_name, file_type, file_size         │   │
│  │   created_at, modified_at, source_volume, access_point_arn    │   │
│  │   tags (map), classification, confidence_score                │   │
│  │   embedding_vector (binary), summary                          │   │
│  │   sensitivity_level, has_pii, anonymized_path                 │   │
│  │                                                               │   │
│  │ Access: Iceberg REST endpoint → Databricks, Snowflake, Spark  │   │
│  │ Governance: SageMaker Lakehouse + Lake Formation              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              Event & Processing Layer                                 │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Real-time Path: FPolicy → Fargate → SQS → Lambda            │    │
│  │   (file create/modify/delete → metadata sync within 5 min)   │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ AI Enrichment: Step Functions → Bedrock/Cortex/Mosaic AI     │    │
│  │   (classification, embedding, summarization, PII detection)  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Batch Path (Alternative): DataSync → S3 → S3 Metadata       │    │
│  │   (automatic Iceberg table from S3 object metadata)          │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              Storage Layer                                            │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ FSx for ONTAP                                                │    │
│  │   • S3 Access Point → AI/Analytics read access               │    │
│  │   • NFS/SMB → Existing workflows (CAD tools, editors)        │    │
│  │   • Deduplication + Compression (50-70% savings)             │    │
│  │   • Snapshot → Consistent batch processing input             │    │
│  │   • FPolicy → Real-time file event detection                 │    │
│  │   • FabricPool → Automatic cold data tiering                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ On-premises ONTAP (optional)                                  │    │
│  │   • SnapMirror → FSx for ONTAP (block-level replication)     │    │
│  │   • FlexCache S3 AP (future: ONTAP 9.18.1 on-prem ready)    │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Platform-Specific Implementation Paths

### AWS Native Path (Athena + Lake Formation + Bedrock)

**Best for**: Organizations already invested in AWS-native analytics stack.

```
FSx for ONTAP ──S3 AP──→ Bedrock KB (RAG, Vision)
                    │
                    └──→ Lambda (metadata extraction)
                              ↓
                    S3 Tables (Iceberg metadata)
                              ↓
                    Glue Catalog (SageMaker Lakehouse)
                              ↓
                    Lake Formation (LF-Tags governance)
                              ↓
                    Athena / EMR / Redshift Spectrum (queries)
```

**Key advantages**:
- FSx S3 AP direct access from Athena and Bedrock (no S3 copy needed for reads)
- Lake Formation enforces governance across all AWS analytics engines
- S3 Tables auto-compaction eliminates table maintenance
- Bedrock Knowledge Base indexes metadata for natural language search

**Governance model**: Lake Formation LF-Tags applied to metadata table columns/rows. Example tags: `department=engineering`, `sensitivity=confidential`, `classification=medical_image`.

> **Region availability note**: Verify S3 Tables availability in your target region before deployment. If S3 Tables is not yet available in ap-northeast-1, use Glue Catalog with self-managed Iceberg tables as fallback (same schema, manual compaction required). Migration to S3 Tables is straightforward once available.

### Databricks Path (Unity Catalog + Mosaic AI)

**Best for**: Organizations with existing Databricks investment (UC, Delta Lake, MLflow).

```
S3 Tables ──Iceberg REST endpoint──→ Databricks External Catalog
                                              ↓
                                    Unity Catalog governance
                                              ↓
                                    Spark SQL / Mosaic AI queries
                                              ↓
                                    Vector Search (similar file discovery)
```

**Key advantages**:
- Iceberg REST endpoint enables direct access to S3 Tables metadata from Databricks
- Mosaic AI for automated image/document classification pipeline
- Vector Search for embedding-based similar file discovery
- Delta Sharing for cross-organization metadata sharing

**Current constraint**: Unity Catalog session policy does not recognize S3 AP ARN format for direct file access. Workaround: metadata queries via Iceberg REST + file access via Bedrock/Lambda.

**Vector Search integration**: For Databricks-first organizations, embeddings can be synced from S3 Tables to Mosaic AI Vector Search Index for native Databricks similarity search. This provides tighter integration with Databricks notebooks and Model Serving compared to OpenSearch Serverless.

**Governance model**: Unity Catalog External Catalog + Lake Formation supplement for cross-engine enforcement.

### Snowflake Path (Horizon Catalog + Cortex AI)

**Best for**: Organizations with existing Snowflake investment (Cortex AI, Data Sharing, Horizon).

```
FSx for ONTAP ──S3 AP Stage──→ COPY INTO → Managed Iceberg Table
                                                    ↓
                                          Cortex AI (PARSE_DOCUMENT, Vision)
                                                    ↓
                                          Horizon Iceberg REST Catalog
                                                    ↓
                                          External engines (Spark, Databricks)
                                          with Row Access Policy enforcement
```

**Key advantages**:
- Cortex AI processes unstructured data directly (PARSE_DOCUMENT, COMPLETE, Vision)
- Horizon Catalog enforces governance on external engine access (Row Access Policy, Masking)
- STORAGE_REQUEST_HISTORY audits external engine access
- Secure Data Sharing for zero-copy cross-organization metadata sharing

**Current constraint**: TO_FILE fails on S3 AP stages (engineering investigation in progress). Workaround: COPY FILES to internal stage for Vision AI processing.

**Governance model**: Horizon Catalog Row Access Policies + Dynamic Masking, enforced on both Snowflake and external engines.

---

## Decision Matrix: Metadata Layer Selection

| Criteria | S3 Tables | Snowflake Managed Iceberg | Glue Catalog (self-managed Iceberg) |
|----------|-----------|--------------------------|-------------------------------------|
| **Management overhead** | None (fully managed) | None (fully managed) | Medium (manual compaction, snapshot expiry) |
| **Query performance** | 3x vs self-managed | Comparable | Baseline |
| **Cross-platform access** | ✅ Iceberg REST endpoint | ✅ Horizon REST Catalog | ✅ Glue Catalog + Iceberg |
| **Governance** | Lake Formation + SageMaker Lakehouse | Horizon (Row Access Policy, Masking) | Lake Formation |
| **External engine enforcement** | ✅ (via Lake Formation) | ✅ (via Horizon) | ✅ (via Lake Formation) |
| **Auto-compaction** | ✅ Built-in | ✅ Built-in | ❌ Manual or Glue job |
| **Cost (100K records)** | ~$5-15/month | Included in Snowflake compute | ~$5/month + maintenance compute |
| **Region availability** | Expanding (check current) | All Snowflake regions | All AWS regions |
| **Best for** | AWS-native + multi-engine | Snowflake-first + external sharing | Maximum flexibility |

**Recommendation**: Start with S3 Tables for AWS-native path. Add Snowflake Managed Iceberg if Horizon governance is required for external engines. Use Glue Catalog as fallback for regions where S3 Tables is not yet available.

---

## Event Detection: FPolicy Pipeline vs DataSync + S3 Metadata

| Aspect | FPolicy Pipeline | DataSync + S3 Metadata |
|--------|-----------------|----------------------|
| **Latency** | ~5 seconds (real-time) | Minutes to hours (batch) |
| **Data copy required** | No (metadata only) | Yes (full file copy to S3) |
| **Storage cost** | Minimal (metadata in S3 Tables) | Significant (S3 copy of all files) |
| **Setup complexity** | Medium (FPolicy Server + Lambda) | Low (DataSync task + enable S3 Metadata) |
| **Metadata richness** | Custom (any field extractable) | Standard S3 object metadata + custom tags |
| **AI enrichment** | Separate pipeline (Step Functions) | Separate pipeline (same) |
| **Best for** | Real-time catalog, no S3 copy budget | Batch processing, S3 already required |

**Recommendation**: Use FPolicy pipeline as primary path (eliminates S3 copy cost). Use DataSync + S3 Metadata as supplementary path when S3 copy is already required for other reasons (e.g., Bedrock KB data source, cross-region access).

---

## AI Enrichment Pipeline

### Processing Modes by File Type

| File Type | AI Service | Output | Latency | Cost (per file) |
|-----------|-----------|--------|---------|-----------------|
| PDF/Document | Bedrock Claude (summarize, extract) | summary, entities, classification | 5-30s | $0.01-0.05 |
| Image | Bedrock Claude Vision (classify, describe) | description, classification, objects | 3-10s | $0.01-0.03 |
| Audio | Transcribe → Bedrock (summarize) | transcript, summary, sentiment | 30-120s | $0.02-0.10 |
| Video | Frame extraction → Vision (sample) | scene descriptions, classifications | 60-300s | $0.05-0.50 |
| CAD/3D | Metadata extraction only | dimensions, layers, components | 1-5s | $0.001 |
| Log/Sensor | Pattern detection (Bedrock) | anomalies, patterns, statistics | 5-15s | $0.01-0.03 |

### Embedding Generation

All file types receive a 1536-dimension vector embedding (Amazon Titan Embeddings V2) based on:
- Documents: Full text content
- Images: AI-generated description
- Audio: Transcription text
- Video: Concatenated scene descriptions

Embeddings enable **similarity search**: "Find files similar to this one" via kNN on OpenSearch Serverless or brute-force scan on the Iceberg embedding column.

### PII Detection and Anonymization

```
File → PII Detection (Comprehend / Bedrock)
         │
         ├─ No PII → has_pii=false, anonymization_status="not_required"
         │
         └─ PII detected → has_pii=true
                              ↓
                    Anonymization Pipeline
                    (face blur, PII redaction, DICOM de-id)
                              ↓
                    anonymized_path = path to clean version
                    anonymization_status = "completed"
```

**Data Clean Room pattern**: Original metadata table (restricted access) + Clean metadata table (broader access, anonymized files only). Lake Formation enforces separation.

---

## Cost Estimation

### Scenario: 10TB unstructured data, 100K files, 1000 changes/day

| Component | Monthly Cost | Notes |
|-----------|-------------|-------|
| **S3 Tables (metadata storage)** | ~$5 | ~1GB for 100K records |
| **S3 Tables (requests)** | ~$10 | Writes from Lambda + reads from queries |
| **Lambda (metadata sync)** | ~$5 | 1000 events/day × 200ms × 128MB |
| **Lambda (AI enrichment)** | ~$50 | 100 new files/day × 30s × 512MB |
| **Bedrock (AI processing)** | ~$100-500 | Depends on model choice and volume |
| **Step Functions** | ~$5 | State transitions |
| **SQS** | ~$1 | Message processing |
| **OpenSearch Serverless (optional)** | ~$350 | 2 OCU minimum for vector search |
| **FSx for ONTAP (existing)** | — | Already provisioned for primary storage |
| | | |
| **Total (without vector search)** | **~$175-575/month** | |
| **Total (with vector search)** | **~$525-925/month** | |

### Cost comparison vs alternatives

| Approach | Monthly Cost (10TB) | Metadata Latency | Governance |
|----------|-------------------|-----------------|------------|
| **This architecture (FPolicy + S3 Tables)** | $175-575 | ~5 seconds | Lake Formation / Horizon |
| S3 full copy + Glue Crawler | $230 (S3) + $50 (Glue) | Hours | Lake Formation |
| S3 full copy + S3 Metadata | $230 (S3) + $15 (Metadata) | Minutes | Lake Formation |
| Custom DynamoDB catalog | $50-200 | Seconds | Custom IAM |

---

## Success KPIs

| KPI | Before (Current State) | After (This Architecture) | Measurement |
|-----|----------------------|--------------------------|-------------|
| **Data discovery time** | Days (manual search, ask colleagues) | Seconds (SQL metadata search, natural language) | Time from "I need X" to "I found X" |
| **Sharing lead time** | Weeks (copy, approve, transfer) | Immediate (Iceberg REST + governance policy) | Time from share request to access granted |
| **AI processing throughput** | Manual (human selects files, runs tools) | Automated (FPolicy → Step Functions pipeline) | Files processed per day without human intervention |
| **Storage cost** | Baseline (S3 full copy + no dedup) | 30-70% reduction (ONTAP dedup + S3 copy elimination) | Monthly storage spend |
| **Governance coverage** | 0% (no metadata, no access control on unstructured data) | 100% (all files cataloged, LF-Tags/Horizon applied) | % of files with classification + access policy |
| **Cross-org data reuse** | Near zero (siloed copies) | Measurable (Delta Sharing / Secure Data Sharing metrics) | Unique datasets accessed by >1 organization |

---

## Industry Use Case Examples

| Industry | Use Case | Key Files | AI Processing | Business Value |
|----------|----------|-----------|--------------|----------------|
| **Manufacturing** | Design document similarity search | CAD (DWG, STEP), blueprints (PDF) | Embedding → similarity search | Past design reuse rate ↑, R&D time ↓ |
| **Financial Services** | Contract auto-classification + compliance search | Contracts (PDF), statements | Entity extraction, classification | Compliance search time: days → seconds |
| **Healthcare** | DICOM image anonymized sharing for research | Medical images (DICOM), reports (PDF) | DICOM de-id, PII redaction | Research dataset construction without privacy risk |
| **Media & Entertainment** | Video asset tag search + content reuse | Video (MP4), images (RAW, JPEG) | Scene classification, object detection | Content reuse efficiency ↑, licensing compliance |
| **Public Sector** | Surveillance footage governance + anomaly detection | Video (H.264), sensor logs | Face detection (for blur), anomaly detection | Citizen privacy protection + security |
| **Energy / Utilities** | IoT sensor log pattern detection | Sensor data (CSV, Parquet), maintenance logs | Anomaly detection, predictive maintenance | Unplanned downtime ↓, maintenance cost ↓ |

---

## Data Sovereignty, Encryption, and Audit Retention

### Data Sovereignty

| Component | Location | Cross-region Transfer |
|-----------|----------|---------------------|
| Raw files (FSx for ONTAP) | Same region as FSx file system | None (S3 AP same-region only) |
| Metadata table (S3 Tables) | Same region (configurable) | None (query results stay in region) |
| AI processing (Bedrock/Lambda) | Same region | None (processing in-region) |
| Governance (Lake Formation) | Same region | Cross-account possible (same region) |

**Guarantee**: Both metadata and raw data remain in the same AWS region. No cross-border data transfer occurs in the default architecture. This satisfies data residency requirements for regulated industries.

### Encryption at Rest

| Layer | Encryption | Key Management |
|-------|-----------|---------------|
| FSx for ONTAP | SSE-FSX (AES-256) | AWS KMS managed, transparent |
| S3 Tables | SSE-S3 or SSE-KMS | Customer choice (KMS recommended for compliance) |
| SQS messages | SSE-SQS or SSE-KMS | AWS managed or customer KMS |
| Lambda environment | Encrypted by default | AWS managed |
| OpenSearch Serverless | Encrypted by default | AWS managed or customer KMS |

### Audit Log Retention

| Regulation | Required Retention | Recommended Configuration |
|-----------|-------------------|--------------------------|
| HIPAA (Healthcare) | 6-7 years | CloudTrail: S3 archive (7 years), Lake Formation logs: 7 years |
| SOX / Financial | 5-7 years | CloudTrail: S3 archive (7 years), query logs: 5 years |
| GDPR (EU) | Duration of processing + reasonable period | CloudTrail: 3 years minimum, deletion audit: indefinite |
| General enterprise | 1-3 years | CloudTrail: 90 days hot + S3 archive (3 years) |

**Implementation**: Configure CloudTrail to deliver logs to S3 with lifecycle policy matching retention requirements. Lake Formation access logs follow the same pattern.

---

## ONTAP Snapshot and FlexClone for AI Processing

### Pattern: Snapshot-based Batch AI Processing

```
1. Create Snapshot before AI batch processing
   → Guarantees consistent point-in-time view
   → Files cannot change during processing

2. AI pipeline reads from Snapshot (via S3 AP)
   → No interference with production NFS/SMB workloads
   → Deterministic results (same input = same output)

3. After processing completes, Snapshot can be deleted
   → Zero additional storage cost (ONTAP Snapshot is space-efficient)
```

**Use case**: Nightly AI enrichment batch that processes all new files. Snapshot ensures no file is modified mid-processing, preventing partial reads or inconsistent classifications.

### Pattern: FlexClone for AI Sandbox

```
1. FlexClone the production volume
   → Instant (metadata-only operation)
   → Zero additional storage (copy-on-write)

2. AI team experiments on FlexClone
   → Can modify, delete, reorganize files freely
   → No impact on production volume

3. Validated results written to metadata table
   → FlexClone deleted after experiment
```

**Use case**: Data science team wants to test new classification models on production data without risk. FlexClone provides a full copy in seconds with zero storage overhead.

---

## Periodic Full-Scan Reconciliation

### Why It's Needed

FPolicy asynchronous mode may drop events under extreme load (>10,000 events/second sustained). Additionally, files created before FPolicy was enabled won't have metadata records. A periodic reconciliation ensures the metadata table stays complete.

### Design

```
EventBridge Schedule (daily at 02:00 UTC)
  → Step Functions: FullScanReconciliation
    → Lambda: ListObjectsV2 on FSx S3 AP (paginated)
    → Lambda: Compare with Metadata_Table (anti-join)
    → Lambda: Insert missing records (enrichment_status = "pending")
    → CloudWatch Metric: reconciliation_gap_count
```

### Configuration

| Parameter | Default | Notes |
|-----------|---------|-------|
| Schedule | Daily 02:00 UTC | Low-traffic window |
| Scope | All volumes with FPolicy enabled | Configurable per volume |
| Batch size | 1000 objects per Lambda invocation | Pagination |
| Alert threshold | gap_count > 100 | Indicates FPolicy event loss |

---

## Snowflake Cortex Search for Natural Language Metadata Discovery

### Pattern: Cortex Search on Metadata Table

```
Managed Iceberg Table (metadata)
  → Cortex Search Service (index on: summary, tags, classification, file_name)
    → Natural language query: "Find all engineering drawings from 2025 related to pump design"
      → Returns: ranked list of file_path + metadata
```

### Configuration

```sql
-- Create Cortex Search service on metadata table
CREATE OR REPLACE CORTEX SEARCH SERVICE metadata_search
  ON unstructured_file_metadata
  WAREHOUSE = 'COMPUTE_WH'
  TARGET_LAG = '1 hour'
  ATTRIBUTES = 'file_type, classification, sensitivity_level'
  COLUMNS = 'summary, file_name, tags'
  AS (
    SELECT
      file_id,
      file_path,
      file_name,
      file_type,
      classification,
      sensitivity_level,
      summary,
      OBJECT_CONSTRUCT_KEEP_NULL(*) AS tags_json
    FROM unstructured_file_metadata
    WHERE is_deleted = FALSE
      AND enrichment_status = 'completed'
  );
```

### Advantages over SQL-only Search

| Aspect | SQL (Athena/Redshift) | Cortex Search |
|--------|----------------------|---------------|
| Query type | Exact match, LIKE, regex | Natural language, semantic |
| Setup | None (standard SQL) | Cortex Search service creation |
| Relevance ranking | Manual (ORDER BY) | Automatic (ML-based) |
| Fuzzy matching | Limited | Built-in |
| Best for | Structured filters (date, type, tag) | Discovery ("find documents about X") |

**Recommendation**: Use SQL for structured queries (known filters) and Cortex Search for discovery (unknown or fuzzy requirements). Both access the same underlying Iceberg metadata table.

---

## Anonymization Quality Assurance Process

### Challenge

AI-based PII detection is not 100% accurate. False negatives (missed PII) create compliance risk. False positives (over-redaction) reduce data utility.

### Recommended Process

```
┌─────────────────────────────────────────────────────────┐
│ Stage 1: Automated PII Detection                         │
│   Comprehend + Bedrock → has_pii flag                    │
│   Expected accuracy: 95-98%                              │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│ Stage 2: Automated Anonymization                         │
│   Face blur, PII redaction, DICOM de-id                  │
│   Output: anonymized file + anonymized_path              │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│ Stage 3: Human Sampling Review (Weekly)                   │
│   - Random 5% sample of anonymized files                 │
│   - Reviewer checks: PII fully removed? Over-redacted?   │
│   - Feedback loop → model fine-tuning                    │
│   - Escalation: if miss rate > 2%, pause pipeline        │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│ Stage 4: Audit Trail                                     │
│   - Who reviewed, when, what decision                    │
│   - Pipeline version that processed each file            │
│   - Retention: matches regulatory requirement            │
└─────────────────────────────────────────────────────────┘
```

### DICOM De-identification Methods

| Method | HIPAA Compliance | Data Utility | Complexity |
|--------|-----------------|-------------|-----------|
| **Safe Harbor** | ✅ (18 identifiers removed) | Lower (aggressive removal) | Low |
| **Expert Determination** | ✅ (statistical verification) | Higher (selective removal) | High |
| **Hybrid** (recommended) | ✅ | Medium-High | Medium |

**Recommendation**: Start with Safe Harbor for initial deployment (simpler, guaranteed compliance). Transition to Expert Determination for research datasets where data utility is critical.

---

## Constraints and Limitations

| Constraint | Impact | Mitigation |
|-----------|--------|-----------|
| FSx S3 AP: No conditional writes | Cannot write Iceberg tables directly to FSx S3 AP | Metadata on S3 Tables (not on FSx); raw files on FSx |
| FSx S3 AP: No S3 Event Notifications | Cannot use native S3 events for change detection | FPolicy provides equivalent real-time detection |
| FSx S3 AP: ListObjectsV2 latency | Slow directory listing (30-80x vs native S3) | Metadata table eliminates need for LIST operations |
| Databricks: Session policy blocks S3 AP | Cannot access FSx files directly from UC | Access metadata via Iceberg REST; files via Bedrock/Lambda |
| Snowflake: TO_FILE fails on S3 AP | Vision AI requires internal stage workaround | COPY FILES to internal stage; PARSE_DOCUMENT works directly |
| S3 Tables: Region availability | Not available in all regions | Fallback to Glue Catalog + self-managed Iceberg |

See [Compatibility Matrix](compatibility-matrix.md) for detailed platform × format × mode verification status.

---

## Relationship to Other Documents

| Document | Relationship |
|----------|-------------|
| [Zero-Copy Unstructured Data Governance](zero-copy-media-governance.md) | Storage optimization options (A/B/C/D) — this document focuses on the metadata catalog layer |
| [Compatibility Matrix](compatibility-matrix.md) | Detailed verification status for each platform × format × mode |
| [Governance and Compliance](governance-and-compliance.md) | Horizon Catalog, Lake Formation, audit logging details |
| [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | Monitoring pipeline for FSx for ONTAP audit logs |

---

## Persona Review Summary

| Persona | Key Recommendation | Incorporated |
|---------|-------------------|-------------|
| **AWS Iceberg SA** | S3 Tables as primary metadata store; Iceberg REST for cross-platform. S3 Metadata as supplementary path. | ✅ DD-1, Architecture |
| **Databricks SA** | External Catalog via Iceberg REST; Mosaic AI for enrichment; Vector Search for discovery. Session policy workaround documented. | ✅ Databricks Path, Constraints |
| **Snowflake PMM** | Horizon Catalog for external engine governance; Cortex AI pipeline; STORAGE_REQUEST_HISTORY audit. | ✅ Snowflake Path, Governance |
| **Storage Specialist** | Hot metadata × cold data separation; ONTAP dedup value; Snapshot for batch consistency. | ✅ Core Concept, Architecture |
| **Partner SA** | FPolicy pipeline leverages existing infrastructure; FlexCache S3 AP future path; DataSync alternative. | ✅ Event Detection, Architecture |
| **Public Sector SA** | PII detection + anonymization pipeline; data clean room pattern; audit trail requirements. | ✅ AI Enrichment, Security |
| **Outcome SA** | Customer value reframing (search, share, AI, cost); success KPIs; phased adoption. | ✅ Executive Summary, Cost |

---

## Next Steps

1. **Phase 1**: Deploy S3 Tables table bucket + Iceberg schema (1 week)
2. **Phase 2**: Build FPolicy → SQS → Lambda metadata sync pipeline (1-2 weeks)
3. **Phase 3**: Implement AI enrichment Step Functions workflow (2-3 weeks)
4. **Phase 4**: Configure cross-platform access (Databricks, Snowflake, EMR) (1-2 weeks)
5. **Phase 5**: Build search & discovery features (SQL + vector) (1-2 weeks)
6. **Phase 6**: Implement anonymization pipeline (1-2 weeks)

See [Tasks](../../.kiro/specs/iceberg-unstructured-metadata-catalog/tasks.md) for detailed implementation plan.


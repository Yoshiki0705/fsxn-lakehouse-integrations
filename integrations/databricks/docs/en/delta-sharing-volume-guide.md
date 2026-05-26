# Delta Sharing & Volume Sharing Integration Guide

> **Status**: Architecture Reference — Pattern A/B ready for PoC, Pattern C blocked (awaiting Databricks UC feature development)
>
> **Context**: This guide documents how to expose FSx for ONTAP data to Databricks Unity Catalog governance using Delta Sharing, given that direct UC External Location integration with FSx S3 Access Points is [not currently supported](../../README.md#support-confirmation-2026-05-26).

## Executive Summary

Delta Sharing is a **sharing protocol**, not a transformation engine. It does not convert arbitrary NAS files (images, videos, PDFs) into queryable tables on the fly. Instead, it exposes **prepared tabular datasets** to recipients across organizations, clouds, and platforms.

For FSx for ONTAP integration with Databricks, Delta Sharing provides a practical sharing layer when:
- Databricks acts as a **recipient** rather than the direct storage owner
- Data is first transformed into Delta or Parquet tables
- Unity Catalog Volumes are used for governed non-tabular file access

### Key Principles

1. **Delta Sharing = sharing protocol** (not a transformation engine)
2. **FSx for ONTAP S3 Access Points provide object access** — Delta Sharing requires table semantics
3. **For unstructured data**: The shareable asset is the derived structured representation (metadata, extracted text, captions, embeddings)
4. **For true zero-copy raw file access**: Unity Catalog must support FSx for ONTAP S3 AP as first-class storage locations (feature gap — [reported to Databricks engineering](../../README.md#support-confirmation-2026-05-26))

---

## Three Integration Patterns

### Pattern A: Metadata Table Sharing (Recommended First PoC)

Share a **file catalog** — not the raw files themselves — through Delta Sharing.

```
FSx for ONTAP
  ↓ S3 Access Point (ListObjectsV2)
AWS Lambda / Glue / Step Functions
  ↓ file inventory extraction
Parquet or Delta metadata table (on S3)
  ↓
Delta Sharing (UC Share or OSS Server)
  ↓
Databricks recipient
```

**Shared table schema example:**

| Column | Type | Description |
|--------|------|-------------|
| `file_id` | STRING | Unique identifier |
| `path` | STRING | S3 AP path |
| `s3_ap_key` | STRING | Object key within access point |
| `size_bytes` | BIGINT | File size |
| `last_modified` | TIMESTAMP | Last modification time |
| `etag` | STRING | S3 ETag |
| `file_extension` | STRING | e.g., `.pdf`, `.jpg`, `.parquet` |
| `mime_type` | STRING | MIME type |
| `classification` | STRING | Data classification label |
| `scan_timestamp` | TIMESTAMP | When inventory was taken |

**AWS services used:**
- FSx for ONTAP S3 Access Points — file access via S3 API
- AWS Lambda — small-scale PoC (ListObjectsV2 → metadata extraction)
- AWS Step Functions — batch processing with retry logic
- AWS Glue — ETL to Parquet/Delta, catalog management
- Amazon S3 — metadata table storage (recommended over FSx for ONTAP S3 AP for Delta Sharing compatibility)

**PoC success criteria:** Databricks can query a Delta Sharing table that represents FSx for ONTAP file metadata.

---

### Pattern B: AI-Enriched Table Sharing (RAG / Search / Analytics)

Process unstructured data with AI services, then share the **derived structured output** through Delta Sharing.

```
FSx for ONTAP (raw files: PDFs, images, audio, video)
  ↓ S3 Access Point (GetObject)
AWS AI Services (Textract, Rekognition, Transcribe, Bedrock)
  ↓ extracted text / captions / transcripts / embeddings
Parquet or Delta tables (on S3)
  ↓
Delta Sharing
  ↓
Databricks recipient (Mosaic AI, Vector Search, MLflow)
```

**Shared table schemas by data type:**

#### Documents (PDF/DOCX) — RAG Pipeline

| Column | Type | Description |
|--------|------|-------------|
| `document_id` | STRING | Unique document ID |
| `source_path` | STRING | FSx for ONTAP S3 AP path |
| `page_number` | INT | Page within document |
| `chunk_id` | STRING | Text chunk identifier |
| `text` | STRING | Extracted text content |
| `summary` | STRING | AI-generated summary |
| `embedding` | ARRAY<FLOAT> | Vector embedding |
| `classification` | STRING | Document classification |
| `created_at` | TIMESTAMP | Processing timestamp |

#### Images — Visual Search

| Column | Type | Description |
|--------|------|-------------|
| `image_id` | STRING | Unique image ID |
| `source_path` | STRING | FSx for ONTAP S3 AP path |
| `mime_type` | STRING | image/jpeg, image/png, etc. |
| `width` | INT | Image width (px) |
| `height` | INT | Image height (px) |
| `detected_labels` | ARRAY<STRING> | Object detection results |
| `caption` | STRING | AI-generated description |
| `embedding` | ARRAY<FLOAT> | Visual embedding |
| `created_at` | TIMESTAMP | Processing timestamp |

#### Video/Audio — Transcription & Analysis

| Column | Type | Description |
|--------|------|-------------|
| `video_id` | STRING | Unique video/audio ID |
| `source_path` | STRING | FSx for ONTAP S3 AP path |
| `start_time_sec` | FLOAT | Segment start time |
| `end_time_sec` | FLOAT | Segment end time |
| `transcript` | STRING | Transcribed text |
| `detected_objects` | ARRAY<STRING> | Objects in frame |
| `scene_summary` | STRING | AI scene description |
| `embedding` | ARRAY<FLOAT> | Segment embedding |
| `created_at` | TIMESTAMP | Processing timestamp |

**AWS AI services by data type:**

| Data Type | Primary Service | Secondary | Output |
|-----------|----------------|-----------|--------|
| PDF/Documents | Amazon Textract | Amazon Bedrock (summarize, embed) | Text, tables, forms, summaries |
| Images | Amazon Rekognition | Bedrock multimodal (caption) | Labels, objects, faces, captions |
| Audio | Amazon Transcribe | Bedrock (summarize) | Transcripts, speaker IDs |
| Video | Rekognition Video | Transcribe + Bedrock | Labels, scenes, transcripts |

**PoC success criteria:** Databricks can query AI-enriched metadata (extracted text, labels, summaries, embeddings) through Delta Sharing.

---

### Pattern C: Raw File Sharing via UC Volumes (Requires Databricks Enhancement)

The ideal zero-copy architecture — but currently blocked by UC session policy limitations.

**Desired architecture:**
```
FSx for ONTAP
  ↓ S3 Access Point
Databricks UC External Location (direct)
  ↓
UC External Volume
  ↓
Delta Sharing (Volume Sharing)
  ↓
Databricks recipient (read_files, ai_query, ai_parse_document)
```

**Current reality (requires S3 copy):**
```
FSx for ONTAP
  ↓ DataSync / SnapMirror
Amazon S3 bucket (standard)
  ↓
Databricks UC External Location
  ↓
UC External Volume
  ↓
Delta Sharing (Volume Sharing)
  ↓
Databricks recipient
```

**What works today (with S3 copy):**

```sql
-- Provider side: Create External Volume on S3 (synced from FSx for ONTAP)
CREATE EXTERNAL VOLUME media_files
  LOCATION 's3://fsxn-synced-bucket/unstructured-data/'
  COMMENT 'Images, videos, PDFs synced from FSx for ONTAP';

-- Add Volume to Share
CREATE SHARE IF NOT EXISTS unstructured_data_share
  COMMENT 'Document and media files for partners';

ALTER SHARE unstructured_data_share
  ADD VOLUME catalog.schema.media_files;

-- Grant to recipient
GRANT SELECT ON SHARE unstructured_data_share
  TO RECIPIENT <partner_org>;
```

```sql
-- Recipient side: Access shared files
CREATE CATALOG IF NOT EXISTS shared_media
  FROM SHARE <provider_name>.unstructured_data_share;

-- Query file metadata
SELECT * EXCEPT (content), _metadata
FROM read_files(
  '/Volumes/shared_media/schema/media_files/',
  format => 'binaryFile'
) LIMIT 10;

-- AI analysis on shared images
SELECT path,
  ai_query('databricks-llama-4-maverick',
    'Describe this image:', files => content)
FROM read_files(
  '/Volumes/shared_media/schema/media_files/',
  format => 'binaryFile',
  fileNamePattern => '*.{jpg,png}')
WHERE _metadata.file_size < 5000000;

-- Parse shared PDFs
SELECT path,
  ai_parse_document(content, map('version', '2.0'))
FROM read_files(
  '/Volumes/shared_media/schema/media_files/',
  format => 'binaryFile',
  fileNamePattern => '*.pdf');
```

**Feature requests to Databricks (reported May 2026):**

1. Support S3 Access Point ARNs as first-class storage locations in UC External Locations
2. Update UC session policy generation for FSx for ONTAP S3 AP ARN patterns
3. Allow UC Volumes to use FSx for ONTAP S3 AP as backend storage
4. Generalize UC storage abstractions beyond standard S3 buckets
5. Clarify whether Databricks-to-Databricks Volume Sharing can work with non-bucket S3 AP backends

**PoC success criteria:** Databricks confirms required UC enhancements or provides an alternative supported design for zero-copy FSx for ONTAP access.

---

## Pattern Comparison

| Dimension | Pattern A | Pattern B | Pattern C |
|-----------|-----------|-----------|-----------|
| **Shared asset** | File metadata table | AI-processed tables | Raw files (via UC Volume) |
| **Data on FSx for ONTAP** | Remains (not shared directly) | Remains (derivatives shared) | Remains (accessed directly) |
| **S3 copy required** | Metadata only (~KB) | Derived tables (~MB-GB) | Full file sync (~GB-TB) |
| **PoC complexity** | Low | Medium | Blocked (requires Databricks UC feature development) |
| **Governance** | Delta Sharing + UC | Delta Sharing + UC | UC Volume ACL |
| **AI/ML readiness** | Catalog only | Full (embeddings, RAG) | Full (read_files + ai_query) |
| **Real-time freshness** | Polling-based | Pipeline-dependent | Near real-time (if supported) |
| **Best for** | File discovery, audit | RAG, search, analytics | Direct file processing |

---

## Provider vs Recipient: Role Clarification

| Role | Databricks as Provider | Databricks as Recipient |
|------|---|---|
| **Data location** | Data must be in UC (S3 bucket) | Data can be anywhere (FSx for ONTAP → processing → share) |
| **Governance** | UC governs access | Provider governs; UC applies local policies |
| **Architecture** | FSx for ONTAP → S3 → UC → Share | FSx for ONTAP → Lambda/Glue → Delta table → OSS Delta Sharing Server → Databricks |
| **Complexity** | Simpler (UC handles everything) | More flexible (customer-managed sharing server) |
| **Recommended for** | Databricks-centric organizations | Multi-platform environments |

**Key insight**: When Databricks is the **recipient**, a customer-managed [OSS Delta Sharing server](https://github.com/delta-io/delta-sharing) can expose FSx for ONTAP-backed datasets without requiring data to be in UC first.

---

## Governance Layers

| Layer | Scope | Enforcement Point |
|-------|-------|-------------------|
| FSx file permissions | NFS/SMB ACLs, UNIX users | FSx for ONTAP |
| S3 AP policy | IAM-based, per-access-point | AWS IAM |
| FPolicy | File operation audit/block | ONTAP |
| Delta Sharing | Share-level, recipient-level | Sharing server or UC |
| Unity Catalog | Table/Volume/Column/Row level | Databricks |

For production deployments, define which layer is the **primary governance point** based on organizational requirements.

---

## Data Freshness Considerations

| Freshness Requirement | Recommended Pattern | Mechanism |
|---|---|---|
| Daily | Pattern A or B | Scheduled Glue/Lambda job |
| Hourly | Pattern A or B | Step Functions with CloudWatch Events |
| Near real-time (minutes) | Pattern A + FPolicy | FPolicy → Lambda → incremental update |
| Real-time (seconds) | Pattern C (future) | Direct FSx for ONTAP S3 AP access (requires UC support) |

---

## Recommended PoC Roadmap

```
Phase 1: Pattern A — File Metadata Sharing
├── Lambda function: ListObjectsV2 on FSx for ONTAP S3 AP → Parquet table
├── Delta Sharing: Expose metadata table to Databricks
├── Databricks: Query file catalog, filter by type/date/size
└── Success: Databricks sees governed FSx for ONTAP file inventory

Phase 2: Pattern B — AI-Enriched Sharing
├── Textract: Extract text from PDFs on FSx for ONTAP
├── Bedrock: Generate embeddings and summaries
├── Delta table: Store chunks + embeddings
├── Delta Sharing: Expose to Databricks
└── Success: Databricks Vector Search on FSx for ONTAP-derived content

Phase 3: Pattern C — Blocked (Databricks Feature Development Required)
├── Feature gap reported to Databricks UC engineering (May 2026)
├── Track UC engineering response and timeline
├── If supported: Direct FSx for ONTAP S3 AP → UC Volume → Volume Sharing
└── Until then: Pattern A/B + S3 sync for raw files (only production-ready path)
```

---

## References

- [Work with unstructured data in volumes](https://docs.databricks.com/aws/en/volumes/unstructured-data-tutorial) — Complete tutorial including Volume Sharing
- [What are Unity Catalog volumes?](https://docs.databricks.com/aws/en/volumes/managed-vs-external) — Managed vs External volumes
- [Volume Sharing with Delta Sharing (Video)](https://www.databricks.com/resources/demos/videos/data-sharing/volume-sharing-delta-sharing) — Demo video
- [Create and manage shares](https://docs.databricks.com/en/delta-sharing/create-share.html) — Adding Volumes to Shares
- [Delta Sharing OSS](https://github.com/delta-io/delta-sharing) — Open-source Delta Sharing server
- [FSx for ONTAP S3 Access Points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-access-points.html) — AWS documentation

---

## Related Documents

- [Databricks README](../../README.md) — Full integration status and architecture
- [Analytics & AI Demo Guide](ai-demo-guide.md) — AI/ML capabilities and current status
- [Support Case Summary](../../.private/support-case-00921422-summary-en.md) — UC + S3 AP limitation details (private)

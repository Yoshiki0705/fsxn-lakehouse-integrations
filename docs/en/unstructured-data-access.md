# Unstructured Data Access (Images, Video, Audio, Documents)

🌐 [日本語](../ja/unstructured-data-access.md)

## Overview

Amazon FSx for NetApp ONTAP (FSx for ONTAP) S3 Access Points provide access not only to structured data (Parquet, CSV)
but also to unstructured data such as images, video, audio, and documents.

Enterprise file data accumulated on file servers can be directly accessed by
AI/ML services and analytics platforms without data copying.

## Architecture

### Pattern E: Unstructured Data Processing

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                           │
│  ┌──────────────┐                                                        │
│  │ NFS/SMB      │  ← Users upload files                                 │
│  │ Clients      │    (images, video, documents)                          │
│  └──────┬───────┘                                                        │
│         │                                                                 │
│         ▼                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌─────────────────────────┐  │
│  │ FSx for      │     │ S3 Access    │     │ AI/ML Services           │  │
│  │ ONTAP Volume │────▶│ Point        │────▶│                         │  │
│  │              │     │              │     │ • SageMaker (training)   │  │
│  │ /images/     │     │              │     │ • Bedrock (RAG)         │  │
│  │ /videos/     │     │              │     │ • Rekognition (vision)  │  │
│  │ /documents/  │     │              │     │ • Transcribe (speech)   │  │
│  │ /audio/      │     │              │     │ • Lambda (processing)   │  │
│  └──────────────┘     └──────────────┘     └─────────────────────────┘  │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Pattern F: Lambda File Processing Pipeline

```
FSx for ONTAP Volume (NFS/SMB)
    │
    └── S3 Access Point
            │
            ├── Lambda: Thumbnail generation (image → resize → write back to FSx for ONTAP)
            ├── Lambda: Text extraction (PDF/DOCX → text → write back to FSx for ONTAP)
            ├── Lambda: Audio transcription (WAV/MP3 → Transcribe → text)
            └── Lambda: Metadata extraction (EXIF, video duration, page count)
```

Reference: [AWS Tutorial - Process files serverlessly with Lambda](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-process-files-with-lambda.html)

## Supported File Formats

### Images

| Format | Extension | Use Case |
|--------|-----------|----------|
| JPEG | .jpg, .jpeg | Photos, web images |
| PNG | .png | Screenshots, transparent images |
| TIFF | .tif, .tiff | Medical imaging, scanned documents |
| DICOM | .dcm | Medical imaging (CT, MRI) |
| RAW | .raw, .cr2, .nef | Professional photography |

### Video

| Format | Extension | Use Case |
|--------|-----------|----------|
| MP4 | .mp4 | General purpose video |
| MOV | .mov | Apple ecosystem video |
| AVI | .avi | Legacy video |
| MKV | .mkv | High quality video |
| MPEG-TS | .ts | Surveillance, broadcast |

### Audio

| Format | Extension | Use Case |
|--------|-----------|----------|
| WAV | .wav | High quality audio |
| MP3 | .mp3 | Compressed audio |
| FLAC | .flac | Lossless audio |
| OGG | .ogg | Open format |

### Documents

| Format | Extension | Use Case |
|--------|-----------|----------|
| PDF | .pdf | Business documents |
| DOCX | .docx | Word documents |
| XLSX | .xlsx | Spreadsheets |
| PPTX | .pptx | Presentations |
| TXT/MD | .txt, .md | Text files |

## Use Case Architectures

### 1. AI/ML Training Data (SageMaker + Bedrock)

```
Researcher → NFS mount → FSx for ONTAP Volume → S3 AP → SageMaker Training Job
                          (image dataset)                  (model training)

                                                        → Bedrock Knowledge Base
                                                          (RAG documents)
```

**ONTAP Value:**
- **FlexClone**: Instant dataset copy per experiment (isolation)
- **Snapshot**: Training data versioning (reproducibility)
- **Deduplication**: Storage efficiency for similar image datasets
- **Tiering**: Auto-tier old training data to S3

### 2. Media Asset Management (Rekognition + MediaConvert)

```
Photographer → SMB share → FSx for ONTAP Volume → S3 AP → Rekognition (tagging)
                            (RAW images)                  → MediaConvert (transcode)
                                                          → Lambda (thumbnails)
```

**ONTAP Value:**
- **Snapshot**: Protect originals before editing
- **SnapMirror**: Cross-site media synchronization
- **Compression**: Storage optimization for RAW files
- **Multi-protocol**: NFS (Linux) + SMB (Windows) + S3 (cloud) simultaneous access

### 3. Document Processing Pipeline (Textract + Comprehend)

```
Scanner → NFS → FSx for ONTAP Volume → S3 AP → Textract (OCR)
                (PDF/TIFF)                     → Comprehend (NLP)
                                               → OpenSearch (search index)
```

**ONTAP Value:**
- **SnapLock**: WORM protection for compliance documents
- **Snapshot**: Preserve document state before/after processing
- **Deduplication**: Efficient storage for multiple document versions

### 4. Surveillance Video Analytics

```
Camera → NFS → FSx for ONTAP Volume → S3 AP → Rekognition Video (analysis)
               (MPEG-TS)                      → Kinesis Video (streaming)
                                              → Lambda (alerting)
```

**ONTAP Value:**
- **FabricPool**: Auto-tier old footage to S3 Glacier
- **Snapshot**: Protect footage at incident time
- **Scale**: Efficiently manage hundreds of TB of video data

## Third-Party Platform Unstructured Data Access

### Databricks + Unstructured Data

```python
# Read image files in Databricks notebook
from pyspark.sql.functions import *

# Read image binaries via S3 AP
images_df = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.jpg") \
    .load(f"s3://{S3_AP_ALIAS}/images/")

# Extract image metadata
images_df.select("path", "length", "modificationTime").show()
```

**Constraints:**
- Readable via `binaryFile` format
- Large files (>100MB) retrieved via Multipart Download
- Image processing libraries available in Databricks ML Runtime

### Snowflake + Unstructured Data

```sql
-- Manage unstructured file metadata with Snowflake Directory Table
CREATE OR REPLACE STAGE MEDIA_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<S3AccessPointAlias>/media/'
  DIRECTORY = (ENABLE = TRUE AUTO_REFRESH = FALSE);

-- List files
SELECT * FROM DIRECTORY(@MEDIA_STAGE);

-- Generate pre-signed URL for external applications
-- NOTE: AWS docs state Presign is "Not supported", but testing confirms
-- GET_PRESIGNED_URL works with FSx for ONTAP S3 AP in practice.
SELECT GET_PRESIGNED_URL(@MEDIA_STAGE, 'images/photo001.jpg', 3600);
```

**Constraints:**
- Snowflake cannot directly query unstructured data content
- Directory Table for metadata management
- **Pre-signed URLs work with FSx for ONTAP S3 AP** (despite AWS docs stating "Not supported")
- Snowpark Python UDFs can process images

### Dremio + Unstructured Data

- Dremio primarily targets structured/semi-structured data
- Can catalog unstructured data metadata (path, size, modification time)
- Actual file processing delegated to external services

## Considerations and Constraints

### S3 API Constraints

| Constraint | Impact | Workaround |
|-----------|--------|------------|
| No S3 Select | Cannot partially read within files | Download full file then process |
| No Event Notifications | New file detection not instant | Lambda polling (1-5 min interval) |
| No Object Lock | No S3-level WORM | Use ONTAP SnapLock instead |
| Max object size | 5TB (S3 API limit) | Normal media files unaffected |

### Performance Considerations

| Item | Recommendation | Reason |
|------|---------------|--------|
| Concurrent access | Depends on FSx for ONTAP throughput | 256 MBps to 4096 MBps |
| Large file reads | Use Multipart Download | Parallelization for speed |
| Many small files | Batch processing recommended | ListObjects overhead |
| Write-back | Use Multipart Upload | For files >5MB |

### Security Considerations

- **UNIX permissions**: FSx for ONTAP file permissions enforced via S3 AP
- **AD integration**: Active Directory user mapping for access control
- **Encryption**: FSx for ONTAP at-rest encryption + S3 AP in-transit encryption (TLS)
- **Audit**: ONTAP FPolicy + CloudTrail for complete access logging

### ONTAP Value for Unstructured Data

| Feature | Value for Unstructured Data |
|---------|---------------------------|
| Deduplication | Reduce duplicate frames in similar images/video |
| Compression | High compression ratio for text documents |
| Snapshot | Protect media state before editing |
| FlexClone | Instant AI training dataset copies |
| FabricPool | Auto-tier infrequently accessed media |
| SnapLock | Tamper-proof compliance documents |
| SnapMirror | Cross-site media sync and DR |
| Multi-protocol | NFS + SMB + S3 simultaneous access |

## Next Steps

- [Architecture Overview](architecture.md)
- [Vendor Comparison](vendor-comparison.md)
- [Getting Started](getting-started.md)

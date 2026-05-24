# EMR Serverless Spark Integration

🌐 **English** | [日本語](docs/ja/README.md)

## Overview

Run Spark SQL on FSx for ONTAP data via S3 Access Points using EMR Serverless.
Read, transform, and write-back Parquet — no cluster management required.

## Status: ✅ Functional Verified (2026-05-23)

- Read 10K rows: 6.78s
- GROUP BY aggregation: 2.52s
- Window function: 1.19s
- Write-back to FSxN: 3.61s
- Total Spark execution: 16.35s (job total: 37s including cold start)

## Architecture

```
EMR Serverless (Spark 3.5)
    │
    └── EMRFS (s3:// — natively supports S3 AP aliases)
            │
            └── S3 Access Point (internet-origin) ──→ FSx for ONTAP Volume
```

## Key Finding: EMRFS vs S3A

- **EMRFS (`s3://`)**: Natively supports S3 AP aliases. Use this.
- **S3A (`s3a://`)**: Does NOT work with AP aliases (URL parsing error). Do not use.

## Quick Start

```bash
# 1. Create EMR Serverless application
aws emr-serverless create-application \
  --name "fsxn-spark" --release-label "emr-7.1.0" --type "SPARK"

# 2. Upload PySpark script
aws s3 cp scripts/spark_verification.py s3://<your-bucket>/emr-scripts/

# 3. Run job
aws emr-serverless start-job-run \
  --application-id <app-id> \
  --execution-role-arn <role-arn> \
  --job-driver '{"sparkSubmit":{"entryPoint":"s3://<bucket>/emr-scripts/spark_verification.py"}}'

# 4. Stop application (cost control)
aws emr-serverless stop-application --application-id <app-id>
```

## Important: Parquet Timestamp

Parquet files must use **microsecond** timestamps (not nanosecond). pandas default is nanosecond — Spark cannot read these.

```python
# Generate Spark-compatible Parquet
import pyarrow as pa
ts_array = pa.array(df['timestamp'].values.astype('datetime64[us]'), type=pa.timestamp('us'))
```

## Cost

EMR Serverless charges per vCPU-hour and GB-hour. A 37-second job costs approximately $0.05.
Application has zero cost when stopped.

## Unstructured Data Support

| Format | Support | Access Method | Use Case |
|--------|:---:|--------------|----------|
| Images (JPEG, PNG, TIFF) | ✅ | spark.read.binaryFile | Image classification, quality inspection, ML pipeline |
| Video (MP4, MOV) | ✅ | spark.read.binaryFile | Frame extraction, video analytics |
| Documents (PDF, DOCX) | ✅ | spark.read.binaryFile + UDF | Text extraction, RAG pipeline, document processing |
| Audio (WAV, MP3) | ✅ | spark.read.binaryFile + UDF | Transcription, speech analytics |
| Binary / Archives | ✅ | spark.read.binaryFile | Custom processing, format conversion |

EMR Spark provides full support for unstructured data processing via `spark.read.format("binaryFile")`. Files are read as binary content and can be processed at executor scale using Spark ML pipelines or custom UDFs.

**Patterns:**
1. **Binary file read** — `spark.read.format("binaryFile")` loads images/documents as binary
2. **UDF processing** — Execute image processing, text extraction within Spark UDFs
3. **ML pipeline** — Full Spark ML pipeline for image/audio classification at scale
4. **Metadata ETL** — Manage file metadata as structured tables for processing pipelines

```python
# Read binary files (images, PDFs, etc.)
df = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.pdf") \
    .load("s3://<ap-alias>/documents/")

# File metadata
df.select("path", "length", "modificationTime").show()

# Process with UDF
from pyspark.sql.functions import udf
@udf("string")
def extract_text(content):
    # Custom text extraction logic
    return extracted_text

df.withColumn("text", extract_text(df.content))
```

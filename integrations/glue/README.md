# AWS Glue Integration

🌐 **English** | [日本語](docs/ja/README.md)

## Overview

Build a medallion architecture (Bronze → Silver → Gold) ETL pipeline on Amazon FSx for NetApp ONTAP
using AWS Glue 4.0, GlueContext/DynamicFrame API, and S3 Access Points.
Serverless, scalable data transformation with job bookmarks for incremental processing.

## Architecture

```
EventBridge (Scheduled)
    │
    ▼
Glue Crawler ──→ Glue Data Catalog
    │                    │
    ▼                    ▼
Glue ETL Job         Glue ETL Job
(Bronze→Silver)      (Silver→Gold)
    │                    │
    ▼                    ▼
S3 Access Point (internet origin) ──→ FSx for ONTAP Volume
                                        ├── bronze/
                                        │   ├── transactions/ (Parquet, partitioned)
                                        │   ├── customers/ (CSV)
                                        │   └── events/ (JSON)
                                        ├── silver/
                                        │   ├── transactions/ (Parquet, ZSTD)
                                        │   ├── customers/ (Parquet, ZSTD)
                                        │   └── events/ (Parquet, ZSTD)
                                        └── gold/
                                            ├── daily_summaries/
                                            ├── category_rollups/
                                            └── customer_metrics/
```

## Important: Network Origin

Glue requires S3 Access Points with **internet network origin**.
VPC-only access points will NOT work with Glue ETL jobs.

Reference: [AWS Tutorial - Transform data with Glue](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

## Key Features

- **Glue 4.0** (Spark 3.3+) with GlueContext and DynamicFrame API
- **Job Bookmarks** for incremental processing (no reprocessing of old data)
- **Medallion Architecture**: Bronze (raw) → Silver (cleaned) → Gold (aggregated)
- **Data Quality**: DQDL rules for completeness, uniqueness, value ranges, freshness
- **Scheduled Execution**: EventBridge rule for automated daily runs
- **ZSTD Compression**: Optimal compression for silver/gold Parquet files

## Status: ✅ Functional Verified (2026-05-23)

| Operation | Status | Details |
|-----------|:---:|---------|
| Glue Crawler (schema discovery) | ✅ | Parquet schema auto-detected via S3 AP |
| Glue ETL Job (Bronze → Silver → Gold) | ✅ | 10K rows, 64 seconds total |
| Write-back to FSx S3 AP (Parquet) | ✅ | Gold layer written to S3 AP successfully |
| Job Bookmarks (incremental) | ✅ | Subsequent runs process only new files |

## Quick Start

```bash
# 1. Copy params and fill values
cp params.example.json params.json
# Edit params.json with your FSx for ONTAP details

# 2. Generate sample data
pip install pandas pyarrow boto3
python scripts/generate_sample_data.py

# 3. Upload to FSx for ONTAP via NFS
rsync -avz ./sample_data/bronze/ /mnt/fsxn/bronze/

# 4. Deploy infrastructure
./deploy.sh

# 5. Validate connectivity
python scripts/validate_connectivity.py

# 6. Run full ETL pipeline
python scripts/run_etl_pipeline.py

# 7. (Optional) Run crawler only
python scripts/run_crawler.py --wait
```

## Directory Structure

```
integrations/glue/
├── README.md                          ← This file
├── template.yaml                      ← CloudFormation (Glue + IAM + EventBridge)
├── deploy.sh                          ← Deployment automation
├── params.example.json                ← Parameter template
├── etl/
│   ├── bronze_to_silver.py            ← PySpark ETL: raw → cleaned
│   └── silver_to_gold.py             ← PySpark ETL: cleaned → aggregated
├── quality/
│   └── rules.dqdl                     ← Data Quality rules (DQDL)
├── scripts/
│   ├── generate_sample_data.py        ← Sample data generator (bronze layer)
│   ├── run_crawler.py                 ← Crawler execution + verification
│   ├── run_etl_pipeline.py            ← Full pipeline orchestrator
│   ├── validate_connectivity.py       ← Connectivity validation
│   └── cleanup.sh                     ← Resource cleanup
└── tests/
    └── results/                       ← Pipeline execution results
```

## ETL Transformations

### Bronze → Silver
- Schema normalization (lowercase column names)
- Null handling (type-aware defaults)
- Type casting (timestamps, numerics)
- Deduplication (by primary key)
- Metadata columns (`_etl_timestamp`, `_source_file`)
- Output: Parquet with ZSTD compression

### Silver → Gold
- **Daily Summaries**: transaction counts, amounts, completion rates by date
- **Category Rollups**: revenue distribution, customer counts by category
- **Customer Metrics**: lifetime value, purchase frequency, favorite category

## Data Quality Rules

DQDL rules validate:
- **Completeness**: Critical columns must not be null (≥95-100%)
- **Uniqueness**: Primary keys must be unique
- **Value Ranges**: Amounts > 0, valid enum values
- **Freshness**: Data within expected time windows

## Unstructured Data Support

| Format | Support | Access Method | Use Case |
|--------|:---:|--------------|----------|
| Images (JPEG, PNG, TIFF) | ⚠️ | PySpark binaryFile in ETL job | Metadata extraction, Bedrock/Rekognition pipeline |
| Video (MP4, MOV) | ⚠️ | PySpark binaryFile in ETL job | Metadata cataloging, frame extraction |
| Documents (PDF, DOCX) | ⚠️ | PySpark binaryFile + Comprehend/Bedrock | Text extraction, document classification |
| Audio (WAV, MP3) | ⚠️ | PySpark binaryFile in ETL job | Metadata cataloging, Transcribe pipeline |
| Binary / Archives | ⚠️ | PySpark binaryFile in ETL job | Custom processing, format conversion |

Glue is primarily used for structured data ETL, but can process binary files in ETL jobs and integrate with AI services for document processing. No interactive file browsing is available.

**Patterns:**
1. **Glue Crawler** — Catalog file structure on S3 AP (paths, sizes, timestamps)
2. **PySpark binary read** — Process images/PDFs using `binaryFile` format in ETL jobs
3. **Metadata ETL** — Manage file metadata through Bronze → Silver → Gold pipeline
4. **Event-driven** — FPolicy + EventBridge triggers Crawler on new file detection

```python
# Process file metadata in Glue ETL
from awsglue.context import GlueContext
glueContext = GlueContext(SparkContext.getOrCreate())

# Read file catalog metadata
df = glueContext.create_dynamic_frame.from_catalog(
    database="fsxn_catalog",
    table_name="file_metadata"
).toDF()

# Aggregate unstructured file metadata
df.filter(df.file_type.isin(['image/jpeg', 'application/pdf'])) \
  .groupBy("file_type").count().show()
```

**Recommended alternative for unstructured data on FSx for ONTAP:**
- Use **AWS Lambda** for serverless file processing ([AWS tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-process-files-with-lambda.html))
- Use **Amazon Bedrock** for RAG over documents ([AWS tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html))
- Use **Snowflake** (Directory Table + GET_PRESIGNED_URL) for file catalog and secure URL generation

## Reference Implementation

This integration leverages patterns from:
- [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns)
  - UC1 (legal-compliance): Glue Crawler + S3 AP pattern
  - UC3 (manufacturing-analytics): Glue ETL pipeline
- [AWS Tutorial: Transform data with Glue](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

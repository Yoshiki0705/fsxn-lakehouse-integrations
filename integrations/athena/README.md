# AWS Athena Integration

🌐 **English** | [日本語](docs/ja/README.md)

## Overview

Query data on Amazon FSx for NetApp ONTAP (FSx for ONTAP) directly from Amazon Athena using
Glue Data Catalog and S3 Access Points. Serverless, pay-per-query analytics.

## Architecture

```
Athena (Serverless SQL)
    │
    └── Glue Data Catalog
            │
            ├── Glue Crawler (schema discovery)
            │
            └── S3 Access Point (internet origin) ──→ FSx for ONTAP Volume
                                                        ├── transactions/ (Parquet, partitioned)
                                                        ├── customers/ (CSV)
                                                        ├── events/ (JSON)
                                                        └── gold/ (CTAS output)
```

## Important: Network Origin

Athena requires S3 Access Points with **internet network origin**.
VPC-only access points will NOT work with Athena.

Reference: [AWS Tutorial - Query files with Athena](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

## Status: ✅ Security Verified (2026-05-23)

Benchmark: 54.8 MB/s peak throughput, 5M rows queried in 2.2s (103 MB Parquet, 128 MB/s provisioned).
9/9 negative security tests PASS. CloudTrail audit confirmed.

## Quick Start

```bash
# 1. Copy params and fill values
cp params.example.json params.json
# Edit params.json with your FSx for ONTAP details

# 2. Generate sample data
pip install pandas pyarrow
python scripts/generate_sample_data.py

# 3. Upload to FSx for ONTAP via NFS
./scripts/upload_sample_data.sh

# 4. Deploy infrastructure
./deploy.sh

# 5. Validate connectivity
python scripts/validate_connectivity.py

# 6. Execute queries and collect metrics
python scripts/execute_queries.py
```

## Directory Structure

```
integrations/athena/
├── README.md                          ← This file
├── template.yaml                      ← CloudFormation (Glue + Athena + IAM)
├── deploy.sh                          ← Deployment automation
├── params.example.json                ← Parameter template
├── sql/
│   ├── 01_basic_queries.sql           ← SELECT, GROUP BY, JOIN queries
│   ├── 02_partition_pruning.sql       ← Partition pruning verification
│   └── 03_ctas_writeback.sql          ← CTAS write-back to FSx for ONTAP
├── scripts/
│   ├── generate_sample_data.py        ← Sample data generator
│   ├── upload_sample_data.sh          ← NFS upload script
│   ├── validate_connectivity.py       ← Connectivity validation
│   ├── execute_queries.py             ← Query execution + metrics
│   ├── run_crawler.py                 ← Crawler execution + verification
│   └── cleanup.sh                     ← Resource cleanup
├── tests/
│   └── results/                       ← Query metrics output
└── docs/
    ├── verification-report-en.md      ← (planned)
    └── verification-report-ja.md      ← (planned)
```

## Unstructured Data Support

| Format | Support | Access Method | Use Case |
|--------|:---:|--------------|----------|
| Images (JPEG, PNG, TIFF) | ❌ | N/A (SQL engine for structured data) | — |
| Video (MP4, MOV) | ❌ | N/A | — |
| Documents (PDF, DOCX) | ❌ | N/A | — |
| Audio (WAV, MP3) | ❌ | N/A | — |
| Binary / Archives | ❌ | N/A | — |

Athena is a SQL query engine optimized for structured data formats (Parquet, CSV, JSON, ORC). It cannot directly query unstructured data (images, video, audio). However, you can create metadata tables to manage file paths and integrate with other services for processing.

**Patterns for unstructured data workflows:**
1. **Metadata table** — Use Glue Crawler to catalog file paths, sizes, and timestamps on S3 AP
2. **Athena + Lambda UDF** — Pass file paths from query results to Lambda for processing
3. **Pipeline integration** — Use Athena to identify files, then process with Lambda/Bedrock

```sql
-- Query file metadata (registered via Glue Crawler)
SELECT key, size, last_modified
FROM fsxn_file_catalog
WHERE key LIKE '%.pdf'
ORDER BY last_modified DESC;
```

**Recommended alternative for unstructured data on FSx for ONTAP:**
- Use **AWS Lambda** for serverless file processing ([AWS tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-process-files-with-lambda.html))
- Use **Amazon Bedrock** for RAG over documents ([AWS tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html))
- Use **Snowflake** (Directory Table + GET_PRESIGNED_URL) for file catalog and secure URL generation

## Reference Implementation

This integration leverages patterns from:
- [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns)
  - UC1 (legal-compliance): Athena × S3 AP E2E verified
  - UC3 (manufacturing-analytics): Athena query patterns
  - `shared/cfn/fpolicy-routing.yaml`: Event-driven Crawler trigger
  - `docs/event-driven/`: FPolicy configuration reference

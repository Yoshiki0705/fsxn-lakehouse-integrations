# Delta Lake OSS Integration

🌐 **English** | [日本語](docs/ja/README.md)

## Overview

Open-source Delta Lake (delta-spark + delta-rs) on FSx for ONTAP via S3 Access Points.
ACID transactions, time travel, OPTIMIZE/VACUUM on enterprise NAS storage
without Databricks Runtime.

## Architecture

```
Apache Spark (EMR / Self-managed)
    └── delta-spark 3.1.0
            └── S3A FileSystem
                    └── S3 Access Point (VPC-scoped) ──→ FSx for ONTAP Volume
                                                          ├── _delta_log/
                                                          └── data/*.parquet

Python (Local / Lambda)
    └── deltalake (delta-rs)
            └── S3 Access Point ──→ FSx for ONTAP Volume
```

## Key Features

- **delta-spark**: Full CRUD (INSERT, UPDATE, DELETE, MERGE), OPTIMIZE, VACUUM
- **delta-rs**: Spark-free Python access (read/write Delta tables)
- **Time Travel**: Query historical versions, RESTORE TABLE
- **Cross-compatibility**: Tables created by Spark readable by delta-rs and vice versa
- **VPC-scoped**: Network isolation for EMR/EC2 workloads

## Status: 🚧 Implementation In Progress

## Unstructured Data Support

| Format | Support | Access Method | Use Case |
|--------|:---:|--------------|----------|
| Images (JPEG, PNG, TIFF) | ❌ | N/A (structured table format) | — |
| Video (MP4, MOV) | ❌ | N/A | — |
| Documents (PDF, DOCX) | ❌ | N/A | — |
| Audio (WAV, MP3) | ❌ | N/A | — |
| Binary / Archives | ❌ | N/A | — |

Delta Lake is a table format for structured data (Parquet-based). It cannot store or query unstructured data directly. However, Delta tables can manage file metadata with ACID transactions, Change Data Feed, and time travel.

**Metadata management pattern:**
```python
# Manage file metadata with delta-rs (no Spark needed)
import deltalake as dl
import pandas as pd

# Write file catalog as Delta table
df = pd.DataFrame({
    'file_path': ['s3://ap-alias/images/001.jpg', 's3://ap-alias/docs/report.pdf'],
    'file_type': ['image/jpeg', 'application/pdf'],
    'file_size': [2048000, 512000],
    'processed': [False, False]
})
dl.write_deltalake('s3://<ap-alias>/file_catalog/', df, mode='append')

# Time travel to view past catalog state
dt = dl.DeltaTable('s3://<ap-alias>/file_catalog/', version=3)
print(dt.to_pandas())
```

## Quick Start

```bash
# delta-rs (no Spark needed)
pip install deltalake pandas boto3
python notebooks/05_delta_rs.py --s3-ap-alias <alias>

# delta-spark (EMR)
spark-submit --packages io.delta:delta-spark_2.12:3.1.0 \
    --properties-file config/spark-defaults.conf \
    notebooks/01_delta_crud.py --s3-ap-alias <alias>
```

## Directory Structure

```
integrations/delta-lake-oss/
├── template.yaml                      ← CloudFormation (IAM, Instance Profile)
├── deploy.sh                          ← Deployment automation
├── params.example.json                ← Parameter template
├── config/
│   └── spark-defaults.conf            ← Spark + Delta + S3A configuration
├── notebooks/
│   ├── 01_delta_crud.py               ← CREATE, INSERT, UPDATE, DELETE, MERGE
│   ├── 02_time_travel.py              ← Version queries, RESTORE
│   └── 05_delta_rs.py                 ← Python-native delta-rs access
└── tests/results/                     ← Execution metrics
```

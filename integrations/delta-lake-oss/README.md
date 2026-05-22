# Delta Lake OSS Integration / Delta Lake OSS 統合

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

### Overview

Open-source Delta Lake (delta-spark + delta-rs) on FSx for ONTAP via S3 Access Points.
ACID transactions, time travel, OPTIMIZE/VACUUM on enterprise NAS storage
without Databricks Runtime.

### Architecture

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

### Key Features

- **delta-spark**: Full CRUD (INSERT, UPDATE, DELETE, MERGE), OPTIMIZE, VACUUM
- **delta-rs**: Spark-free Python access (read/write Delta tables)
- **Time Travel**: Query historical versions, RESTORE TABLE
- **Cross-compatibility**: Tables created by Spark readable by delta-rs and vice versa
- **VPC-scoped**: Network isolation for EMR/EC2 workloads

### Status: 🚧 Implementation In Progress

### Quick Start

```bash
# delta-rs (no Spark needed)
pip install deltalake pandas boto3
python notebooks/05_delta_rs.py --s3-ap-alias <alias>

# delta-spark (EMR)
spark-submit --packages io.delta:delta-spark_2.12:3.1.0 \
    --properties-file config/spark-defaults.conf \
    notebooks/01_delta_crud.py --s3-ap-alias <alias>
```

### Directory Structure

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

---

<a id="日本語"></a>

## 日本語

### 概要

オープンソース Delta Lake (delta-spark + delta-rs) を FSx for ONTAP S3 AP 経由で使用。
Databricks Runtime なしで ACID トランザクション、タイムトラベル、
OPTIMIZE/VACUUM をエンタープライズ NAS ストレージ上で実現。

### 主な特徴

- **delta-spark**: 完全な CRUD + OPTIMIZE + VACUUM
- **delta-rs**: Spark 不要の Python ネイティブアクセス
- **タイムトラベル**: 過去バージョンクエリ、RESTORE TABLE
- **相互互換性**: Spark 作成テーブルを delta-rs で読み取り可能（逆も可）
- **VPC スコープ**: EMR/EC2 ワークロードのネットワーク分離

### ステータス: 🚧 実装中

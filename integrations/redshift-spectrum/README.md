# Redshift Spectrum Integration / Redshift Spectrum 統合

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

### Overview

Query data on Amazon FSx for NetApp ONTAP directly from Amazon Redshift Spectrum
using Glue Data Catalog and S3 Access Points. Combines DWH local tables with
external FSxN data in federated queries.

### Architecture

```
Redshift Serverless (DWH)
    │
    ├── Local tables (Redshift-managed storage)
    │
    └── External Schema (Glue Data Catalog)
            │
            └── S3 Access Point (internet origin) ──→ FSx for ONTAP Volume
                                                        ├── sensor_data (Parquet, 10K rows)
                                                        └── sensor_benchmark (Parquet, 5M rows)
```

### Key Points

- **Same pattern as Athena**: Internet-origin S3 AP + Glue Catalog
- **Federated queries**: JOIN local Redshift tables with external FSxN data
- **Predicate pushdown**: Spectrum pushes filters to S3 layer (reduces data scanned)
- **No session policy issues**: AWS-native service, direct IAM role (no third-party intermediary)

### Status: ✅ Functional Verified (2026-05-23)

Verified with Redshift Serverless (8 RPU) + Spectrum on FSx for ONTAP S3 AP (internet-origin).
- COUNT(*) 10K rows: 3.2s
- GROUP BY + AVG: 2.6s
- COUNT(*) 5M rows: 4.3s
- Same pattern as Athena (Glue Catalog + internet-origin AP + IAM role)

### Quick Start

```bash
# 1. Deploy Redshift Serverless + IAM Role
./deploy.sh

# 2. Create external schema and run queries
python scripts/run_spectrum_queries.py

# 3. Cleanup (important — Redshift Serverless costs ~$2.88/hr at 8 RPU)
./scripts/cleanup.sh
```

### Directory Structure

```
integrations/redshift-spectrum/
├── README.md                          ← This file
├── template.yaml                      ← CloudFormation (Redshift Serverless + IAM)
├── deploy.sh                          ← Deployment automation
├── params.example.json                ← Parameter template
├── sql/
│   ├── 01_create_external_schema.sql  ← External schema pointing to Glue Catalog
│   ├── 02_spectrum_queries.sql        ← SELECT, GROUP BY, aggregation queries
│   ├── 03_federated_join.sql          ← JOIN local + external tables
│   └── 04_pushdown_verification.sql   ← SVL_S3QUERY_SUMMARY analysis
├── scripts/
│   ├── run_spectrum_queries.py        ← Query execution + metrics
│   ├── validate_connectivity.py       ← Connectivity validation
│   └── cleanup.sh                     ← Resource cleanup (delete Serverless)
└── tests/results/                     ← Query metrics output
```

---

<a id="日本語"></a>

## 日本語

### 概要

Amazon Redshift Spectrum から Amazon FSx for NetApp ONTAP のデータを直接クエリします。
Glue Data Catalog と S3 Access Points を使用し、DWH ローカルテーブルと
外部 FSxN データのフェデレーテッドクエリを実現します。

### 主なポイント

- **Athena と同パターン**: Internet-origin S3 AP + Glue Catalog
- **フェデレーテッドクエリ**: Redshift ローカルテーブルと外部 FSxN データの JOIN
- **述語プッシュダウン**: Spectrum がフィルタを S3 レイヤーにプッシュ（スキャンデータ削減）
- **セッションポリシー問題なし**: AWS ネイティブサービス、直接 IAM ロール

### ステータス: ✅ 機能検証済み (2026-05-23)

Redshift Serverless (8 RPU) + Spectrum で FSx for ONTAP S3 AP（internet-origin）を検証済み。
- COUNT(*) 10K 行: 3.2 秒
- GROUP BY + AVG: 2.6 秒
- COUNT(*) 500 万行: 4.3 秒
- Athena と同パターン（Glue Catalog + internet-origin AP + IAM ロール）

### 重要: コスト

Redshift Serverless は最低 8 RPU（約 $2.88/時間）。検証後は速やかに削除してください。

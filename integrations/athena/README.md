# AWS Athena Integration / AWS Athena 統合

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

### Overview

Query data on Amazon FSx for NetApp ONTAP (FSx for ONTAP) directly from Amazon Athena using
Glue Data Catalog and S3 Access Points. Serverless, pay-per-query analytics.

### Architecture

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

### Important: Network Origin

Athena requires S3 Access Points with **internet network origin**.
VPC-only access points will NOT work with Athena.

Reference: [AWS Tutorial - Query files with Athena](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

### Status: 🚧 Implementation In Progress

### Quick Start

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

### Directory Structure

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

### Reference Implementation

This integration leverages patterns from:
- [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns)
  - UC1 (legal-compliance): Athena × S3 AP E2E verified
  - UC3 (manufacturing-analytics): Athena query patterns
  - `shared/cfn/fpolicy-routing.yaml`: Event-driven Crawler trigger
  - `docs/event-driven/`: FPolicy configuration reference

---

<a id="日本語"></a>

## 日本語

### 概要

Amazon Athena から Amazon FSx for NetApp ONTAP（FSx for ONTAP）のデータを直接クエリします。
Glue Data Catalog と S3 Access Points を使用したサーバーレス分析です。

### アーキテクチャ

```
Athena (サーバーレス SQL)
    │
    └── Glue Data Catalog
            │
            ├── Glue Crawler (スキーマ自動検出)
            │
            └── S3 Access Point (インターネットオリジン) ──→ FSx for ONTAP Volume
                                                              ├── transactions/ (Parquet, パーティション)
                                                              ├── customers/ (CSV)
                                                              ├── events/ (JSON)
                                                              └── gold/ (CTAS 出力先)
```

### 重要: ネットワークオリジン

Athena は **インターネットネットワークオリジン** の S3 Access Point が必要です。
VPC 限定のアクセスポイントは Athena では動作しません。

参考: [AWS チュートリアル - Athena でファイルをクエリ](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

### ステータス: 🚧 実装中

### クイックスタート

```bash
# 1. パラメータファイルをコピーして値を入力
cp params.example.json params.json

# 2. サンプルデータ生成
pip install pandas pyarrow
python scripts/generate_sample_data.py

# 3. FSx for ONTAP に NFS 経由でアップロード
./scripts/upload_sample_data.sh

# 4. インフラデプロイ
./deploy.sh

# 5. 接続検証
python scripts/validate_connectivity.py

# 6. クエリ実行とメトリクス収集
python scripts/execute_queries.py
```

### リファレンス実装

以下のリポジトリのパターンを活用:
- [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns)
  - UC1 (法務コンプライアンス): Athena × S3 AP E2E 検証済み
  - UC3 (製造業分析): Athena クエリパターン
  - `shared/cfn/fpolicy-routing.yaml`: イベント駆動 Crawler トリガー
  - `docs/event-driven/`: FPolicy 設定リファレンス

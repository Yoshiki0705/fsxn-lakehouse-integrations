# AWS Glue Integration / AWS Glue 統合

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

### Overview

Build a medallion architecture (Bronze → Silver → Gold) ETL pipeline on Amazon FSx for NetApp ONTAP
using AWS Glue 4.0, GlueContext/DynamicFrame API, and S3 Access Points.
Serverless, scalable data transformation with job bookmarks for incremental processing.

### Architecture

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

### Important: Network Origin

Glue requires S3 Access Points with **internet network origin**.
VPC-only access points will NOT work with Glue ETL jobs.

Reference: [AWS Tutorial - Transform data with Glue](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

### Key Features

- **Glue 4.0** (Spark 3.3+) with GlueContext and DynamicFrame API
- **Job Bookmarks** for incremental processing (no reprocessing of old data)
- **Medallion Architecture**: Bronze (raw) → Silver (cleaned) → Gold (aggregated)
- **Data Quality**: DQDL rules for completeness, uniqueness, value ranges, freshness
- **Scheduled Execution**: EventBridge rule for automated daily runs
- **ZSTD Compression**: Optimal compression for silver/gold Parquet files

### Status: 🚧 Implementation In Progress

### Quick Start

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

### Directory Structure

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

### ETL Transformations

#### Bronze → Silver
- Schema normalization (lowercase column names)
- Null handling (type-aware defaults)
- Type casting (timestamps, numerics)
- Deduplication (by primary key)
- Metadata columns (`_etl_timestamp`, `_source_file`)
- Output: Parquet with ZSTD compression

#### Silver → Gold
- **Daily Summaries**: transaction counts, amounts, completion rates by date
- **Category Rollups**: revenue distribution, customer counts by category
- **Customer Metrics**: lifetime value, purchase frequency, favorite category

### Data Quality Rules

DQDL rules validate:
- **Completeness**: Critical columns must not be null (≥95-100%)
- **Uniqueness**: Primary keys must be unique
- **Value Ranges**: Amounts > 0, valid enum values
- **Freshness**: Data within expected time windows

### Reference Implementation

This integration leverages patterns from:
- [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns)
  - UC1 (legal-compliance): Glue Crawler + S3 AP pattern
  - UC3 (manufacturing-analytics): Glue ETL pipeline
- [AWS Tutorial: Transform data with Glue](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

---

<a id="日本語"></a>

## 日本語

### 概要

AWS Glue 4.0 を使用して、Amazon FSx for NetApp ONTAP 上にメダリオンアーキテクチャ
（Bronze → Silver → Gold）の ETL パイプラインを構築します。
GlueContext/DynamicFrame API と S3 Access Points を活用した、
サーバーレスでスケーラブルなデータ変換を実現します。

### アーキテクチャ

```
EventBridge (スケジュール実行)
    │
    ▼
Glue Crawler ──→ Glue Data Catalog
    │                    │
    ▼                    ▼
Glue ETL Job         Glue ETL Job
(Bronze→Silver)      (Silver→Gold)
    │                    │
    ▼                    ▼
S3 Access Point (インターネットオリジン) ──→ FSx for ONTAP Volume
                                              ├── bronze/ (生データ)
                                              │   ├── transactions/ (Parquet)
                                              │   ├── customers/ (CSV)
                                              │   └── events/ (JSON)
                                              ├── silver/ (クレンジング済み)
                                              │   ├── transactions/ (Parquet, ZSTD)
                                              │   ├── customers/ (Parquet, ZSTD)
                                              │   └── events/ (Parquet, ZSTD)
                                              └── gold/ (集計済み)
                                                  ├── daily_summaries/
                                                  ├── category_rollups/
                                                  └── customer_metrics/
```

### 重要: ネットワークオリジン

Glue は **インターネットネットワークオリジン** の S3 Access Point が必要です。
VPC 限定のアクセスポイントは Glue ETL ジョブでは動作しません。

参考: [AWS チュートリアル - Glue でデータを変換](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

### 主な機能

- **Glue 4.0** (Spark 3.3+) — GlueContext と DynamicFrame API
- **ジョブブックマーク** — 増分処理（過去データの再処理なし）
- **メダリオンアーキテクチャ**: Bronze（生データ）→ Silver（クレンジング）→ Gold（集計）
- **データ品質**: DQDL ルールによる完全性・一意性・値範囲・鮮度チェック
- **スケジュール実行**: EventBridge による日次自動実行
- **ZSTD 圧縮**: Silver/Gold レイヤーの最適圧縮

### ステータス: 🚧 実装中

### クイックスタート

```bash
# 1. パラメータファイルをコピーして値を入力
cp params.example.json params.json

# 2. サンプルデータ生成
pip install pandas pyarrow boto3
python scripts/generate_sample_data.py

# 3. FSx for ONTAP に NFS 経由でアップロード
rsync -avz ./sample_data/bronze/ /mnt/fsxn/bronze/

# 4. インフラデプロイ
./deploy.sh

# 5. 接続検証
python scripts/validate_connectivity.py

# 6. ETL パイプライン実行
python scripts/run_etl_pipeline.py

# 7. (オプション) クローラーのみ実行
python scripts/run_crawler.py --wait
```

### ETL 変換内容

#### Bronze → Silver
- スキーマ正規化（カラム名の小文字化）
- Null 値処理（型に応じたデフォルト値）
- 型キャスト（タイムスタンプ、数値）
- 重複排除（主キーベース）
- メタデータカラム追加（`_etl_timestamp`, `_source_file`）
- 出力: Parquet + ZSTD 圧縮

#### Silver → Gold
- **日次サマリー**: 日別のトランザクション数、金額、完了率
- **カテゴリ集計**: カテゴリ別の売上分布、顧客数
- **顧客メトリクス**: 生涯価値、購入頻度、お気に入りカテゴリ

### データ品質ルール

DQDL ルールによる検証:
- **完全性**: 重要カラムの非 NULL 率（95-100%）
- **一意性**: 主キーの一意性
- **値範囲**: 金額 > 0、有効な列挙値
- **鮮度**: 期待される時間窓内のデータ

### リファレンス実装

以下のリポジトリのパターンを活用:
- [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns)
  - UC1 (法務コンプライアンス): Glue Crawler + S3 AP パターン
  - UC3 (製造業分析): Glue ETL パイプライン
- [AWS チュートリアル: Glue でデータを変換](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

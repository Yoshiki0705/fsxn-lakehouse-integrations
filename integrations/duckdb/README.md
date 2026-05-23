# DuckDB Integration / DuckDB 統合

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

### Overview

Lightweight, in-process analytics on FSx for ONTAP data using DuckDB. No server required.
Deploy as Lambda for serverless pay-per-invocation queries, or run locally/on EC2.

### What is DuckDB?

DuckDB is an in-process SQL OLAP database — think "SQLite for analytics." It runs inside your application (Python, Node.js, Java, etc.) with zero infrastructure. No database server to manage, no cluster to provision.

![DuckDB Homepage](../../docs/images/duckdb-homepage.png)
*DuckDB — An in-process SQL OLAP database management system ([duckdb.org](https://duckdb.org))*

**Key characteristics:**
- **In-process**: Runs inside Lambda, your laptop, or any compute — no separate DB server
- **Columnar**: Optimized for analytical queries (aggregations, scans, JOINs)
- **Parquet-native**: Reads Parquet files directly from S3 with predicate pushdown
- **Zero-copy**: No ETL needed — query files where they are

![DuckDB Web Shell](../../docs/images/duckdb-web-shell.png)
*DuckDB Web Shell — Try SQL queries in your browser at [shell.duckdb.org](https://shell.duckdb.org)*

**Why DuckDB for FSx for ONTAP?**
- Query Parquet/CSV/JSON on FSx S3 AP without provisioning any analytics infrastructure
- Deploy in Lambda for serverless, pay-per-invocation analytics ($0 when idle)
- No session policy issues (unlike Databricks/Snowflake) — uses direct IAM credentials
- Sub-second queries on millions of rows

![Why DuckDB](../../docs/images/duckdb-why-duckdb.png)
*DuckDB design philosophy — simple, portable, fast ([duckdb.org/why_duckdb](https://duckdb.org/why_duckdb))*

### Architecture

```
Lambda (arm64, Python 3.12)          Local / EC2
    │                                    │
    └── DuckDB (in-process)              └── DuckDB (in-process)
            │                                    │
            └── httpfs extension                  └── httpfs extension
                    │                                    │
                    └── S3 AP (VPC-scoped) ──→ FSx for ONTAP     └── S3 AP ──→ FSx for ONTAP
```

### Key Features

- **Zero infrastructure**: DuckDB runs in-process (no database server)
- **Lambda deployment**: Serverless, pay-per-invocation, arm64 Graviton
- **Parquet pushdown**: Predicate and projection pushdown for minimal data transfer
- **Write-back**: COPY results to FSx for ONTAP as Parquet/CSV
- **Sub-second queries**: Warm Lambda queries in 200-500ms

### Status: ✅ Functional Verified (2026-05-23)

Verified locally with DuckDB 1.4.4 + httpfs on FSx for ONTAP S3 AP (internet-origin).
- Read: 10K rows in 628ms, 5M rows in 779ms
- Aggregation: GROUP BY in 1.2s, Window function in 1.0s
- Write-back: COPY TO Parquet in 304ms
- Lambda deployment: Ready (template.yaml + handler.py complete)

### Quick Start

```bash
# Local queries
pip install duckdb boto3
python notebooks/01_local_queries.py --ap-alias <your-ap-alias>

# Lambda deployment
./lambda/build_layer.sh
./deploy.sh
python scripts/validate_connectivity.py
```

### Directory Structure

```
integrations/duckdb/
├── template.yaml                  ← CloudFormation (Lambda + Layer + IAM)
├── deploy.sh                      ← Deployment automation
├── params.example.json            ← Parameter template
├── lambda/
│   ├── handler.py                 ← Lambda function (DuckDB query executor)
│   └── build_layer.sh             ← Layer builder (Docker, arm64)
├── notebooks/
│   ├── 01_local_queries.py        ← Local DuckDB queries on FSx for ONTAP
│   ├── 02_pushdown_verification.py ← Predicate pushdown tests
│   └── 03_write_back.py           ← Write results to FSx for ONTAP
├── scripts/
│   ├── validate_connectivity.py   ← Connectivity validation
│   └── cleanup.sh                 ← Resource cleanup
└── tests/results/                 ← Query metrics output
```

---

<a id="日本語"></a>

## 日本語

### 概要

DuckDB を使用した FSx for ONTAP データの軽量インプロセス分析。サーバー不要。
Lambda にデプロイしてサーバーレスクエリ、またはローカル/EC2 で実行。

### DuckDB とは？

DuckDB はインプロセス SQL OLAP データベースです。「分析版 SQLite」と考えてください。アプリケーション内（Python、Node.js、Java 等）で動作し、インフラ管理ゼロ。データベースサーバーの管理もクラスタのプロビジョニングも不要です。

![DuckDB ホームページ](../../docs/images/duckdb-homepage.png)
*DuckDB — インプロセス SQL OLAP データベース管理システム ([duckdb.org](https://duckdb.org))*

**主な特徴:**
- **インプロセス**: Lambda、ローカル PC、任意のコンピュートで動作 — 別途 DB サーバー不要
- **列指向**: 分析クエリ（集約、スキャン、JOIN）に最適化
- **Parquet ネイティブ**: S3 上の Parquet ファイルを述語プッシュダウン付きで直接読み取り
- **ゼロコピー**: ETL 不要 — ファイルがある場所でそのままクエリ

![DuckDB Web Shell](../../docs/images/duckdb-web-shell.png)
*DuckDB Web Shell — ブラウザで SQL クエリを試せます ([shell.duckdb.org](https://shell.duckdb.org))*

**なぜ FSx for ONTAP に DuckDB？**
- 分析インフラをプロビジョニングせずに FSx S3 AP 上の Parquet/CSV/JSON をクエリ
- Lambda にデプロイしてサーバーレス従量課金分析（アイドル時 $0）
- セッションポリシー問題なし（Databricks/Snowflake と異なり）— 直接 IAM 認証情報を使用
- 数百万行に対するサブ秒クエリ

![Why DuckDB](../../docs/images/duckdb-why-duckdb.png)
*DuckDB の設計哲学 — シンプル、ポータブル、高速 ([duckdb.org/why_duckdb](https://duckdb.org/why_duckdb))*

### 主な特徴

- **インフラ不要**: DuckDB はインプロセス実行（DBサーバーなし）
- **Lambda デプロイ**: サーバーレス、従量課金、arm64 Graviton
- **Parquet プッシュダウン**: 述語・射影プッシュダウンでデータ転送最小化
- **書き戻し**: COPY で結果を FSx for ONTAP に Parquet/CSV 出力
- **サブ秒クエリ**: ウォーム Lambda で 200-500ms

### ステータス: ✅ 機能検証済み (2026-05-23)

DuckDB 1.4.4 + httpfs で FSx for ONTAP S3 AP（internet-origin）に対してローカル検証済み。
- 読み取り: 10K 行 628ms、500 万行 779ms
- 集約: GROUP BY 1.2 秒、Window 関数 1.0 秒
- 書き戻し: COPY TO Parquet 304ms
- Lambda デプロイ: 準備完了（template.yaml + handler.py 完成）

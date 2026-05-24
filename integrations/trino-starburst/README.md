# Trino / Starburst Integration / Trino / Starburst 統合

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

### Overview

Query FSx for ONTAP data via S3 Access Points using Trino — an open-source distributed SQL query engine. Trino uses its own S3 filesystem implementation that supports path-style access, making it compatible with FSx S3 AP aliases.

### Status: ⚠️ Blocked by S3 Gateway Endpoint Routing

- Infrastructure prepared (Docker Compose + config)
- **Finding**: FSx S3 AP alias traffic is NOT routed correctly through S3 Gateway VPC Endpoint
- Regular S3 bucket access works fine through the same Gateway endpoint
- FSx S3 AP alias resolves to `s3-r-w.ap-northeast-1.amazonaws.com` — this IP range may not be in the S3 prefix list
- **Workaround options**:
  1. Use a subnet without S3 Gateway endpoint (route via IGW/NAT)
  2. Add S3 Interface endpoint (PrivateLink)
  3. Use internet-routed EC2 (public subnet without Gateway endpoint route)
- Trino configuration is ready — blocked only by network routing

### Architecture

```
Trino (Docker, single-node)
    │
    └── Hive Connector (file-based metastore)
            │
            └── S3 filesystem (path-style access)
                    │
                    └── FSx S3 Access Point (internet-origin)
                            │
                            └── FSx for ONTAP Volume (Parquet files)
```

### Key Configuration

Trino's Hive connector supports `hive.s3.path-style-access=true`, which is required for S3 AP alias resolution (same pattern as DuckDB's `s3_url_style='path'`).

```properties
# catalog/fsxn.properties
connector.name=hive
hive.metastore=file
hive.metastore.catalog.dir=s3://<FSx-S3-AP-alias>/
hive.s3.path-style-access=true
hive.s3.endpoint=https://s3.ap-northeast-1.amazonaws.com
hive.s3.region=ap-northeast-1
hive.s3.aws-access-key=<from-instance-profile-or-explicit>
hive.s3.aws-secret-key=<from-instance-profile-or-explicit>
```

### Expected Behavior

Based on DuckDB and EMR Spark verification results (both use path-style S3 access):
- **Read Parquet**: Expected to WORK (same S3 API pattern as DuckDB httpfs)
- **Write Parquet**: Expected to WORK (flat file PutObject)
- **Delta/Iceberg write**: Expected to FAIL (same atomic rename constraint)
- **No session policy issues**: Direct IAM credentials, no intermediary governance layer

### Quick Start

```bash
# 1. Start Trino (Docker)
docker compose up -d

# 2. Connect with Trino CLI
docker exec -it trino trino --catalog fsxn --schema default

# 3. Run queries
trino> SELECT COUNT(*) FROM sensor_data;
trino> SELECT status, AVG(temperature) FROM sensor_data GROUP BY status;
```

### Directory Structure

```
integrations/trino-starburst/
├── README.md                          ← This file
├── docker-compose.yaml                ← Trino single-node + config
├── config/
│   ├── etc/
│   │   ├── config.properties          ← Trino server config
│   │   ├── jvm.config                 ← JVM settings
│   │   ├── node.properties            ← Node identity
│   │   └── catalog/
│   │       └── fsxn.properties        ← FSx S3 AP connector config
├── sql/
│   ├── 01_create_schema.sql           ← Schema + table DDL
│   ├── 02_read_queries.sql            ← SELECT, GROUP BY, aggregation
│   └── 03_write_back.sql              ← CTAS write-back test
├── scripts/
│   ├── run_verification.sh            ← End-to-end verification
│   └── cleanup.sh                     ← Stop and remove containers
└── params.example.json                ← Parameter template
```

### Comparison with Other Engines

| Feature | Trino | DuckDB | Athena | EMR Spark |
|---------|-------|--------|--------|-----------|
| Deployment | Docker / EC2 / K8s | In-process / Lambda | Serverless | EMR Serverless |
| S3 AP support | path-style access | path-style + endpoint | Native (EMRFS) | Native (EMRFS) |
| Session policy risk | None (direct IAM) | None (direct IAM) | None (AWS-native) | None (AWS-native) |
| Write-back | PutObject (flat files) | COPY TO | CTAS | Spark write |
| Cost model | Compute (EC2/container) | Per-invocation (Lambda) | Per-scan | Per-job |
| Best for | Federated SQL, multi-source | Lightweight ad-hoc | Serverless SQL | Large-scale ETL |

---

<a id="日本語"></a>

## 日本語

### 概要

Trino（オープンソース分散 SQL クエリエンジン）を使用して、FSx for ONTAP のデータを S3 Access Points 経由でクエリします。Trino は path-style アクセスをサポートする独自の S3 ファイルシステム実装を持ち、FSx S3 AP alias と互換性があります。

### ステータス: ⚠️ S3 Gateway エンドポイントルーティングでブロック

- インフラ準備済み（Docker Compose + 設定）
- **発見**: FSx S3 AP alias トラフィックが S3 Gateway VPC エンドポイント経由で正しくルーティングされない
- 通常の S3 バケットアクセスは同じ Gateway エンドポイント経由で正常動作
- FSx S3 AP alias は `s3-r-w.ap-northeast-1.amazonaws.com` に解決 — この IP 範囲が S3 プレフィックスリストに含まれていない可能性
- **回避策**:
  1. S3 Gateway エンドポイントのないサブネットを使用（IGW/NAT 経由）
  2. S3 Interface エンドポイント（PrivateLink）を追加
  3. インターネットルーティングの EC2 を使用
- Trino 設定は準備完了 — ネットワークルーティングのみがブロッカー

### 主な設定

Trino の Hive コネクタは `hive.s3.path-style-access=true` をサポートしており、S3 AP alias の解決に必要です（DuckDB の `s3_url_style='path'` と同じパターン）。

### 期待される動作

DuckDB および EMR Spark の検証結果に基づく（両方とも path-style S3 アクセスを使用）:
- **Parquet 読み取り**: 動作する見込み（DuckDB httpfs と同じ S3 API パターン）
- **Parquet 書き込み**: 動作する見込み（フラットファイル PutObject）
- **Delta/Iceberg 書き込み**: 失敗する見込み（同じ atomic rename 制約）
- **セッションポリシー問題なし**: 直接 IAM 認証情報、中間ガバナンスレイヤーなし

### 他エンジンとの比較

| 特徴 | Trino | DuckDB | Athena | EMR Spark |
|------|-------|--------|--------|-----------|
| デプロイ | Docker / EC2 / K8s | インプロセス / Lambda | サーバーレス | EMR Serverless |
| S3 AP サポート | path-style access | path-style + endpoint | ネイティブ (EMRFS) | ネイティブ (EMRFS) |
| セッションポリシーリスク | なし（直接 IAM） | なし（直接 IAM） | なし（AWS ネイティブ） | なし（AWS ネイティブ） |
| コストモデル | コンピュート（EC2/コンテナ） | 従量課金（Lambda） | スキャン量課金 | ジョブ課金 |
| 最適用途 | フェデレーテッド SQL、マルチソース | 軽量アドホック | サーバーレス SQL | 大規模 ETL |

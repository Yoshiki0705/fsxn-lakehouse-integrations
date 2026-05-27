# ベンダー比較マトリクス

🌐 [English](../en/vendor-comparison.md)

## プロジェクトコンセプト

Amazon FSx for NetApp ONTAP（FSx for ONTAP）× S3 Access Points × Lakehouse/Data Lake Integrations

FSx for ONTAP のエンタープライズストレージを S3 Access Points 経由で
各 Lakehouse/Data Lake プラットフォームから直接アクセス可能にするパターン集。
ONTAP の重複排除・圧縮・Snapshot・階層化を活かしつつ、モダンな分析基盤と統合する。

```
Lakehouse Platform ←→ S3 Access Point ←→ FSx for NetApp ONTAP
(External Table / Stage / Location)         (NFS/SMB/S3 統合ストレージ)
```

---

## Tier 1: 最有力候補

| ベンダー | 統合方式 | ユースケース | ステータス |
|---------|---------|-------------|----------|
| **Databricks** | Unity Catalog External Location / S3 External Table | Delta Lake on FSx for ONTAP, ML Feature Store | ⚠️ ブロック（セッションポリシー — UC テーブル作成失敗） |
| **Snowflake** | External Stage + `AWS_ACCESS_POINT_ARN` / External Table | ガバナンス付き分析、Cortex AI、Data Sharing、Managed Iceberg | ✅ 検証済み（2026年5月） |

### Databricks

- **認証**: Cross-account IAM Role + External ID
- **ネットワーク**: VPC network origin（推奨）
- **データ形式**: Delta Lake, Iceberg, Parquet, CSV, JSON, ORC
- **非構造化データ**: `binaryFile` フォーマットで画像/動画読み取り可能
- **ONTAP 活用**: FlexClone（dev/test）、Snapshot（Time Travel 補完）
- **制限**: UC セッションポリシーが S3 AP 上のテーブル作成とサブディレクトリ一覧をブロック。推奨パス: DataSync → S3 → UC。

### Snowflake

- **認証**: Storage Integration + IAM Role
- **ネットワーク**: Internet network origin（PrivateLink オプション）
- **データ形式**: Parquet, CSV, JSON, Avro, ORC, Iceberg
- **非構造化データ**: Directory Table + Pre-signed URL + Cortex AI（PARSE_DOCUMENT で OCR、ステージング経由でマルチモーダル Vision）
- **AI 機能**: FSx データ上で 8/10 Cortex AI 関数検証済み（SUMMARIZE, TRANSLATE, SENTIMENT, COMPLETE, EXTRACT_ANSWER, PARSE_DOCUMENT, Cortex Search 198ms, Vision AI ステージング経由）
- **ガバナンス**: Object Tags, Row Access Policy, Column Masking, Data Sharing — External Table 上で全て検証済み
- **高度なパターン**: Dynamic Table（確認済み、FULL refresh、最小 60秒 TARGET_LAG）、Managed Iceberg Table（確認済み、顧客 S3 上のオープン形式）
- **ONTAP 活用**: Snapshot（Time Travel 超過分）、FlexClone（テスト環境）、マルチプロトコル（NFS/SMB/S3 同一データ）
- **Data Sharing**: Snowflake Data Sharing 経由でパートナー/サプライヤーへのガバナンス付き配布（External Table 共有可能）
- **既知の制限**: AUTO_REFRESH 利用不可（S3 Event Notifications なし）; Task + ALTER EXTERNAL TABLE REFRESH を使用

---

## Tier 2: オープンテーブルフォーマット

| フォーマット/エンジン | 統合方式 | ユースケース | ステータス |
|-------------------|---------|-------------|----------|
| **Apache Iceberg** | S3 Catalog + S3 AP | ベンダー中立テーブルフォーマット | 🚧 計画中 |
| **Delta Lake (OSS)** | S3 Storage Layer | Spark/Databricks 互換 | 🚧 計画中 |
| **Apache Hudi** | S3 Storage Layer | CDC・増分処理 | 🚧 計画中 |
| **Dremio** | S3 Source / Nessie Catalog | Iceberg ネイティブ Lakehouse | 🚧 計画中 |
| **Starburst / Trino** | S3 Connector / Hive Metastore | 分散 SQL フェデレーション | 🚧 計画中 |

### Apache Iceberg

- **認証**: IAM Role（エンジン依存）
- **カタログ**: REST Catalog, Glue Catalog, Hive Metastore
- **特徴**: ベンダー中立、スキーマ進化、パーティション進化
- **非構造化データ**: メタデータテーブルでファイル管理可能

### Dremio

- **認証**: IAM Role / Access Key
- **カタログ**: Nessie (Git-like catalog) / Arctic
- **特徴**: Iceberg ネイティブ、リフレクション（高速化）
- **非構造化データ**: メタデータカタログ化のみ

### Starburst / Trino

- **認証**: IAM Role / Instance Profile
- **カタログ**: Hive Metastore / Glue Catalog
- **特徴**: 分散 SQL、フェデレーテッドクエリ、多数のコネクタ
- **非構造化データ**: ファイルメタデータクエリ可能

---

## Tier 3: クラウドネイティブ分析

| サービス | 統合方式 | ユースケース | ステータス |
|---------|---------|-------------|----------|
| **AWS Athena** | S3 AP 直接クエリ | サーバーレス SQL | ✅ セキュリティ検証済み |
| **AWS Glue** | S3 AP Crawler / ETL Job | データカタログ + ETL | ✅ 機能検証済み |
| **AWS Lake Formation** | S3 AP 登録 | ガバナンス・権限管理 | 🚧 計画中 |
| **Amazon Redshift Spectrum** | External Schema on S3 AP | DWH + Data Lake 統合 | 🚧 計画中 |
| **Amazon EMR (Spark)** | S3A Connector → S3 AP | 大規模バッチ処理 | 🚧 計画中 |
| **Google BigQuery Omni** | S3 Connection | クロスクラウド分析 | 📋 調査中 |
| **Microsoft Fabric / Synapse** | S3 Shortcut / External Table | Microsoft エコシステム統合 | 📋 調査中 |

### AWS Athena

- **認証**: IAM Role（サービスロール）
- **ネットワーク**: Internet network origin **必須**
- **特徴**: サーバーレス、従量課金（スキャンデータ量）
- **非構造化データ**: メタデータクエリのみ（ファイルパス、サイズ）
- **参考**: [AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

### AWS Glue

- **認証**: Glue サービスロール
- **ネットワーク**: Internet network origin **必須**
- **特徴**: Crawler（スキーマ発見）、ETL Job（PySpark/Python Shell/Ray）
- **非構造化データ**: Crawler でファイルメタデータ収集、ETL で変換処理
- **参考**: [AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

### Amazon Redshift Spectrum

- **認証**: Redshift IAM Role
- **ネットワーク**: Internet network origin **必須**
- **特徴**: DWH + Data Lake フェデレーテッドクエリ
- **非構造化データ**: 非対応（構造化データのみ）
- **参考**: [AWS re:Post](https://repost.aws/articles/AR7E4oxFvtR5GgajAQT7X1xQ)

### Amazon EMR (Spark)

- **認証**: Instance Profile / IAM Role
- **ネットワーク**: VPC network origin 可能
- **特徴**: 大規模バッチ、Spark/Hive/Presto
- **非構造化データ**: `binaryFile` フォーマット、画像処理ライブラリ

### Google BigQuery Omni

- **認証**: S3 Connection（IAM Role）
- **ネットワーク**: Internet network origin
- **特徴**: クロスクラウド分析、BigLake テーブル
- **非構造化データ**: Object Table で画像/動画メタデータ管理

### Microsoft Fabric / Synapse

- **認証**: S3 Shortcut（Access Key / IAM Role）
- **ネットワーク**: Internet network origin
- **特徴**: OneLake 統合、Power BI 連携
- **非構造化データ**: OneLake Shortcut 経由でファイルアクセス

---

## Tier 4: 新興・特化型

| ベンダー | 統合方式 | ユースケース | ステータス |
|---------|---------|-------------|----------|
| **Firebolt** | S3 External Table | 高速 OLAP | 📋 調査中 |
| **ClickHouse** | S3 Table Function | リアルタイム分析 | 📋 調査中 |
| **DuckDB** | S3 httpfs Extension | エッジ/Lambda 内分析 | ✅ 機能検証済み |
| **Apache Spark (Self-managed)** | S3A FileSystem | カスタム Spark クラスタ | 📋 調査中 |
| **Presto / PrestoDB** | Hive Connector + S3 | 分散クエリ | 📋 調査中 |

### DuckDB

- **認証**: Access Key / IAM Role（Lambda 実行ロール）
- **ネットワーク**: VPC network origin 可能
- **特徴**: インプロセス分析、Lambda 内で実行可能、軽量
- **非構造化データ**: Parquet/CSV のみ（バイナリ非対応）
- **ユースケース**: Lambda 内での軽量分析、エッジコンピューティング

### ClickHouse

- **認証**: Access Key
- **ネットワーク**: Internet network origin
- **特徴**: 列指向、リアルタイム分析、高速集計
- **非構造化データ**: 非対応（構造化データ特化）

### Firebolt

- **認証**: IAM Role
- **ネットワーク**: Internet network origin
- **特徴**: 高速 OLAP、サブセカンドクエリ
- **非構造化データ**: 非対応

---

## 非構造化データ対応マトリクス

| プラットフォーム | 画像 | 動画 | 音声 | ドキュメント | 方式 |
|---------------|------|------|------|------------|------|
| **SageMaker** | ✅ | ✅ | ✅ | ✅ | S3 AP 直接読み取り |
| **Bedrock** | ✅ | ❌ | ❌ | ✅ | Knowledge Base (RAG) |
| **Rekognition** | ✅ | ✅ | ❌ | ❌ | S3 AP 直接読み取り |
| **Transcribe** | ❌ | ❌ | ✅ | ❌ | S3 AP 直接読み取り |
| **Textract** | ✅ | ❌ | ❌ | ✅ | S3 AP 直接読み取り |
| **Lambda** | ✅ | ✅ | ✅ | ✅ | S3 AP 読み書き |
| **Databricks** | ✅ | ✅ | ✅ | ✅ | binaryFile フォーマット |
| **Snowflake** | ✅ | ✅ | ✅ | ✅ | Directory Table + Pre-signed URL |
| **EMR Spark** | ✅ | ✅ | ✅ | ✅ | binaryFile / カスタム |
| **Athena** | ❌ | ❌ | ❌ | ❌ | 構造化データのみ |
| **BigQuery Omni** | ✅ | ✅ | ❌ | ❌ | Object Table |

✅ = 直接処理可能 / 📋 = メタデータのみ / ❌ = 非対応

---

## ネットワークオリジン要件まとめ

| ネットワークオリジン | 対応プラットフォーム |
|-------------------|-------------------|
| **VPC origin** | Databricks, EMR, Lambda, DuckDB (Lambda内) |
| **Internet origin** | Athena, Glue, Redshift Spectrum, Snowflake, BigQuery Omni, Fabric |

⚠️ VPC origin は同一 VPC 内からのみアクセス可能（よりセキュア）
⚠️ Internet origin は IAM 認証で保護（より広いサービス互換性）

---

## 選定ガイド

### 構造化データ分析が主目的

```
高頻度クエリ + ガバナンス → Databricks (Unity Catalog)
データ共有 + SQL 中心 → Snowflake
サーバーレス + 低コスト → Athena
ETL パイプライン → Glue
DWH 統合 → Redshift Spectrum
```

### 非構造化データ処理が主目的

```
AI/ML 学習 → SageMaker + S3 AP
RAG パイプライン → Bedrock + S3 AP
画像/動画分析 → Rekognition + Lambda + S3 AP
ドキュメント処理 → Textract + Lambda + S3 AP
メディア変換 → MediaConvert + S3 AP
```

### ベンダー中立を重視

```
テーブルフォーマット → Apache Iceberg
カタログ → REST Catalog or Glue Catalog
エンジン → Trino / Spark / Dremio
```

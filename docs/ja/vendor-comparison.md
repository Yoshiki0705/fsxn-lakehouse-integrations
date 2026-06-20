# プラットフォーム統合リファレンス

🌐 [English](../en/vendor-comparison.md)

> **フレーミング**: 本ドキュメントは各プラットフォームの統合方式・対応状況・トレードオフを中立的に整理したリファレンスです。優劣の順位付けではなく、用途に応じた選択（right-tool-for-the-job）を支援することを目的とします。

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

## マネージド Lakehouse プラットフォーム

| ベンダー | 統合方式 | ユースケース | ステータス |
|---------|---------|-------------|----------|
| **Databricks** | Unity Catalog External Location / S3 External Table | Delta Lake on FSx for ONTAP, ML Feature Store | ⚠️ ブロック（セッションポリシー — UC テーブル作成失敗） |
| **Snowflake** | External Stage + `AWS_ACCESS_POINT_ARN` / External Table | ガバナンス付き分析、Cortex AI、Data Sharing、Managed Iceberg | ✅ 検証済み（2026年5月） |

### Databricks

- **認証**: Cross-account IAM Role + External ID
- **ネットワーク**: VPC network origin（推奨）
- **データ形式**: Delta Lake, Iceberg, Parquet, CSV, JSON, ORC
- **非構造化データ**: UC Volumes + `read_files()` + `ai_query()`（画像/ドキュメントに LLM）+ `ai_parse_document()`（OCR）
- **AI 機能**: Mosaic AI（ML トレーニング、Feature Store、Model Registry）、`ai_query`（ファイルに LLM）、`ai_parse_document`（OCR）、Vector Search（RAG）、MLflow 実験追跡
- **ガバナンス**: Unity Catalog — テーブル/カラム Grants、Row Filters、Column Masks、UC Tags、自動リネージ（カラムレベル）、監査ログ（システムテーブル）、Lakehouse Monitoring（データ品質 + ドリフト）
- **Data Sharing**: Delta Sharing — オープンプロトコル、Snowflake/Pandas/Spark/Power BI から Databricks アカウントなしで読み取り可能
- **ONTAP 活用**: FlexClone（dev/test）、Snapshot（Delta Time Travel 補完）、FabricPool（コールドデータ階層化）
- **特徴**: 自動データリネージ（カラムレベル）、ML モデルガバナンス（MLflow + Model Registry）、Lakehouse Monitoring、Iceberg REST Catalog（外部エンジンから UC テーブルへのアクセス）
- **制限**: UC セッションポリシーが FSx for ONTAP S3 AP 上のテーブル作成とサブディレクトリ一覧を直接ブロック。**推奨パス: DataSync → S3 → UC**（フルガバナンス、フル AI、フルリネージ）

### Snowflake

- **認証**: Storage Integration + IAM Role
- **ネットワーク**: Internet network origin（PrivateLink オプション）
- **データ形式**: Parquet, CSV, JSON, Avro, ORC, Iceberg
- **非構造化データ**: Directory Table + Pre-signed URL + Cortex AI（PARSE_DOCUMENT で OCR、ステージング経由でマルチモーダル Vision）
- **AI 機能**: FSx for ONTAP データ上で 8/10 Cortex AI 関数検証済み（SUMMARIZE, TRANSLATE, SENTIMENT, COMPLETE, EXTRACT_ANSWER, PARSE_DOCUMENT, Cortex Search 198ms, Vision AI ステージング経由）
- **ガバナンス**: Object Tags, Row Access Policy, Column Masking, Data Sharing — External Table 上で全て検証済み
- **高度なパターン**: Dynamic Table（確認済み、FULL refresh、最小 60秒 TARGET_LAG）、Managed Iceberg Table（確認済み、ユーザー所有の S3 上のオープン形式）
- **ONTAP 活用**: Snapshot（Time Travel 超過分）、FlexClone（テスト環境）、マルチプロトコル（NFS/SMB/S3 同一データ）
- **Data Sharing**: Snowflake Data Sharing 経由でパートナー/サプライヤーへのガバナンス付き配布（External Table 共有可能）
- **既知の制限**: AUTO_REFRESH 利用不可（S3 Event Notifications なし）; Task + ALTER EXTERNAL TABLE REFRESH を使用

---

## オープンテーブルフォーマット & 分散 SQL

| フォーマット/エンジン | FSx for ONTAP S3 AP からの読み取り | FSx for ONTAP S3 AP への書き込み | S3 への書き込み（同期経由） | ステータス |
|-------------------|:---:|:---:|:---:|--------|
| **Apache Iceberg** | ⚠️ 実験的（既存テーブル） | ❌ 非サポート（NullPointerException） | ✅ EMR Spark → S3 | Part 7 検証済み |
| **Delta Lake (OSS)** | ✅ 読み取り検証済み（delta-rs） | ❌ 非サポート（501 Not Implemented） | ✅ DataSync → S3 → UC | Part 7 検証済み |
| **Apache Hudi** | ⚠️ 未テスト | ❌ 非サポート（atomic rename なし） | ✅ 標準 S3 パス | Part 7 検証済み |
| **Trino / Starburst** | ✅ 読み取り検証済み（5M 行、1.5秒） | ❌（同じ制限） | N/A | Part 0 検証済み |
| **Dremio** | 🔲 計画中 | 🔲 計画中 | N/A | 📋 NetApp/Dremio ジョイントソリューション（独自検証未実施） |

> **主要な発見（Part 7）**: 3つのトランザクショナルテーブルフォーマット（Delta, Iceberg, Hudi）は全て FSx for ONTAP S3 AP への書き込みに失敗。根本原因は S3 API の基本的な制限 — conditional writes なし（`If-None-Match` → 501）、atomic rename なし。既存テーブルの読み取りは理論的に可能だが、Delta read のみ検証済み。

### Apache Iceberg

- **読み取り**: 既存 Iceberg テーブル（Glue Catalog にメタデータ、FSx for ONTAP S3 AP にデータファイル）は GetObject 経由で理論的に読み取り可能。完全な検証は未実施。
- **書き込み**: ❌ S3FileIO が AP エイリアスでのメタデータ書き込み/検証を処理できない（コミット時に NullPointerException）。Conditional writes 非サポート。
- **動作する代替パス**: EMR Spark が標準 S3 に Iceberg を書き込み → Glue Catalog に登録 → Athena/Redshift/Snowflake/Databricks からクエリ。FSx for ONTAP S3 AP は読み取り専用ソースデータとして機能。
- **Snowflake パス**: FSx for ONTAP S3 AP → External Stage → COPY INTO → Snowflake Managed Iceberg Table（ユーザー所有の S3 上のオープン形式、2026年5月確認済み）
- **カタログオプション**: Glue Catalog（AWS ネイティブ）、Snowflake Managed Iceberg（Snowflake ネイティブ）、Databricks UC Iceberg REST Catalog（Databricks ネイティブ）

### Delta Lake (OSS)

- **読み取り**: ✅ delta-rs（Rust）で検証済み。Spark Delta reader も既存テーブルで動作。
- **書き込み**: ❌ Delta コミットプロトコルが `_delta_log/` に `If-None-Match` conditional write を要求 — FSx for ONTAP S3 AP は 501 Not Implemented を返す。
- **動作する代替パス**: DataSync → S3 → Delta Table（Databricks UC または OSS Spark）。FSx for ONTAP S3 AP は読み取り専用ソース。
- **Databricks パス**: DataSync → S3 → UC Managed Delta Table（フルガバナンス、リネージ、Time Travel）

### Apache Hudi

- **読み取り**: 未テスト（既存テーブルの GetObject 経由読み取りは理論的に可能）。
- **書き込み**: ❌ Hudi タイムラインコミットが atomic rename（`.inflight` → `.commit`）を要求。S3 に rename 操作なし。
- **動作する代替パス**: 標準 S3 バケットで Hudi 書き込みパス。FSx for ONTAP S3 AP は読み取り専用ソース。

### Trino / Starburst

- **読み取り**: ✅ 検証済み — Trino 481 + Glue Catalog + `hive.s3.path-style-access=true` + 明示的 `hive.s3.endpoint`。5M 行を 1.5秒。
- **書き込み**: 未テスト（トランザクショナル書き込みには同じ S3 AP 制限が適用）。
- **設定**: S3 AP エイリアス解決に `hive.s3.path-style-access=true` と明示的 `hive.s3.endpoint` が必要。DuckDB と同じパターン。
- **カタログ**: Glue Catalog（Athena、Redshift、EMR と共有）

### Dremio

- **認証**: IAM Role / Access Key
- **カタログ**: Nessie (Git-like catalog) / Arctic
- **特徴**: Iceberg ネイティブ、リフレクション（高速化）
- **ステータス**: 📋 **NetApp/Dremio ジョイントソリューション存在** — このリポジトリでの独自検証は未実施
- **NetApp パートナーシップ**: Dremio と NetApp が NetApp INSIGHT 2024（2024年9月）で Hybrid Iceberg Lakehouse ジョイントソリューションを発表。ONTAP S3、NAS、StorageGRID ソースをカバーする完全なデプロイメントガイドが [docs.netapp.com](https://docs.netapp.com/us-en/netapp-solutions/data-analytics/dremio-lakehouse-introduction.html) に存在。
- **FSx for ONTAP 統合**: NetApp ブログ（2025年1月）で Dremio Cloud + FSx for ONTAP S3 Access Points を NAS データ上の AI-ready 分析のジョイントソリューションとして紹介（[netapp.com](https://www.netapp.com/blog/ai-insights-ontap-s3-access-points-dremio/)）
- **主要機能**: Iceberg ネイティブクエリエンジン、リフレクション（マテリアライズド高速化）、セマンティックレイヤー、data-as-code（Nessie Git-like バージョニング）
- **Iceberg 相互運用性**: Dremio が書き込む Iceberg テーブルは Snowflake（External Iceberg Table）、Databricks（UC Iceberg）、Athena（Glue Catalog）、EMR、Trino から読み取り可能
- **このリポジトリで未検証の理由**: Dremio Cloud またはセルフマネージド Dremio インスタンスが必要。NetApp/Dremio ジョイントソリューションドキュメントがリファレンスアーキテクチャを提供。将来のフェーズで独自検証を追加する可能性あり。

---

## クラウドネイティブ分析（AWS）

| サービス | 統合方式 | ユースケース | ステータス |
|---------|---------|-------------|----------|
| **AWS Athena** | Glue Catalog 経由 S3 AP 直接クエリ | サーバーレス SQL | ✅ セキュリティ検証済み |
| **AWS Glue** | S3 AP Crawler / ETL Job | データカタログ + ETL + 書き戻し | ✅ 機能検証済み |
| **AWS Lake Formation** | Glue Catalog テーブルへのガバナンス | 細粒度アクセス制御（テーブル/カラム/行/タグ） | ✅ 検証済み（カラム、行フィルタ、LF-Tag） |
| **Amazon Redshift Spectrum** | Glue Catalog 上の External Schema | DWH + Data Lake フェデレーテッドクエリ | ✅ 機能検証済み |
| **Amazon EMR Serverless** | EMRFS (`s3://`) 直接アクセス | Spark ETL + 書き戻し | ✅ 機能検証済み |
| **Amazon Bedrock KB** | S3 AP をデータソースとして使用 | RAG / ドキュメント検索 | ✅ AWS ドキュメント記載パス |
| **DuckDB Lambda** | httpfs 拡張 + path-style | 軽量サーバーレス分析 | ✅ 機能検証済み |

### AWS Athena

- **認証**: IAM Role（サービスロール）
- **ネットワーク**: Internet network origin **必須**
- **特徴**: サーバーレス、従量課金（$5/TB スキャン）、Glue Catalog 統合
- **AI 統合**: Athena + Bedrock KB（同じ FSx for ONTAP データで RAG）、Athena + SageMaker（ML 推論 UDF）
- **ガバナンス**: Lake Formation（テーブル/カラム/行/タグ）— Athena と Redshift Spectrum に同じ権限が自動適用
- **書き戻し**: ✅ CTAS で FSx for ONTAP S3 AP に Parquet 書き戻し（検証済み、3.7秒）
- **特徴**: ゼロインフラ、全 AWS エンジンと Glue Catalog 共有、Lake Formation ガバナンス自動適用
- **ベンチマーク**: 54.8 MB/s ピーク（5M 行を 2.2秒）
- **参考**: [AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

### AWS Glue

- **認証**: Glue サービスロール
- **ネットワーク**: Internet network origin **必須**
- **特徴**: Crawler（スキーマ発見）、ETL Job（PySpark/Python Shell/Ray）、Data Quality
- **AI 統合**: Glue + Bedrock（AI 駆動変換）、Glue Data Quality（自動バリデーション）
- **ガバナンス**: Glue Data Catalog が Lake Formation の基盤 — 全権限はここで定義
- **書き戻し**: ✅ ETL 書き戻し（検証済み、10K 行メダリオンパイプライン 64秒）
- **特徴**: スキーマ発見（Crawler）、ビジュアル ETL（Studio）、サーバーレス Spark、Data Quality ルール
- **参考**: [AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

### AWS Lake Formation

- **認証**: Lake Formation admin + プリンシパルごとの grants
- **ネットワーク**: N/A（ガバナンスレイヤー、クエリエンジンではない）
- **特徴**: テーブル/カラムレベル grants、Row Filters（Data Cells Filter）、LF-Tags（タグベースアクセス制御）、クロスアカウント共有
- **AI 統合**: Bedrock KB、SageMaker、EMR ML ワークロードがアクセスするデータをガバナンス
- **ガバナンス**: ✅ 細粒度な AWS ネイティブガバナンス — 細粒度（カラム/行/タグ）、マルチエンジン（Athena + Redshift + EMR + Glue が同じ権限を共有）、データ移動なし
- **特徴**: 単一のガバナンス定義が全 AWS 分析エンジンに同時適用。エンジンごとの設定不要。データコピーなしのクロスアカウントテーブル共有。
- **検証済み機能（2026年5月）**: カラムレベル権限（特定カラム拒否）、Row Filter（式によるフィルタ）、LF-Tag（sensitivity 分類 + タグベース grants）

### Amazon Redshift Spectrum

- **認証**: S3 AP 権限付き Redshift IAM Role
- **ネットワーク**: Internet network origin **必須**
- **特徴**: DWH + Data Lake フェデレーテッドクエリ、マテリアライズドビュー、ストアドプロシージャ
- **AI 統合**: Redshift ML（CREATE MODEL）、SageMaker エンドポイントへのフェデレーテッドクエリ
- **ガバナンス**: Lake Formation（Athena と同じ権限 — 一度設定すれば全エンジンに適用）
- **書き戻し**: ❌（クエリ結果は Redshift に残る; 書き戻しには EMR を使用）
- **特徴**: NAS データとローカル DWH テーブルの JOIN、外部データ上のマテリアライズドビュー、Athena と同じ Glue Catalog
- **ベンチマーク**: 5M 行を 4.3秒（Serverless 8 RPU）

### Amazon EMR Serverless (Spark)

- **認証**: 実行ロール（IAM）
- **ネットワーク**: Internet network origin（EMRFS が S3 AP をネイティブ処理）
- **特徴**: フル Spark SQL、UDF、ウィンドウ関数、MLlib、分散処理
- **AI 統合**: Spark MLlib、SageMaker Spark コネクタ、S3 上の Iceberg テーブル作成
- **ガバナンス**: IAM ベース（出力のガバナンス読み取りには Lake Formation と組み合わせ）
- **書き戻し**: ✅ 検証済みの書き戻しパス — FSx for ONTAP S3 AP にフラット Parquet（検証済み、16秒 ETL 合計）
- **特徴**: セッションポリシー問題なし（直接 IAM）、フル Spark パワー、FSx for ONTAP への書き戻し、S3 上の Iceberg テーブル作成
- **ベンチマーク**: 10K 行 読み取り+変換+書き込み 16秒、$0.05/ジョブ
- **重要**: `s3://`（EMRFS）を使用。`s3a://` は AP エイリアスをパースできない

### Amazon Bedrock Knowledge Bases

- **認証**: Bedrock サービスロール（S3 AP 権限付き）
- **ネットワーク**: Internet network origin
- **特徴**: RAG ドキュメント取り込み、ベクトル embedding、権限認識型検索
- **AI 統合**: ✅ **ネイティブ RAG パス** — FSx for ONTAP S3 AP からドキュメント取り込み、embedding 作成、ガードレール付きセマンティック検索
- **ガバナンス**: Bedrock ガードレール（トピックフィルタリング、PII 検出、ハルシネーション低減）、IAM モデルアクセスポリシー
- **特徴**: ゼロコピー RAG（COPY INTO なしで FSx for ONTAP S3 AP から直接読み取り）、権限認識型検索、マルチステップ推論の Bedrock エージェント
- **参考**: [AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)

### DuckDB Lambda

- **認証**: Lambda 実行ロール（IAM）
- **ネットワーク**: Internet network origin（VPC 不要）
- **特徴**: インプロセス SQL、サブ秒ウォームクエリ、arm64（Graviton2）
- **AI 統合**: 最小限（SQL のみ; AI には Bedrock と組み合わせ）
- **ガバナンス**: IAM + S3 AP ポリシーのみ（テーブルレベルガバナンスなし）
- **書き戻し**: ✅ COPY TO Parquet（検証済み、304ms）
- **特徴**: 低コストなパス（$0.00001/クエリ）、ゼロアイドルコスト、サブ秒ウォームレイテンシ（452ms）
- **ベンチマーク**: 10K 行 452ms（ウォーム）、5M 行 779ms

### AWS ネイティブ構成の特徴

| 特徴 | 詳細 |
|--------|------|
| **セッションポリシー問題なし** | 全 AWS サービスが直接 IAM を使用 — S3 AP ARN 形式をブロックする中間セッションポリシーなし |
| **Glue Catalog 共有** | Athena、Redshift Spectrum、EMR、Glue が同じカタログを共有。一度登録すれば全エンジンからクエリ可能 |
| **Lake Formation マルチエンジン** | 単一のガバナンス定義が全エンジンに同時適用。プラットフォームごとの設定不要 |
| **ゼロコピー RAG** | Bedrock KB が FSx for ONTAP S3 AP から直接読み取り — COPY INTO なし、ステージングなし、RAG のためのデータ移動なし |
| **サーバーレスファースト** | Athena、Glue、EMR Serverless、Lambda — スタック全体でゼロアイドルコスト |
| **書き戻し検証済み** | EMR、Athena CTAS、DuckDB が FSx for ONTAP S3 AP にフラット Parquet を書き戻し可能（Snowflake/Databricks は不可） |
| **S3 上の Iceberg** | EMR Spark が標準 S3 に Iceberg テーブル作成 → Glue Catalog に登録 → Athena/Redshift/Snowflake/Databricks からクエリ可能 |
- **ネットワーク**: Internet network origin
- **特徴**: OneLake 統合、Power BI 連携
- **非構造化データ**: OneLake Shortcut 経由でファイルアクセス

---

## 新興・特化型プラットフォーム

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

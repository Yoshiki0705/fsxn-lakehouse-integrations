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
- **非構造化データ**: UC Volumes + `read_files()` + `ai_query()`（画像/ドキュメントに LLM）+ `ai_parse_document()`（OCR）
- **AI 機能**: Mosaic AI（ML トレーニング、Feature Store、Model Registry）、`ai_query`（ファイルに LLM）、`ai_parse_document`（OCR）、Vector Search（RAG）、MLflow 実験追跡
- **ガバナンス**: Unity Catalog — テーブル/カラム Grants、Row Filters、Column Masks、UC Tags、自動リネージ（カラムレベル）、監査ログ（システムテーブル）、Lakehouse Monitoring（データ品質 + ドリフト）
- **Data Sharing**: Delta Sharing — オープンプロトコル、Snowflake/Pandas/Spark/Power BI から Databricks アカウントなしで読み取り可能
- **ONTAP 活用**: FlexClone（dev/test）、Snapshot（Delta Time Travel 補完）、FabricPool（コールドデータ階層化）
- **独自の強み**: 自動データリネージ（カラムレベル）、ML モデルガバナンス（MLflow + Model Registry）、Lakehouse Monitoring、Iceberg REST Catalog（外部エンジンから UC テーブルへのアクセス）
- **制限**: UC セッションポリシーが FSx S3 AP 上のテーブル作成とサブディレクトリ一覧を直接ブロック。**推奨パス: DataSync → S3 → UC**（フルガバナンス、フル AI、フルリネージ）

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

## Tier 3: クラウドネイティブ分析 (AWS)

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
- **AI 統合**: Athena + Bedrock KB（同じ FSx データで RAG）、Athena + SageMaker（ML 推論 UDF）
- **ガバナンス**: Lake Formation（テーブル/カラム/行/タグ）— Athena と Redshift Spectrum に同じ権限が自動適用
- **書き戻し**: ✅ CTAS で FSx S3 AP に Parquet 書き戻し（検証済み、3.7秒）
- **独自の強み**: ゼロインフラ、全 AWS エンジンと Glue Catalog 共有、Lake Formation ガバナンス自動適用
- **ベンチマーク**: 54.8 MB/s ピーク（5M 行を 2.2秒）
- **参考**: [AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

### AWS Glue

- **認証**: Glue サービスロール
- **ネットワーク**: Internet network origin **必須**
- **特徴**: Crawler（スキーマ発見）、ETL Job（PySpark/Python Shell/Ray）、Data Quality
- **AI 統合**: Glue + Bedrock（AI 駆動変換）、Glue Data Quality（自動バリデーション）
- **ガバナンス**: Glue Data Catalog が Lake Formation の基盤 — 全権限はここで定義
- **書き戻し**: ✅ ETL 書き戻し（検証済み、10K 行メダリオンパイプライン 64秒）
- **独自の強み**: スキーマ発見（Crawler）、ビジュアル ETL（Studio）、サーバーレス Spark、Data Quality ルール
- **参考**: [AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

### AWS Lake Formation

- **認証**: Lake Formation admin + プリンシパルごとの grants
- **ネットワーク**: N/A（ガバナンスレイヤー、クエリエンジンではない）
- **特徴**: テーブル/カラムレベル grants、Row Filters（Data Cells Filter）、LF-Tags（タグベースアクセス制御）、クロスアカウント共有
- **AI 統合**: Bedrock KB、SageMaker、EMR ML ワークロードがアクセスするデータをガバナンス
- **ガバナンス**: ✅ **最強の AWS ネイティブガバナンス** — 細粒度（カラム/行/タグ）、マルチエンジン（Athena + Redshift + EMR + Glue が同じ権限を共有）、データ移動なし
- **独自の強み**: 単一のガバナンス定義が全 AWS 分析エンジンに同時適用。エンジンごとの設定不要。データコピーなしのクロスアカウントテーブル共有。
- **検証済み機能（2026年5月）**: カラムレベル権限（特定カラム拒否）、Row Filter（式によるフィルタ）、LF-Tag（sensitivity 分類 + タグベース grants）

### Amazon Redshift Spectrum

- **認証**: S3 AP 権限付き Redshift IAM Role
- **ネットワーク**: Internet network origin **必須**
- **特徴**: DWH + Data Lake フェデレーテッドクエリ、マテリアライズドビュー、ストアドプロシージャ
- **AI 統合**: Redshift ML（CREATE MODEL）、SageMaker エンドポイントへのフェデレーテッドクエリ
- **ガバナンス**: Lake Formation（Athena と同じ権限 — 一度設定すれば全エンジンに適用）
- **書き戻し**: ❌（クエリ結果は Redshift に残る; 書き戻しには EMR を使用）
- **独自の強み**: NAS データとローカル DWH テーブルの JOIN、外部データ上のマテリアライズドビュー、Athena と同じ Glue Catalog
- **ベンチマーク**: 5M 行を 4.3秒（Serverless 8 RPU）

### Amazon EMR Serverless (Spark)

- **認証**: 実行ロール（IAM）
- **ネットワーク**: Internet network origin（EMRFS が S3 AP をネイティブ処理）
- **特徴**: フル Spark SQL、UDF、ウィンドウ関数、MLlib、分散処理
- **AI 統合**: Spark MLlib、SageMaker Spark コネクタ、S3 上の Iceberg テーブル作成
- **ガバナンス**: IAM ベース（出力のガバナンス読み取りには Lake Formation と組み合わせ）
- **書き戻し**: ✅ **最強の書き戻しパス** — FSx S3 AP にフラット Parquet（検証済み、16秒 ETL 合計）
- **独自の強み**: セッションポリシー問題なし（直接 IAM）、フル Spark パワー、FSx への書き戻し、S3 上の Iceberg テーブル作成
- **ベンチマーク**: 10K 行 読み取り+変換+書き込み 16秒、$0.05/ジョブ
- **重要**: `s3://`（EMRFS）を使用。`s3a://` は AP エイリアスをパースできない

### Amazon Bedrock Knowledge Bases

- **認証**: Bedrock サービスロール（S3 AP 権限付き）
- **ネットワーク**: Internet network origin
- **特徴**: RAG ドキュメント取り込み、ベクトル embedding、権限認識型検索
- **AI 統合**: ✅ **ネイティブ RAG パス** — FSx S3 AP からドキュメント取り込み、embedding 作成、ガードレール付きセマンティック検索
- **ガバナンス**: Bedrock ガードレール（トピックフィルタリング、PII 検出、ハルシネーション低減）、IAM モデルアクセスポリシー
- **独自の強み**: ゼロコピー RAG（COPY INTO なしで FSx S3 AP から直接読み取り）、権限認識型検索、マルチステップ推論の Bedrock エージェント
- **参考**: [AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)

### DuckDB Lambda

- **認証**: Lambda 実行ロール（IAM）
- **ネットワーク**: Internet network origin（VPC 不要）
- **特徴**: インプロセス SQL、サブ秒ウォームクエリ、arm64（Graviton2）
- **AI 統合**: 最小限（SQL のみ; AI には Bedrock と組み合わせ）
- **ガバナンス**: IAM + S3 AP ポリシーのみ（テーブルレベルガバナンスなし）
- **書き戻し**: ✅ COPY TO Parquet（検証済み、304ms）
- **独自の強み**: 最安パス（$0.00001/クエリ）、ゼロアイドルコスト、サブ秒ウォームレイテンシ（452ms）
- **ベンチマーク**: 10K 行 452ms（ウォーム）、5M 行 779ms

### AWS ネイティブ固有の価値提案

| 優位性 | 詳細 |
|--------|------|
| **セッションポリシー問題なし** | 全 AWS サービスが直接 IAM を使用 — S3 AP ARN 形式をブロックする中間セッションポリシーなし |
| **Glue Catalog 共有** | Athena、Redshift Spectrum、EMR、Glue が同じカタログを共有。一度登録すれば全エンジンからクエリ可能 |
| **Lake Formation マルチエンジン** | 単一のガバナンス定義が全エンジンに同時適用。プラットフォームごとの設定不要 |
| **ゼロコピー RAG** | Bedrock KB が FSx S3 AP から直接読み取り — COPY INTO なし、ステージングなし、RAG のためのデータ移動なし |
| **サーバーレスファースト** | Athena、Glue、EMR Serverless、Lambda — スタック全体でゼロアイドルコスト |
| **書き戻し検証済み** | EMR、Athena CTAS、DuckDB が FSx S3 AP にフラット Parquet を書き戻し可能（Snowflake/Databricks は不可） |
| **S3 上の Iceberg** | EMR Spark が標準 S3 に Iceberg テーブル作成 → Glue Catalog に登録 → Athena/Redshift/Snowflake/Databricks からクエリ可能 |
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

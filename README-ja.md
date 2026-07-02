🌐 [English](./README.md) | **日本語**

# FSx for ONTAP Lakehouse Integrations

> **FSx for ONTAP S3 Access Points と各種分析・Lakehouse エンジンの連携を検証するフレームワーク。** 各ディレクトリに再現可能なエビデンス、テストテンプレート、観察された制約のドキュメントを収録しています（本番環境用コネクタではありません）。

---

## ここから始める — 役割に合ったパスを選択

| あなたの役割 | まず読むドキュメント | 所要時間 |
|------------|-------------------|:-------:|
| 📊 **ビジネスリーダー / 営業 / アカウントマネージャー** | [**わかりやすいビジネスガイド**](docs/ja/quickstart-business-guide.md) — 専門用語なし、何ができるか、いくらかかるか | 5分 |
| 🏭 **業界ソリューションアーキテクト** | [**業界別ソリューションカタログ**](docs/ja/industry-solution-catalog.md) — 26 業界、ユースケース別推奨パターン | 20分 |
| 🔧 **技術リード / データエンジニア** | [**UC 接続総合ガイド**](docs/ja/fsx-ontap-to-databricks-unity-catalog-guide.md) — フルアーキテクチャ、全パス、制約 | 30分 |
| 🚀 **実装パートナー / SI** | [**PoC 実行ガイド**](docs/implementation-guide/poc-execution-guide-ja.md) — ステップバイステップチェックリスト | 15分 |
| 📐 **ソリューションアーキテクト** | [**アーキテクチャ比較**](docs/adoption-guide/architecture-comparison-ja.md) — 判断フレームワーク、トレードオフ | 15分 |
| 🔍 **コストを評価したい** | [**コスト見積もり**](docs/adoption-guide/cost-estimation-ja.md) — コンポーネント別内訳、スケーリング数式 | 10分 |

---

## 概要

**既存のエンタープライズファイル資産を、NFS/SMB ワークロードを中断することなく、分析・AI 対応データに変換します。**

Amazon FSx for NetApp ONTAP（FSx for ONTAP）の S3 Access Points 経由で、各 Data Lake / Lakehouse プラットフォームと統合するパターン集です。

---

## ビジネス成果

| 成果 | 説明 |
|------|------|
| **データコピーの排除** | N 個の冗長コピー → FSx for ONTAP 上の 1 つの正式ソースに集約 |
| **NAS→S3 同期パイプラインの廃止** | 分析のためにファイルデータを S3 にコピーする ETL ジョブが不要 |
| **インサイトまでの時間短縮** | パイプライン構築に数日 → S3 Access Point 経由の直接クエリで数時間に |
| **既存 NFS/SMB ワークロードの維持** | アプリケーションは NFS/SMB 経由の書き込みをそのまま継続 |
| **ガバナンスの統一** | 単一データ格納場所 + 二層アクセス制御（IAM + ファイルシステム権限） |
| **ファイルデータでの AI/ML 活用** | Amazon Bedrock、SageMaker、EMR がデータ移動なしで既存ファイルにアクセス |

FSx for ONTAP S3 Access Points により、データ移動なしでファイルデータへの S3 API アクセスが可能になり、S3 互換アプリケーションや AWS サービスがファイルデータを直接読み書きできます。（[AWS ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)）

---

## コア技術機能

<details>
<summary>ONTAP 機能と Lakehouse での利点（クリックで展開）</summary>

| ONTAP 機能 | Lakehouse での利点 |
|------------|-------------------|
| 重複排除 & 圧縮 | 類似データセットのストレージコスト削減 |
| Snapshot | Delta/Iceberg タイムトラベルを補完するポイントインタイムリカバリ（[Recovery Semantics](docs/ja/recovery-semantics.md) 参照） |
| FlexClone | 開発/テストデータセットの瞬時プロビジョニング |
| SnapMirror | Lakehouse データのクロスリージョン DR |
| FabricPool 階層化 | コールドデータの S3 への自動オフロード |
| マルチプロトコル (NFS/SMB/iSCSI/S3) | あらゆるワークロードからの統一アクセス |

</details>

---

## アーキテクチャパターン

<details>
<summary>5 つのアーキテクチャパターン（クリックで展開）</summary>

### パターン A: 読み取り専用分析

```
Lakehouse Platform → (S3 API) → S3 Access Point → FSx for ONTAP Volume
```

- External Table / External Stage として登録
- Parquet、CSV、JSON、ORC ファイルを直接クエリ

### パターン B: 読み書きマネージドテーブル

```
Lakehouse Platform ←→ S3 Access Point ←→ FSx for ONTAP Volume
```

- Iceberg / Delta / Hudi テーブルのストレージレイヤーとして使用
- ONTAP Snapshot によるポイントインタイムテーブルリカバリ

### パターン C: ETL パイプライン（メダリオンアーキテクチャ）

```
Source (FSx for ONTAP) → S3 AP → Glue/EMR/Lambda → Transform → S3 AP → FSx for ONTAP (curated)
```

- Raw → Bronze → Silver → Gold

### パターン D: データ共有

```
FSx for ONTAP (Producer) → S3 AP (スコープドポリシー) → Consumer Platform
```

- S3 AP ポリシーによるコンシューマー別アクセス制御
- ONTAP FlexClone による瞬時論理コピー

### パターン E: OpenSharing（ゼロコピーガバナンスアクセス）— 分析段階

```
FSx for ONTAP → OpenSharing Server (共有 + アクセス制御)
                    → Catalog (ガバナンス境界)
                    → Lakehouse Serverless Compute (インプレースクエリ)
                    → Iceberg IRC clients (クロスエンジン)
```

- [OpenSharing 発表](https://www.databricks.com/company/newsroom/press-releases/databricks-announces-opensharing)（2026-06-10）に基づく将来的パターン（Delta Sharing の Linux Foundation ホスティングへの進化）
- Presigned-URL 共有モデルが現在の Databricks S3 AP ARN 制限をバイパスする可能性（仮説検証中）
- [OpenSharing 統合分析](docs/ja/opensharing-integration-analysis.md) を参照

</details>

---

## 対応プラットフォーム

<details>
<summary>プラットフォーム検証ステータス（クリックで展開）</summary>

| プラットフォーム | 検証ステータス | パターン | 備考 |
|----------------|:---:|---------|------|
| [AWS Athena](integrations/athena/) | ✅ セキュリティ検証済み | Glue Data Catalog + Serverless | 読み取り専用。[ベンチマーク: 54.8 MB/s、5M 行 2 秒](verification-pack/athena-parquet-read/) |
| [AWS Glue ETL](integrations/glue/) | ✅ 機能検証済み | Crawler + ETL + Medallion | 読み取り + 書き戻し (Parquet)。[10K 行 ETL 64 秒](verification-pack/glue-etl/) |
| [Delta Lake OSS](integrations/delta-lake-oss/) | ✅ 読み取り検証 / ❌ 書き込み | delta-rs + Spark | 読み取り可。書き込みは 501（条件付き書き込み非対応）|
| [Databricks](integrations/databricks/) | ⚠️ ブロック中 | Unity Catalog + Delta Lake | セッションポリシーが S3 AP ARN 形式を認識しない。サポートケース提出済み。OpenSharing パス分析中（[パターン E](#パターン-e-opensharingゼロコピーガバナンスアクセス-分析段階) 参照）|
| [Snowflake](integrations/snowflake/) | ✅ 検証済み | External Stage + External Table | `AWS_ACCESS_POINT_ARN` ステージパラメータで動作。SELECT + External Table 検証済み |
| [Apache Iceberg](integrations/iceberg/) | ⚠️ 読み取り実験的 / ❌ 書き込み失敗 | REST Catalog（ベンダー中立） | 書き込み失敗: S3FileIO が AP エイリアスを処理不可。既存テーブルの読み取りは動作見込み |
| [Iceberg メタデータカタログ](integrations/iceberg-metadata-catalog/) | ✅ AWS ネイティブ検証済み / ⚠️ クロスプラットフォーム進行中 | S3 Tables + PyIceberg + Glue REST + Bedrock | AI メタデータカタログ。AWS パス検証済み; Databricks/Snowflake パス検証中。[詳細](integrations/iceberg-metadata-catalog/docs/poc-results-summary.md) |
| [EMR + Spark](integrations/emr-spark/) | ✅ 機能検証済み | Spark SQL + Iceberg | 読み取り + 書き戻し検証済み。[10K 行 16 秒 (EMR Serverless)](verification-pack/emr-spark/) |
| [Redshift Spectrum](integrations/redshift-spectrum/) | ✅ 機能検証済み | External Schema | Athena と同パターン。[5M 行 4.3 秒](verification-pack/redshift-spectrum/) |
| [DuckDB](integrations/duckdb/) | ✅ 機能検証済み | Lambda 軽量分析 | 読み取り + 書き戻し。[5M 行 779ms、書き戻し 304ms](integrations/duckdb/) |
| [製造データプラットフォーム](integrations/manufacturing-data-platform/) | 🔧 設計 + PoC | Kafka + ClickHouse + Databricks (streaming) | エッジ→クラウドストリーミングパイプライン。[エッジプロジェクト](#関連プロジェクト)と連携。[Edge ↔ Lakehouse 同期](integrations/manufacturing-data-platform/docs/ja/14_edge_lakehouse_sync.md) |
| [Dremio](integrations/dremio/) | 🔲 計画中 | Arctic Catalog | — |
| [Trino / Starburst](integrations/trino-starburst/) | 🔲 計画中 | Hive Connector | — |
| [BigQuery Omni](integrations/bigquery-omni/) | 🔲 計画中 | BigLake | GCP 環境が必要 |
| [Microsoft Fabric](integrations/microsoft-fabric/) | 🔲 計画中 | OneLake Shortcut | Azure 環境が必要 |

> **主要な発見**: AWS ネイティブサービス（Athena、Glue、EMR、Bedrock）は正常に動作。サードパーティプラットフォームは明示的な S3 AP ARN 設定が必要: Snowflake は `AWS_ACCESS_POINT_ARN`（完全解決済み）、Databricks は `access_point` フィールド（部分解決）。詳細は [互換性マトリクス](docs/ja/compatibility-matrix.md) を参照。

</details>

---

## エンジン選定ガイド

<details>
<summary>ユースケース別の推奨エンジン（クリックで展開）</summary>

| 主要な質問 | 推奨エンジン | アクセスパターン | ガバナンス | AI 対応度 | PoC コスト (1日) |
|---|---|---|---|---|---|
| 「NAS データを最安で検索したい」 | DuckDB Lambda | ゼロコピー | なし (IAM のみ) | 発見 / プロファイリング | ~$0.01 |
| 「サーバーレス SQL、インフラ不要」 | Athena | ゼロコピー | Glue + Lake Formation | 発見 → キュレーション | ~$0.05 |
| 「Spark ETL で書き戻しが必要」 | EMR Serverless | ゼロコピー (読み取り) + FSx for ONTAP に書き込み | IAM | Parquet / Iceberg 作成 | ~$0.50 |
| 「DWH JOIN + エンタープライズガバナンスが必要」 | Redshift Spectrum + Lake Formation | ゼロコピー | Lake Formation (列/行/タグ) | ガバナンス付き分析 | ~$1.50 |
| 「NAS データで AI（要約、RAG、感情分析）」 | Snowflake External Table + Cortex | ゼロコピー | Snowflake RBAC + Tags | AI 対応 (Cortex AI 即時利用可) | ~$5 |
| 「Databricks 利用中、フル UC + ML が必要」 | DataSync → S3 → UC | S3 同期あり | Unity Catalog (フル) | フル ML/AI (Mosaic AI, Feature Store) | ~$10 |
| 「FSx for ONTAP で Delta/Iceberg は使える？」 | No — FSx for ONTAP から読み取り、S3 に書き込み | 読み取り: ゼロコピー、書き込み: S3 | エンジンに依存 | エンジンに依存 | ~$0.50 |

### FSx for ONTAP + S3 AP が適するケース (vs S3 のみ)

| 検討事項 | S3 のみ | FSx for ONTAP + S3 AP |
|---|---|---|
| 既存 NFS/SMB ワークロード | マイグレーションまたはデュアルパス維持が必要 | 変更不要 — 既存アプリは NFS/SMB を継続 |
| ストレージ効率 | 重複排除/圧縮なし | ONTAP 重複排除 + 圧縮 (1.5-2x 典型) |
| ポイントインタイムリカバリ | S3 Versioning (オブジェクト単位、大規模で高コスト) | ONTAP Snapshot (ボリューム単位、瞬時、スペース効率良) |
| 開発/テストデータプロビジョニング | フルコピーが必要 | FlexClone (瞬時ゼロコピークローン) |
| マルチプロトコルアクセス | S3 のみ | NFS + SMB + S3 で同一データに同時アクセス |
| アプリケーション変更の要否 | 必要 (S3 SDK に書き換え) | 不要 (NFS/SMB そのまま、S3 AP は追加的) |

### オープンテーブルフォーマット: マルチプラットフォームブリッジ

Snowflake と Databricks を両方使う環境では、オープン Iceberg フォーマットでキュレーション済みデータを共有可能:

```
FSx for ONTAP (ソース) → S3 AP / DataSync → S3 → Snowflake Managed Iceberg Table
                                                          ↓
                                                同一 Iceberg on S3
                                                          ↓
                                    Databricks UC / Athena / EMR (Iceberg 読み取り)
```

ベンダーロックインなし。データオーナーシップは保持。各プラットフォームが独自のガバナンスを適用。

---

## ユースケース

> [業界別ソリューションカタログ](docs/ja/industry-solution-catalog.md) で 26 業界をカバー。代表例を以下に掲載。

| 業界 | ユースケース | 主要パターン |
|------|------------|-------------|
| 製造 / 産業 | 品質分析、予知保全、トレーサビリティ | DataSync / Kafka (FPolicy) |
| 自動車 | ADAS/AD データ、コネクテッドカー、部品系譜 | DataSync / Kafka |
| 金融 / 保険 | リスク分析、不正検知、規制報告 | DataSync / Glue ETL |
| 医療 / ライフサイエンス | EHR 分析、ゲノミクス、医療画像 | DataSync / Glue ETL |
| 半導体 / EDA | チップ設計検証、テープアウト分析 | Glue/EMR / DataSync |
| メディア / エンターテインメント | 映像メタデータ、コンテンツ分類、DAM | パターン A（読み取り専用） |
| 小売 / EC | POS 分析、需要予測、顧客 360 | DataSync / Kafka |
| エネルギー / ユーティリティ | グリッド監視、アセット管理、コンプライアンス | DataSync / Kafka |
| 通信 | CDR 分析、ネットワーク品質、IoT ゲートウェイ | Kafka → Structured Streaming |
| 公共セクター | 文書アーカイブ検索、情報公開、データ主権 | DataSync (SnapLock) |
| 農業 | 精密農業、気象データ、収量予測 | DataSync / S3 Tables |
| 物流 / サプライチェーン | 追跡、ルート最適化、倉庫分析 | Kafka → UC Delta |
| 建設 / BIM | 3D モデルメタデータ、安全検査、進捗 | DataSync / Glue ETL |
| 教育 / 研究 | 研究データカタログ、e ラーニング分析 | DataSync / S3 Tables |

全 26 業界のガバナンス考慮事項、注意点、推奨パスは [業界別ソリューションカタログ](docs/ja/industry-solution-catalog.md) を参照。

</details>

---

## クイックスタート

<details>
<summary>前提条件とデプロイコマンド（クリックで展開）</summary>

### 前提条件

- FSx for NetApp ONTAP を持つ AWS アカウント
- FSx for ONTAP SVM で S3 Access Points が有効
- AWS CLI v2 設定済み
- Python 3.12+
- **重要**: 分析プラットフォームと FSx for ONTAP は同一 AWS リージョンに配置する必要があります。
  [リージョン設計ガイド](docs/ja/region-design-guide.md) を参照

### ベースインフラストラクチャのデプロイ

```bash
# ターゲットリージョンを設定（FSx for ONTAP と一致させること）
export AWS_REGION=<YOUR_REGION>  # 例: ap-northeast-1, us-east-1, eu-west-1

# VPC + FSx for ONTAP + S3 Access Point をデプロイ
aws cloudformation deploy \
  --template-file shared/cloudformation/vpc-networking.yaml \
  --stack-name fsxn-lakehouse-vpc \
  --capabilities CAPABILITY_IAM \
  --region ${AWS_REGION}

aws cloudformation deploy \
  --template-file shared/cloudformation/fsxn-s3ap-base.yaml \
  --stack-name fsxn-lakehouse-base \
  --capabilities CAPABILITY_IAM \
  --region ${AWS_REGION}
```

### S3 AP アクセスの検証

```bash
python shared/scripts/validate-access.py \
  --access-point-arn arn:aws:s3:${AWS_REGION}:<YOUR_ACCOUNT_ID>:accesspoint/fsxn-lakehouse \
  --region ${AWS_REGION}
```

</details>

---

## リポジトリ構造

<details>
<summary>ディレクトリ構成（クリックで展開）</summary>

```
fsxn-lakehouse-integrations/
├── README.md                    # English version
├── README-ja.md                 # 本ファイル（日本語）
├── docs/                        # ドキュメント
│   ├── ja/                      # 日本語ドキュメント
│   ├── en/                      # 英語ドキュメント
│   ├── adoption-guide/          # 技術採用ガイド (JA/EN ペア)
│   ├── implementation-guide/    # PoC 実行ガイド (JA/EN ペア)
│   └── images/                  # 図表
├── shared/                      # 共通モジュール
│   ├── cloudformation/          # ベース CFn テンプレート
│   ├── scripts/                 # ユーティリティスクリプト
│   └── sample-data/             # サンプルデータセット
├── integrations/                # プラットフォーム別実装
│   ├── databricks/
│   ├── snowflake/
│   ├── iceberg/
│   └── ...
├── use-cases/                   # 業界別ユースケース
│   ├── financial-data-mesh/
│   ├── manufacturing-iot-lake/
│   └── ...
└── .github/workflows/           # CI/CD
```

</details>

---

## 技術スタック

<details>
<summary>言語、フレームワーク、テスト済みバージョン（クリックで展開）</summary>

- **インフラストラクチャ**: CloudFormation (YAML) + Terraform (Databricks/Snowflake)
- **スクリプト**: Python 3.12, Bash
- **ノートブック**: Jupyter / Databricks Notebooks
- **SQL**: Snowflake SQL, Athena SQL, Trino SQL
- **テスト**: pytest, cfn-lint
- **ドキュメント**: Markdown（日英バイリンガル）

### テスト済み環境 (Iceberg メタデータカタログ)

| コンポーネント | バージョン | 備考 |
|-------------|---------|------|
| Python | 3.12+ | macOS/Linux |
| PyIceberg | 0.7+ (テスト済み 0.11.1) | `[s3tables]` エクストラ付き |
| Apache Iceberg | format-version 2 | ソフトデリート用 Position Delete Files |
| S3 Tables | GA (2024-12) | 自動コンパクション、Iceberg REST エンドポイント |
| OpenSearch Serverless NextGen | GA (2026-05-28) | スケールトゥゼロ、kNN ベクトル検索 |
| Amazon Bedrock | Claude 3 Haiku, Titan Embeddings V2 | ビジョン分類 + 1024次元埋め込み |
| PyArrow | 17.0+ (テスト済み 24.0.0) | Arrow ベース Iceberg 書き込み |

</details>

---

## ドキュメント

<details>
<summary>全ドキュメント索引（クリックで展開）</summary>

| ドキュメント | リンク |
|------------|------|
| **最初に読む（非技術者向け）** | [**わかりやすいビジネスガイド**](docs/ja/quickstart-business-guide.md) |
| アーキテクチャ | [アーキテクチャ](docs/ja/architecture.md) |
| Getting Started | [クイックスタート](docs/ja/getting-started.md) |
| リージョン設計ガイド | [リージョン設計ガイド](docs/ja/region-design-guide.md) |
| 対応リージョン | [対応リージョン](docs/ja/supported-regions.md) |
| ベンダー比較 | [ベンダー比較](docs/ja/vendor-comparison.md) |
| 非構造化データ | [非構造化データ](docs/ja/unstructured-data-access.md) |
| 互換性マトリクス | [互換性マトリクス](docs/ja/compatibility-matrix.md) |
| リカバリセマンティクス | [リカバリセマンティクス](docs/ja/recovery-semantics.md) |
| ガバナンスとコンプライアンス | [ガバナンスとコンプライアンス](docs/ja/governance-and-compliance.md) |
| ゼロコピー非構造化データガバナンス | [ゼロコピーガバナンス](docs/ja/zero-copy-media-governance.md) |
| OpenSharing 統合分析 | [OpenSharing 統合分析](docs/ja/opensharing-integration-analysis.md) |
| KPI と PoC 検証 | [KPI と PoC 検証](docs/ja/kpi-and-validation.md) |
| **FSx for ONTAP → Databricks UC ガイド** | [**UC 接続総合ガイド**](docs/ja/fsx-ontap-to-databricks-unity-catalog-guide.md) |
| DataSync → S3 ガイド | [DataSync ガイド](docs/ja/datasync-to-s3-guide.md) |
| Kafka-ClickHouse-UC 接続 | [Kafka-CH-UC 接続](docs/ja/kafka-clickhouse-unity-catalog-connectivity.md) |
| S3 Annotations ガバナンス | [S3 Annotations 評価](docs/ja/s3-annotations-governance-evaluation.md) |
| 業界別ソリューションカタログ | [業界別カタログ](docs/ja/industry-solution-catalog.md) |
| **採用ガイド** | |
| テクニカルオーバービュー | [テクニカルオーバービュー](docs/adoption-guide/technical-overview-ja.md) |
| アーキテクチャ比較 | [アーキテクチャ比較](docs/adoption-guide/architecture-comparison-ja.md) |
| テクニカル FAQ | [テクニカル FAQ](docs/adoption-guide/technical-faq-ja.md) |
| コスト見積もり | [コスト見積もり](docs/adoption-guide/cost-estimation-ja.md) |
| **実装ガイド** | |
| PoC 実行ガイド | [PoC 実行ガイド](docs/implementation-guide/poc-execution-guide-ja.md) |

</details>

---

## ブログシリーズ

<details>
<summary>公開済み・進行中のブログシリーズ（クリックで展開）</summary>

### シリーズ 1: 「FSx for ONTAP S3 Access Points × Lakehouse Deep Dive」（公開済み）

dev.to（英語）+ はてなブログ（日本語）での検証シリーズ:

| パート | プラットフォーム | 日本語 | English |
|:---:|----------|-----|-----|
| 0 | シリーズ概要 — 何が動き、何が動かず、なぜか | [はてなブログ](https://hakobiya.hatenablog.com/entry/fsxn-lakehouse-part0-overview) | [dev.to](https://dev.to/aws-builders/fsx-for-ontap-s3-access-points-x-lakehouse-what-works-what-doesnt-and-why-1jo3) |
| 1 | Athena — NAS データをインプレースでクエリ | [はてなブログ](https://hakobiya.hatenablog.com/entry/fsxn-lakehouse-part1-athena) | [dev.to](https://dev.to/aws-builders/query-nas-data-in-place-with-athena-and-fsx-for-ontap-s3-access-points-3lhh) |
| 2 | Databricks — レイヤーごとの境界検証 | [はてなブログ](https://hakobiya.hatenablog.com/entry/fsxn-lakehouse-part2-databricks) | [dev.to](https://dev.to/aws-builders/databricks-and-fsx-for-ontap-s3-access-points-a-layer-by-layer-validation-of-observed-boundaries-p4d) |
| 3 | Snowflake — ゼロコピー読み取り + Cortex AI | [はてなブログ](https://hakobiya.hatenablog.com/entry/fsxn-lakehouse-part3-snowflake) | [dev.to](https://dev.to/aws-builders/snowflake-and-fsx-for-ontap-s3-access-points-from-access-denied-to-working-external-tables-9k8) |
| 4 | DuckDB Lambda — $0.00001/クエリのサーバーレス分析 | [はてなブログ](https://hakobiya.hatenablog.com/entry/fsxn-lakehouse-part4-duckdb) | [dev.to](https://dev.to/aws-builders/serverless-analytics-on-nas-data-for-000001query-duckdb-lambda-x-fsx-for-ontap-2o5o) |
| 5 | EMR Spark — NAS データでの読み書き ETL | [はてなブログ](https://hakobiya.hatenablog.com/entry/fsxn-lakehouse-part5-emr-spark) | [dev.to](https://dev.to/aws-builders/read-write-etl-on-nas-data-with-emr-serverless-spark-no-cluster-no-copy-hgm) |
| 6 | Redshift Spectrum + Lake Formation — エンタープライズガバナンス | [はてなブログ](https://hakobiya.hatenablog.com/entry/fsxn-lakehouse-part6-redshift-lakeformation) | [dev.to](https://dev.to/aws-builders/redshift-spectrum-lake-formation-enterprise-governance-on-nas-data-2pik) |
| 7 | テーブルフォーマット制約 — Delta/Iceberg/Hudi が書き込めない理由 | [はてなブログ](https://hakobiya.hatenablog.com/entry/fsxn-lakehouse-part7-table-format) | [dev.to](https://dev.to/aws-builders/why-delta-iceberg-and-hudi-cant-write-to-fsx-s3-access-points-and-what-works-instead-5be3) |
| 8 | OpenSharing × FSx for ONTAP — ゼロコピー共有の新パス | [はてなブログ](https://hakobiya.hatenablog.com/entry/fsxn-lakehouse-part8-opensharing) | — |

### シリーズ 2: 「非構造化データ向け Iceberg メタデータカタログ」（進行中）

FSx for ONTAP 上の非構造化ファイルを S3 にコピーせず即座に検索可能にする AI メタデータカタログ:

| パート | トピック | ステータス |
|:---:|-------|--------|
| 1 | アーキテクチャ & PoC 結果 — 数時間から数秒へ | 📝 ドラフト |
| 2 | AI エンリッチメントパイプライン — Bedrock Vision + Embeddings | 📝 ドラフト |
| 3 | ガバナンス & クロスプラットフォームアクセス — Lake Formation + OpenSearch | 📝 ドラフト |

**主要結果**: 40 ファイルを 30 秒でカタログ化、AI 分類 $0.01/ファイル、Athena クエリ < 2 秒、スケールトゥゼロベクトル検索（アイドル $0）、フルデモ 47 秒 $0.07。

参照: [アーキテクチャ](docs/ja/iceberg-metadata-catalog.md) | [PoC 結果](integrations/iceberg-metadata-catalog/docs/poc-results-summary.md) | [デモガイド](integrations/iceberg-metadata-catalog/demo/docs/demo-guide.md)

</details>

---

## 関連プロジェクト

| プロジェクト | 役割 | 関係性 |
|------------|------|--------|
| [ontap-edge-to-cloud-ai](https://github.com/Yoshiki0705/ontap-edge-to-cloud-ai) | エッジデバイス (Raspberry Pi) → ONTAP → Kafka 取り込み | 本リポジトリの [製造データプラットフォーム](integrations/manufacturing-data-platform/) が消費するイベントとペイロードを生成。スキーマ、ClickHouse DDL、Databricks パイプラインは同期維持 — [Edge ↔ Lakehouse 同期](integrations/manufacturing-data-platform/docs/ja/14_edge_lakehouse_sync.md) 参照。|
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | FSx for ONTAP S3 Access Points 向け 17 サーバーレスパターン | 上記 S3 AP 統合のコンパニオンパターンライブラリ。|

本リポジトリはエッジ→クラウドアーキテクチャの **Kafka + ClickHouse + Databricks** 側を担当し、エッジデバイス側は `ontap-edge-to-cloud-ai` に存在します。

---

## ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照。

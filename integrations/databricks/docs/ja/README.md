# Databricks 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: 実験的**
> - Unity Catalog External Location と FSx for ONTAP S3 Access Point の組み合わせは、テスト環境においてセッションポリシー境界により成功しませんでした。
> - Instance Profile + boto3 は、制御されたドライバーノード PoC としてのみ成功しました。
> - 本リポジトリは Databricks + FSx S3 Access Points の本番サポートを主張するものではありません。

## 概要

Amazon FSx for NetApp ONTAP（FSx for ONTAP）と Databricks を S3 Access Points 経由で統合する実験的検証パッケージです。

Unity Catalog External Location は現在セッションポリシーの制約により動作しないため、本番環境での Delta Lake テーブルには [Databricks がサポートするクラウドストレージパターン](https://docs.databricks.com/aws/en/connect/storage/amazon-s3) を使用してください。

## 検証結果 (2026-05-17)

| アプローチ | 結果 | 備考 |
|----------|------|------|
| S3 AP + Unity Catalog | ❌ | セッションポリシーが S3 AP ARN をサポートしない |
| S3 AP + boto3 (Managed VPC) | ❌ | IMDS ブロック |
| NFS マウント (Managed VPC) | ❌ | Egress 制限 + seccomp |
| NFS マウント (Customer VPC) | ❌ | seccomp フィルターが NFS マウントをブロック |
| NFS RPC 直接 (Customer VPC) | ✅ | Python RPC で全操作成功 |
| ONTAP REST API (Customer VPC) | ✅ | 認証・設定変更可能 |
| Instance Profile + boto3 (Customer VPC, Dedicated) | ✅ | S3 AP 読み取り成功。UC ガバナンスをバイパス — PoC のみ |

## 主要概念: Databricks ストレージ & 取り込みアーキテクチャ

Databricks のストレージと取り込みの概念を理解することが、FSx for ONTAP S3 AP 統合の評価に不可欠です。

### Storage Credential → External Location → External Table/Volume

```
Storage Credential（IAM ロール ARN + External ID）
    │
    └── External Location（クラウドストレージパス + クレデンシャル）
            │
            ├── External Table（表形式データ: Parquet, Delta, Iceberg）
            └── External Volume（非表形式: 画像、ドキュメント、音声）
```

| 概念 | 説明 | FSx S3 AP ステータス | リファレンス |
|---|---|:---:|---|
| **[Storage Credential](https://docs.databricks.com/aws/en/connect/unity-catalog/storage-credentials)** | Databricks がクラウドストレージにアクセスするために引き受ける IAM ロール | ✅ 作成済み | [ドキュメント](https://docs.databricks.com/aws/en/connect/unity-catalog/storage-credentials) |
| **[External Location](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/s3/s3-external-location-manual)** | S3 パスを Storage Credential にマッピング。アクセス境界を定義 | ✅ 作成済み（`access_point` フィールド付き） | [ドキュメント](https://docs.databricks.com/aws/en/connect/unity-catalog/cloud-storage/s3/s3-external-location-manual) |
| **[External Table](https://docs.databricks.com/aws/en/tables/external)** | External Location にデータが存在する UC ガバナンス付きテーブル | ❌ CREATE TABLE ブロック | [ドキュメント](https://docs.databricks.com/aws/en/tables/external) |
| **[External Volume](https://docs.databricks.com/aws/en/volumes/managed-vs-external)** | External Location の非構造化ファイルに対する UC ガバナンス付きボリューム | ❌ ブロック（同じセッションポリシー問題） | [ドキュメント](https://docs.databricks.com/aws/en/volumes/managed-vs-external) |
| **[Managed Table](https://docs.databricks.com/aws/en/data-governance/unity-catalog/managed-versus-external)** | UC マネージドテーブル（データライフサイクルを Databricks が制御） | ✅ 動作（標準 S3 上） | [ドキュメント](https://docs.databricks.com/aws/en/data-governance/unity-catalog/managed-versus-external) |
| **[Managed Volume](https://docs.databricks.com/aws/en/volumes/managed-vs-external)** | 非構造化ファイル用 UC マネージドボリューム（Databricks マネージドストレージ） | ✅ 動作（標準 S3 上） | [ドキュメント](https://docs.databricks.com/aws/en/volumes/managed-vs-external) |

### Auto Loader（増分取り込み）

[Auto Loader](https://docs.databricks.com/ingestion/auto-loader/index.html) は Snowflake の Snowpipe に相当する機能 — クラウドストレージに到着した新しいファイルを増分的に処理します。

| モード | 説明 | S3 Event Notifications 必要 | FSx S3 AP ステータス |
|---|---|:---:|:---:|
| **[Directory Listing](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/directory-listing-mode)** | 定期的にディレクトリを一覧して新規ファイルを検出 | ❌ 不要 | ⚠️ External Location が必要（ブロック） |
| **[File Notification](https://docs.databricks.com/aws/en/ingestion/cloud-object-storage/auto-loader/file-notification-mode)** | S3 Event Notifications + SQS でリアルタイム検出 | ✅ 必要 | ❌ 不可（FSx S3 AP は S3 Events 非サポート） |

**Snowflake との比較:**

| 機能 | Snowflake (Snowpipe) | Databricks (Auto Loader) | FSx S3 AP サポート |
|---|---|---|:---:|
| イベント駆動取り込み | Snowpipe (S3 Events → SNS → Snowflake) | File Notification モード (S3 Events → SQS) | ❌ 両方ブロック（FSx S3 AP に S3 Events なし） |
| ポーリングベース取り込み | スケジュール `ALTER STAGE REFRESH` (Task) | Directory Listing モード | ⚠️ Snowflake: 動作; Databricks: UC でブロック |
| FSx 向け代替手段 | FPolicy → Lambda → SNS → Snowpipe | FPolicy → Lambda → S3 に書き込み → Auto Loader | ✅ 回避策あり |
| 増分処理 | Snowpipe がロード済みファイルを追跡 | Auto Loader がチェックポイントで処理済みファイルを追跡 | — |

### Volumes: 非構造化データガバナンス

[Unity Catalog Volumes](https://docs.databricks.com/aws/en/volumes/managed-vs-external) は Snowflake の Directory Table に相当 — 非表形式ファイル（画像、ドキュメント、音声、動画）へのガバナンス付きアクセスを提供します。

| 概念 | Snowflake 相当 | 説明 | FSx S3 AP ステータス |
|---|---|---|:---:|
| **External Volume** | 外部ステージの Directory Table | 外部ストレージ上のガバナンス付きファイルアクセス | ❌ ブロック（External Location が必要） |
| **Managed Volume** | 内部ステージ + Directory Table | Databricks マネージドストレージ上のガバナンス付きファイルアクセス | ✅ 動作（標準 S3） |
| **Volume パス** (`/Volumes/catalog/schema/volume/`) | `@stage/path/` | SQL/Python でのファイルアクセス統一パス | ❌ FSx S3 AP では利用不可 |

**重要な違い**: Snowflake の Directory Table は FSx S3 AP 外部ステージで今日動作します。Databricks の External Volumes は External Location の作成が必要で、セッションポリシーによりブロックされています。

### 概念マッピング: Snowflake ↔ Databricks

| Snowflake 概念 | Databricks 相当 | 目的 | FSx S3 AP (Snowflake) | FSx S3 AP (Databricks) |
|---|---|---|:---:|:---:|
| Storage Integration | Storage Credential | IAM ロール参照 | ✅ | ✅ |
| External Stage | External Location | クラウドストレージパスマッピング | ✅ | ✅（部分的） |
| External Table | External Table | 外部データへのガバナンス付き読み取り | ✅ | ❌ ブロック |
| Directory Table | External Volume | 非構造化データのファイルカタログ | ✅ | ❌ ブロック |
| Snowpipe | Auto Loader | 増分ファイル取り込み | ⚠️（S3 Events なし） | ❌ ブロック |
| COPY INTO | COPY INTO / Auto Loader | バッチデータロード | ✅ | ❌ ブロック |
| Internal Stage | Managed Volume | Snowflake/Databricks マネージドストレージ | ✅ | ✅ |
| `AWS_ACCESS_POINT_ARN` | `access_point` フィールド | セッションポリシー用 S3 AP ARN | ✅（全て解決） | ⚠️（部分的解決） |

## マネージドテーブル vs 外部テーブル — 設計ガイド

Unity Catalog におけるマネージドテーブルと外部テーブルの違いを理解することがアーキテクチャ判断に不可欠です — 特に現在の FSx S3 AP セッションポリシーの制限を考慮して。

> **主要概念**: [外部テーブル](https://docs.databricks.com/aws/en/tables/external)（UC がメタデータのみ管理）| [マネージドテーブル](https://docs.databricks.com/aws/en/data-governance/unity-catalog/managed-versus-external)（UC が両方管理）| [External Location](https://docs.databricks.com/aws/en/connect/unity-catalog/storage-credentials)（クラウドパスをクレデンシャルにマッピング）
>
> AI/ML 固有の影響については [AI/ML デモガイド](ai-demo-guide.md) を参照。

### 比較マトリクス

| 観点 | UC 外部テーブル（FSx S3 AP 上） | UC マネージドテーブル（S3 バケット上） | boto3 PoC（UC テーブルなし） |
|---|---|---|---|
| **データ所在** | FSx for ONTAP（ゼロコピー） | Databricks マネージド S3 | FSx for ONTAP |
| **UC ガバナンス** | ❌ **ブロック**（CREATE TABLE 失敗） | ✅ 完全（タグ、マスク、リネージ） | ❌ なし |
| **ONTAP 機能の保持** | ✅ Snapshot, FlexClone, FPolicy | ❌ データは ONTAP 外 | ✅（読み取り専用） |
| **マルチプロトコルアクセス** | ✅ NFS/SMB/S3 AP | ❌ S3 のみ | ✅ NFS/SMB/S3 AP |
| **クエリ性能** | N/A（テーブル作成ブロック） | ✅ 最適化 Delta/Iceberg | ❌ Spark 最適化なし |
| **Delta Lake 機能** | ❌ ブロック | ✅ ACID, Time Travel, MERGE | ❌ 適用外 |
| **ML Feature Store** | ❌ ブロック | ✅ 完全サポート | ❌ 適用外 |
| **データ鮮度** | リアルタイム（サポートされれば） | 取り込みパイプラインに依存 | リアルタイム（boto3 が現在の状態を読み取り） |
| **ストレージコスト** | FSx のみ | FSx + S3（重複） | FSx のみ |
| **本番適合性** | ❌ 現時点で不可 | ✅ 推奨 | ⚠️ PoC のみ |

### 現在の状態: 動作するものと動作しないもの

```
FSx for ONTAP S3 AP
     │
     ├── UC External Location（access_point フィールド設定済み）
     │     ├── トップレベル ls: ✅（287 アイテム）
     │     ├── 明示的ファイル読み取り（spark.read.csv）: ✅（1000 行）
     │     ├── サブディレクトリ一覧: ❌（AccessDenied）
     │     ├── CREATE TABLE: ❌（UC_CLOUD_STORAGE_ACCESS_FAILURE）
     │     └── 書き込み操作: ❌（PutObject AccessDenied）
     │
     └── Instance Profile + boto3（Customer VPC, Dedicated クラスター）
           ├── GetObject: ✅
           ├── ListObjectsV2: ✅
           └── UC ガバナンス: ❌（完全にバイパス）
```

### 推奨アーキテクチャパターン（現時点）

FSx S3 AP 上の UC 外部テーブルがブロックされているため、推奨パターンは**ステージング取り込み**アプローチ:

```
FSx for ONTAP ──S3 AP──▶ 取り込みジョブ ──▶ S3 バケット ──▶ UC マネージドテーブル ──▶ ML/AI
     │                    (Glue/EMR/Lambda)                    │
     │                                                         └── 完全 UC ガバナンス
     └── 同一データに NFS/SMB でアクセス（ソースオブトゥルース）
```

**または読み取り専用分析の場合:**
```
FSx for ONTAP ──S3 AP──▶ Athena（SQL 分析、コピー不要）
                    └──▶ Snowflake External Table（ガバナンス付き、コピー不要）
```

### パターン別の選択ガイド

| 要件 | 推奨パターン | 理由 |
|---|---|---|
| ガバナンス付き ML 学習データ | S3 バケット → UC マネージドテーブル | 完全 UC ガバナンス、Feature Store、リネージ |
| NAS 上の読み取り専用 SQL 分析 | Athena + FSx S3 AP | コピー不要、サーバーレス、ガバナンス付き |
| NAS 上のガバナンス付き外部テーブル | Snowflake External Table | 現時点で完全ガバナンス付きで動作 |
| 探索的データアクセス（PoC） | Instance Profile + boto3 | 迅速なアクセス、ガバナンスなし |
| 本番 Delta Lake テーブル | S3 バケット（標準パターン） | ACID, MERGE, OPTIMIZE に必要 |
| リアルタイム NAS データ + UC ガバナンス | プラットフォームサポート待ち | UC セッションポリシー解消が必要 |

### コスト & ガバナンスのトレードオフ

| パターン | ストレージコスト | ガバナンス | 性能 | ONTAP 機能 |
|---|---|---|---|---|
| **Athena + FSx S3 AP** | 最低（FSx のみ） | AWS 側（IAM, S3 AP） | 良好（サーバーレス） | ✅ 保持 |
| **Snowflake External Table** | 低（FSx のみ） | ✅ 完全（タグ、マスキング） | 中程度 | ✅ 保持 |
| **S3 にステージング → UC テーブル** | 高（FSx + S3） | ✅ 完全 UC | 最高（Delta 最適化） | ❌ コピーで失われる |
| **boto3 PoC** | 最低（FSx のみ） | ❌ なし | 低（ドライバーのみ） | ✅ 保持 |

### AI レディネススコア

| パターン | ガバナンス | 性能 | AI 機能 | コスト | 運用容易性 | 総合 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Athena + FSx S3 AP** | ★★★☆☆ | ★★★★☆ | ★☆☆☆☆ (SQL のみ) | ★★★★★ | ★★★★★ | **3.6** |
| **Snowflake External Table** | ★★★★☆ | ★★★☆☆ | ★★★★☆ (Cortex AI) | ★★★★★ | ★★★★☆ | **4.0** |
| **S3 にステージング → UC テーブル** | ★★★★★ | ★★★★★ | ★★★★★ (全 Mosaic AI) | ★★☆☆☆ | ★★☆☆☆ | **3.8** |
| **boto3 PoC (Databricks)** | ★☆☆☆☆ | ★★☆☆☆ | ★★★☆☆ (ドライバーのみ) | ★★★★★ | ★★★☆☆ | **2.8** |
| **Bedrock KB + FSx S3 AP** | ★★★☆☆ | ★★★★☆ | ★★★★☆ (RAG) | ★★★★☆ | ★★★★☆ | **3.8** |

- **ガバナンス**: UC リネージ、タグ、マスキング、Row Filter
- **性能**: クエリレイテンシ、分散処理
- **AI 機能**: 利用可能な AI/ML 関数の幅
- **コスト**: ストレージ効率、コンピュートコスト
- **運用容易性**: セットアップ、メンテナンス、パイプラインの複雑さ

### リファレンス

- [Unity Catalog External Tables](https://docs.databricks.com/aws/en/tables/external)
- [Managed vs External Assets](https://docs.databricks.com/aws/en/data-governance/unity-catalog/managed-versus-external)
- [External Locations](https://docs.databricks.com/aws/en/connect/unity-catalog/storage-credentials)
- [Delta Lake on Databricks](https://docs.databricks.com/aws/en/delta/index)

## 非構造化データ対応

| フォーマット | 対応 | アクセス方法 | ユースケース |
|------------|:---:|------------|------------|
| 画像 (JPEG, PNG, TIFF) | ⚠️ | Instance Profile + boto3（ドライバーのみ） | 画像分類、品質検査 |
| 動画 (MP4, MOV) | ⚠️ | Instance Profile + boto3（ドライバーのみ） | フレーム抽出、動画分析 |
| ドキュメント (PDF, DOCX) | ⚠️ | Instance Profile + boto3（ドライバーのみ） | テキスト抽出、RAG パイプライン |
| 音声 (WAV, MP3) | ⚠️ | Instance Profile + boto3（ドライバーのみ） | 文字起こし、音声分析 |
| バイナリ / アーカイブ | ⚠️ | Instance Profile + boto3（ドライバーのみ） | ダウンロード、カスタム処理 |

**現在の制約:**
- Unity Catalog External Table 作成がブロック → ガバナンス付き非構造化データカタログ不可
- `spark.read.binaryFile` は明示的ファイルパスで動作（`access_point` フィールド設定時）
- Instance Profile + boto3 は UC ガバナンスをバイパス（PoC のみ、本番非推奨）
- Snowflake の Directory Table や GET_PRESIGNED_URL に相当する機能なし
- Executor スケール処理は未検証

**FSx for ONTAP 上の非構造化データの推奨代替手段:**
- **Snowflake**（Directory Table + GET_PRESIGNED_URL）でファイルカタログとセキュア URL 生成
- **AWS Lambda** でサーバーレスファイル処理（[AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-process-files-with-lambda.html)）
- **Amazon Bedrock** でドキュメント RAG（[AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)）

## ONTAP の価値

| ONTAP 機能 | Databricks へのメリット | リファレンス |
|---|---|---|
| **FlexCache** | リージョン/拠点間で学習データをキャッシュし低遅延アクセスを実現。Write-back モードで特徴量エンジニアリングを高速化 | [FlexCache ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html) |
| **SnapLock / Tamperproof Snapshot** | 不変の学習データ保護 — 管理者権限でも保持期間中は削除不可。規制 ML のコンプライアンス | [SnapLock on FSx](https://netapp.com/blog/snaplock-on-amazon-fsx-ontap/) |
| **ARP/AI** | AI によるランサムウェア検知。学習データとモデルアーティファクトを自動スナップショットで保護 | [ARP on FSx](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/ARP.html) |
| **FlexClone** | フルコピーなしの即時 dev/test データセットプロビジョニング。ゼロコピー ML 実験 | [FlexClone ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| **Snapshot** | テーブルレベルのポイントインタイムリカバリ（Delta Time Travel を補完）。特徴量パイプラインのバージョン管理 | [Snapshot ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapshots-ontap.html) |
| **FabricPool** | コールドパーティションの S3 自動階層化（Databricks コンピュートに透過的） | [FabricPool ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/fabricpool.html) |
| **ストレージ効率化** | 重複排除 + 圧縮 + コンパクションで Delta バージョンファイルを最大 65% 削減 | [ストレージ効率](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/storage-efficiency.html) |
| **SnapMirror** | レイクハウスデータと ML パイプラインのクロスリージョン DR | [SnapMirror ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html) |
| **マルチプロトコル** | NFS（データサイエンティスト）+ SMB（Windows ユーザー）+ S3 AP（Databricks/Spark）— 同一データ、コピー不要 | [マルチプロトコル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html) |
| **FPolicy** | ファイル操作の監視とブロック。データアクセスコンプライアンスの監査証跡 | [FPolicy ドキュメント](https://docs.netapp.com/us-en/ontap/nas-audit/fpolicy-config-types-concept.html) |

## ガバナンス & AI/ML ガイド

| ガイド | 説明 |
|---|---|
| [AI/ML デモガイド](ai-demo-guide.md) | 現在のステータス、動作するデモ、ブロックされたパス、将来の機能 |
| [ガバナンス: タグとデータ保護 (ABAC)](ai-demo-guide.md#ガバナンスタグとデータ保護-abac) | UC ABAC、Governed Tags、カラムマスク、Row Filter — 現在の制限 |
| [ガバナンス: ファイルレベルアクセス制御](ai-demo-guide.md#ファイルレベルのアクセス制御-ontap-ネイティブレイヤー) | ONTAP デュアルレイヤー認可、FPolicy、チームごとの S3 AP 分離（補償コントロール） |
| [統合: ONTAP × Databricks タグ](ai-demo-guide.md#統合-ontap-ファイルレベル制御--databricks-タグガバナンス) | 組み合わせガバナンスマトリクス、現在 vs 将来、設計パターン |

## クイックスタート

```bash
# 1. CloudFormation テンプレートをデプロイ
cp params.example.json params.json  # パラメータを編集
./deploy.sh

# 2. Databricks Storage Credential を設定（Terraform または UI）
cd terraform/
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply

# 3. External Location を作成して S3 AP を指定
# 4. ノートブックを順番に実行 (01 → 06)
```

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

## マネージドテーブル vs 外部テーブル — 設計ガイド

Unity Catalog におけるマネージドテーブルと外部テーブルの違いを理解することがアーキテクチャ判断に不可欠です — 特に現在の FSx S3 AP セッションポリシーの制限を考慮して。

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

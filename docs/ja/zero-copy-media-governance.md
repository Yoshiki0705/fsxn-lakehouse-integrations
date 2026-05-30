# ゼロコピー非構造化データガバナンス: FSx for ONTAP による S3 重複排除とマルチプラットフォーム活用

🌐 日本語 | [English](../en/zero-copy-media-governance.md)

## 顧客課題

| # | 課題 | 根本原因 |
|---|------|---------|
| 1 | S3 保管コストが増え続けている。重複データを可能な限り持ちたくない | 汎用ファイルサーバー → DataSync（ファイル差分）→ S3 フルコピーで冗長ストレージが発生 |
| 2 | 非構造化データ（画像、動画、PDF、CAD、ログ、音声等）をタグで権限制御しながら組織を跨いで活用したい | S3 にフラットにコピーされているだけでガバナンスなし |

### 対象データ

| カテゴリ | 例 | 典型的なサイズ | AI/分析での活用 |
|---------|---|--------------|----------------|
| 画像 | 製品写真、医療画像(DICOM)、衛星画像、設計図面 | 1-100MB/file | Vision AI、品質検査、物体検出 |
| 動画 | 監視カメラ、製造ライン、トレーニング教材 | 100MB-10GB/file | 異常検知、行動分析 |
| ドキュメント | PDF、Word、設計仕様書、契約書、マニュアル | 1-50MB/file | RAG、要約、検索、コンプライアンス |
| CAD/3D | AutoCAD、SolidWorks、点群データ | 10MB-1GB/file | デジタルツイン、シミュレーション |
| ログ/センサー | IoT センサーデータ、アプリケーションログ | 可変 | 予知保全、異常検知 |
| 音声 | コールセンター録音、会議録音 | 10-100MB/file | 文字起こし、感情分析 |

### 既存環境の前提

顧客は以下のいずれかのデータ活用基盤を既に運用しており、蓄積された資産・知見・チームスキルを活かして拡張したい:

| 既存環境 | 背景 | 本ドキュメントでの対応セクション |
|---------|------|-------------------------------|
| **Databricks** | UC、Delta Lake、MLflow 等のパイプライン資産がある | [Databricks パス](#databricks-パス) |
| **Snowflake** | Cortex AI、Data Sharing、Horizon Catalog の知見がある | [Snowflake パス](#snowflake-パス) |
| **AWS ネイティブ** | Athena、Glue、Bedrock、Lake Formation を中心に構築済み | [AWS ネイティブパス](#aws-ネイティブパス) |

### 現状アーキテクチャ（問題状態）

```
オンプレ汎用ファイルサーバー（NAS/Windows）
  ↓ DataSync（ファイル差分 — 1バイト変更でもファイル全体を再転送）
Amazon S3（フルコピー、重複排除なし）
  ↓
データ活用基盤（Databricks / Snowflake / AWS ネイティブ）

問題点:
- ファイルサーバーにも S3 にもインライン重複排除機能がない
- DataSync ファイル差分: 1バイト変更 → ファイル全体を再転送
- S3 コストがデータ量に比例して増大
- 非構造化データ資産にガバナンスなし
```

---

## ストレージ最適化（全プラットフォーム共通）

### Option A: S3 最適化のみ（最小変更）

```
汎用ファイルサーバー（変更なし）
  ↓ DataSync（ファイル差分）
S3 bucket
  ├── S3 Intelligent-Tiering（自動階層化）
  │   └── Archive Instant Access: 90日未アクセスで $0.004/GB
  ├── S3 Lifecycle Policy（古いバージョン削除）
  └── データ活用基盤から直接参照
```

**コスト削減**: 20-40%（階層化のみ、重複排除なし）
**限界**: 重複データは排除できない。帯域非効率も残存。

---

### Option B: FSx for ONTAP 移行（推奨）

```
汎用ファイルサーバー
  ↓ DataSync（一回限りのマイグレーション）
FSx for ONTAP（唯一のクラウドコピー）
  │ ← インライン重複排除 + 圧縮（自動）
  │ ← Snapshot（ポイントインタイムリカバリ）
  │ ← FabricPool（コールドデータを S3 IA に自動階層化 $0.0125/GB）
  │
  ↓ S3 Access Point（用途別に複数 AP）
  ├── AP-1: データ活用基盤（Databricks / Snowflake / Athena）
  ├── AP-2: AI サービス（Bedrock KB / Cortex Search）
  └── AP-3: アプリケーション直接アクセス

S3 フルコピー = 廃止
```

**コスト削減**: 50-70%（dedup + FabricPool + S3 コピー廃止）

---

### Option C: オンプレ ONTAP + SnapMirror（ハイブリッド）

```
オンプレ ONTAP（汎用FS から置き換え）
  │ ← インライン重複排除 + 圧縮
  ↓ SnapMirror（ブロックレベル差分 = DataSync の 2,500 倍効率的）
FSx for ONTAP（クラウドレプリカ）
  ↓ S3 Access Point → データ活用基盤
```

**DataSync vs SnapMirror**:

| 観点 | DataSync（ファイル差分） | SnapMirror（ブロック差分） |
|------|----------------------|------------------------|
| 10GB ファイルの1バイト変更 | **10GB 再転送** | **4KB 転送** |
| 帯域効率 | 低 | **2,500倍** |
| ネットワーク圧縮 | なし | 組み込み |

---

### Option D: FlexCache S3 Access Points（将来ロードマップ）

> **ステータス**: FlexCache ボリュームへの S3 Access Points サポートは、FSx for ONTAP ではまもなく利用可能になる見込みです（FSx での提供時期未定）。
>
> **根拠**: NetApp ONTAP 9.18.1 で FlexCache ボリュームへの S3 プロトコルアクセスが正式サポートされました（`-is-s3-enabled` オプション）。オンプレミス ONTAP では既にこの機能が利用可能であり、FSx for ONTAP への展開は技術的に確立された基盤の上に構築されます。
>
> **参照**:
> - [ONTAP 9.18.1 What's New](https://docs.netapp.com/us-en/ontap/release-notes/whats-new-9181.html)
> - [Create an ONTAP S3 NAS bucket on FlexCache volumes](https://docs.netapp.com/us-en/ontap/s3-multiprotocol/create-nas-bucket-task.html) — "All nodes in the cluster must be running ONTAP 9.18.1 or later"

```
FSx for ONTAP（オリジン）
  ↓ FlexCache Volume（ホットデータのみキャッシュ、オリジンの 10-30%）
  ↓ S3 Access Point（FlexCache 上）
  ├── データ活用基盤（低レイテンシーアクセス）
  └── AI サービス

利点:
- フルレプリケーション不要 → ストレージコスト 60-80% 削減
- アクセス時にキャッシュウォーム → 初期同期不要
- キャッシュミスのみ WAN 通過 → 帯域最小化
```

**コスト比較（10TB 非構造化データ）**:

| 項目 | 現状（S3 コピー） | Option B | Option D（将来） |
|------|-----------------|----------|-----------------|
| ストレージ月額 | $230 | $450（dedup後） | $180（キャッシュのみ） |
| オンプレ運用費 | あり | なし | なし |
| **現行比削減率** | — | 50%（TCO） | **80%** |

---

## 段階的導入ロードマップ

| Phase | 期間 | 施策 | 効果 |
|-------|------|------|------|
| **Phase 1** | 即時（1-2週間） | S3 Intelligent-Tiering + Lifecycle Policy 適用 | コスト 20-40% 削減 |
| **Phase 2** | 1-3ヶ月 | FSx for ONTAP 導入 + S3 コピー廃止 | コスト 50%+ 削減、dedup 有効化 |
| **Phase 3** | FlexCache S3 AP GA 後 | FlexCache S3 AP に移行 | コスト 80% 削減、最小データ移動 |

---

## Databricks パス

**前提**: 既存の Databricks 環境で培った UC、Delta Lake、MLflow 等のパイプライン資産・チームスキルを活かして拡張する。

### ガバナンス実装

```sql
-- UC Volume に非構造化データを格納
CREATE EXTERNAL VOLUME unstructured_assets
  LOCATION 's3://company-assets-bucket/volumes/';

-- メタデータカタログ（タグベースガバナンス）
CREATE TABLE asset_catalog (
  asset_id STRING GENERATED ALWAYS AS IDENTITY,
  volume_path STRING,
  asset_type STRING,        -- 'image', 'video', 'document', 'cad', 'audio', 'log'
  department STRING,
  classification STRING,    -- 'public', 'internal', 'confidential', 'restricted'
  tags MAP<STRING, STRING>,
  file_size_bytes BIGINT,
  checksum STRING,
  source_path STRING,
  synced_at TIMESTAMP
);

-- タグベース Row Filter（部門 + 分類レベル）
CREATE FUNCTION asset_access_filter(department STRING, classification STRING)
RETURN
  IS_ACCOUNT_GROUP_MEMBER('asset_admin')
  OR (department = current_user_attribute('department')
      AND classification IN ('public', 'internal'))
  OR (IS_ACCOUNT_GROUP_MEMBER(concat(department, '_confidential'))
      AND classification = 'confidential');

ALTER TABLE asset_catalog SET ROW FILTER asset_access_filter
  ON (department, classification);

-- Delta Sharing（組織横断共有）
CREATE SHARE partner_asset_share;
ALTER SHARE partner_asset_share ADD TABLE asset_catalog;
```

### AI 活用パス

| ユースケース | Databricks 機能 | データパス |
|------------|----------------|-----------|
| 画像分類・タグ自動付与 | Mosaic AI (Vision) | UC Volume → Model Serving |
| ドキュメント RAG | Vector Search | UC Volume → Embedding → Vector Index |
| 音声文字起こし | Model Serving (Whisper) | UC Volume → Batch Inference |
| 異常検知（センサー） | MLflow + Feature Store | Auto Loader → Delta Table → ML Pipeline |

### 制約事項

- UC Volume は S3 バックエンドが必須（FSx S3 AP を直接 Volume 登録不可）
- UC Row Filter / Column Mask は外部エンジン（Athena/EMR）に強制されない
- 外部エンジンからのアクセスには Lake Formation の併用が必要

---

## Snowflake パス

**前提**: 既存の Snowflake 環境で培った Cortex AI、Data Sharing、Horizon Catalog の知見・ガバナンス設計を活かして拡張する。

### ガバナンス実装

```sql
-- External Stage（FSx S3 AP 直接アクセス）
CREATE OR REPLACE STAGE unstructured_stage
  URL = 's3://fsxn-ap-alias/assets/'
  STORAGE_INTEGRATION = fsxn_integration;

-- External Table（メタデータ + ガバナンス）
CREATE OR REPLACE EXTERNAL TABLE asset_catalog (
  file_path VARCHAR AS (metadata$filename),
  asset_type VARCHAR AS (
    CASE WHEN metadata$filename LIKE '%.jpg' THEN 'image'
         WHEN metadata$filename LIKE '%.pdf' THEN 'document'
         WHEN metadata$filename LIKE '%.mp4' THEN 'video'
         ELSE 'other' END),
  file_size NUMBER AS (metadata$file_row_number),
  last_modified TIMESTAMP AS (metadata$file_last_modified)
)
LOCATION = @unstructured_stage
FILE_FORMAT = (TYPE = 'CSV');

-- Row Access Policy（部門ベース）
CREATE OR REPLACE ROW ACCESS POLICY asset_rap AS (department VARCHAR)
RETURNS BOOLEAN ->
  CURRENT_ROLE() IN ('ADMIN') OR department = CURRENT_ROLE();

ALTER TABLE asset_catalog ADD ROW ACCESS POLICY asset_rap ON (department);

-- Dynamic Data Masking（機密パス非表示）
CREATE OR REPLACE MASKING POLICY path_mask AS (val VARCHAR)
RETURNS VARCHAR ->
  CASE WHEN CURRENT_ROLE() IN ('ADMIN', 'DATA_ENGINEER') THEN val
       ELSE '***MASKED***' END;

-- Secure Data Sharing（組織横断）
CREATE SHARE partner_share;
GRANT USAGE ON DATABASE assets_db TO SHARE partner_share;
GRANT SELECT ON TABLE asset_catalog TO SHARE partner_share;
```

### AI 活用パス

| ユースケース | Snowflake 機能 | データパス |
|------------|---------------|-----------|
| ドキュメント RAG | Cortex Search | COPY INTO → Internal Table → Cortex Search Service |
| 画像/動画分析 | Cortex AI (Vision) | COPY FILES → Internal Stage → TO_FILE → AI_COMPLETE |
| テキスト要約 | Cortex AI (COMPLETE) | PARSE_DOCUMENT → COMPLETE |
| 組織横断共有 | Secure Data Sharing + Horizon | External Table → Share → 受信者 |

### Snowflake 固有の強み

- **Horizon Iceberg REST Catalog**: 外部エンジン（Spark, Trino）にも Row Access Policy + Masking を強制（Databricks UC にはない機能）
- **全エディション対応**: Standard でも Horizon Catalog 利用可能
- **COPY INTO 不要のガバナンス**: External Table に直接 Row Access Policy / Masking 適用可能
- **Data Sharing**: 受信者側にデータコピーなしで共有（ゼロコピー共有）

### 制約事項

- TO_FILE は FSx S3 AP ステージで SQL コンパイル時エラー（エンジニアリング調査中）
- Vision AI（TO_FILE 経由）のみ内部ステージへの COPY FILES が必要。Cortex AI 関数（COMPLETE, SUMMARIZE）と Cortex Search は Managed Iceberg Table で直接動作（内部テーブル不要）
- AUTO_REFRESH 非対応（Task + ALTER STAGE REFRESH で代替）

---

## AWS ネイティブパス

**前提**: 既存の AWS ネイティブ環境（Athena、Glue、Bedrock、Lake Formation）で培った知見・パイプラインを活かして拡張する。

### ガバナンス実装

```yaml
# Lake Formation によるタグベースアクセス制御
# 1. LF-Tags 定義
LF-Tags:
  classification: [public, internal, confidential, restricted]
  department: [engineering, marketing, legal, research]
  asset_type: [image, video, document, cad, audio, log]

# 2. Glue Catalog テーブル（FSx S3 AP 上のデータを直接参照）
GlueCatalog:
  Database: unstructured_assets
  Table: asset_catalog
    Location: "s3://fsxn-ap-alias/assets/"
    InputFormat: org.apache.hadoop.mapred.TextInputFormat
    SerDe: org.openx.data.jsonserde.JsonSerDe

# 3. LF-Tag ベースの権限付与
Grants:
  - Principal: "arn:aws:iam::ACCOUNT:role/engineering-analyst"
    LFTagPolicy:
      Expression:
        - TagKey: department
          TagValues: [engineering]
        - TagKey: classification
          TagValues: [public, internal]
    Permissions: [SELECT, DESCRIBE]
```

```sql
-- Athena からの直接クエリ（Lake Formation ガバナンス適用済み）
SELECT "$path" as file_path,
       "$size" as file_size,
       classification,
       department
FROM unstructured_assets.asset_catalog
WHERE asset_type = 'document'
  AND department = 'engineering';
```

### AI 活用パス

| ユースケース | AWS サービス | データパス |
|------------|-------------|-----------|
| ドキュメント RAG | Bedrock Knowledge Base | FSx S3 AP → Bedrock KB → OpenSearch (embeddings) |
| 画像分析 | Bedrock (Claude Vision) | FSx S3 AP → Lambda → Bedrock InvokeModel |
| テキスト抽出 | Textract | FSx S3 AP → Textract → S3 (結果) |
| 音声文字起こし | Transcribe | FSx S3 AP → Transcribe → S3 (結果) |
| 異常検知 | SageMaker | DataSync subset → S3 → SageMaker Training |

### AWS ネイティブ固有の強み

- **Lake Formation**: Athena、Redshift、EMR 全てに一貫したガバナンスを強制
- **FSx S3 AP 直接アクセス**: S3 コピーなしで Athena/Bedrock から直接クエリ
- **Bedrock Knowledge Base**: FSx S3 AP を直接データソースとして RAG 構築可能
- **マネージドサービス**: インフラ運用なしで AI/分析パイプライン構築

### 制約事項

- Athena は VPC-origin AP にアクセス不可（Internet-origin AP が必要）
- Lake Formation のデータリネージは組み込みではない（別途構築が必要）
- Bedrock KB は非構造化データの自動インデックスのみ（構造化クエリは Athena）

---

## プラットフォーム比較

| 観点 | Databricks | Snowflake | AWS ネイティブ |
|------|-----------|-----------|--------------|
| **FSx S3 AP 直接アクセス** | ❌（UC Session Policy 制約） | ⚠️（LIST のみ、GetObject ブロック） | ✅（Athena, Bedrock 直接アクセス） |
| **ガバナンスモデル** | UC Tags + Row Filter + Column Mask | Row Access Policy + Masking + Tags | Lake Formation LF-Tags |
| **外部エンジンへのガバナンス強制** | ❌（UC は外部エンジンに強制しない） | ✅（Horizon Catalog が強制） | ✅（Lake Formation が全エンジンに強制） |
| **組織横断共有** | Delta Sharing（オープンプロトコル） | Secure Data Sharing（ゼロコピー） | Lake Formation Cross-account + RAM |
| **非構造化データ AI** | Mosaic AI, Vector Search | Cortex AI, Cortex Search | Bedrock, Textract, Transcribe |
| **重複排除** | なし（S3 依存） | なし（S3 依存） | なし（S3 依存） |
| **FSx for ONTAP + dedup** | ✅（Option B/C/D で解決） | ✅（Option B/C/D で解決） | ✅（Option B/C/D で解決） |

---

## 推奨マトリクス

| 優先事項 | 推奨 | 理由 |
|---------|------|------|
| **最速のコスト削減** | Phase 1 (S3 Tiering) + Phase 2 (FSx for ONTAP) | 即効性 + 根本解決の組み合わせ |
| **最大の帯域効率** | Option C（SnapMirror） | ブロックレベル差分 = DataSync の 2,500 倍 |
| **将来最適（最低コスト）** | Option D（FlexCache S3 AP） | キャッシュのみ = 現行比 80% 削減 |
| **マルチエンジンガバナンス** | Snowflake Horizon または Lake Formation | 外部エンジンにもガバナンス強制 |
| **組織横断共有** | Delta Sharing（広い互換性）または Snowflake Sharing（ゼロコピー） | 要件に応じて選択 |

---

## ペルソナ別サマリー

| ペルソナ | 主要推奨 |
|---------|---------|
| **Snowflake PMM（高橋さん）** | Horizon Catalog で外部エンジンへのガバナンス強制が可能。非構造化データの AI-Ready 化には Cortex Search + Data Sharing が最短パス。Databricks 環境でも Horizon 経由で Snowflake ガバナンスを適用できる。Managed Iceberg Table → Horizon REST Catalog で Databricks/Spark からも読み取り可能（閉じた世界ではない）。 |
| **Databricks SA（倉光さん）** | UC Volumes + Delta Sharing が正解。Mosaic AI で非構造化データのタグ自動付与を実現。S3 コスト削減には FSx for ONTAP を戦略的に推奨。将来的には Lakehouse Federation で FSx S3 AP 上のデータを仮想的に参照するパスも検討対象。 |
| **AWS Iceberg SA（疋田さん）** | FSx for ONTAP S3 AP + Lake Formation で S3 コピー廃止 + 全エンジンガバナンス。Bedrock KB が FSx S3 AP を直接参照できるのは AWS ネイティブの強み。Glue Catalog + Iceberg 形式での保存パスも Open Table Format の選択肢として有効。 |
| **Storage Specialist** | ONTAP 重複排除が根本解決。同一ファイルの複数コピー（バージョン違い、部門別コピー）に対して最も効果的。画像/動画の「類似ファイル」間の dedup 効果は限定的（同一ブロックがある場合のみ）。 |
| **Partner SA** | NetApp Console + DataSync → FSx マイグレーションが確立されたパス（10TB / Direct Connect 1Gbps で約22時間）。FlexCache S3 AP はハイブリッド環境のゲームチェンジャー。 |
| **Public Sector SA** | データ主権要件では Option C（オンプレ ONTAP + SnapMirror）が必須。医療画像(DICOM)や監視映像は PII/PHI に該当する可能性があり、匿名化パイプラインの検討が必要。 |
| **Outcome SA** | 顧客のゴールは「コスト削減 + ガバナンス付き組織横断活用」。段階的導入（Phase 1→2→3）で投資リスクを最小化しながら成果を積み上げる。成功指標: ストレージコスト削減率、データ発見時間、共有リクエスト→利用開始時間。業界別例: 製造（設計図面の全社再利用）、金融（契約書のコンプライアンス検索）、医療（DICOM の研究部門共有）。 |

---

## 運用監視・セキュリティ監視

本ドキュメントで提案するアーキテクチャの運用監視（Observability）およびセキュリティ監視（SIEM）については、以下の別プロジェクトで詳細に扱っています:

| 領域 | リポジトリ | 内容 |
|------|-----------|------|
| **Observability** | [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | FSx for ONTAP の監査ログを Datadog、Splunk、Grafana、Elastic 等に連携。S3 AP 経由の Lambda パイプライン。 |
| **SLO / アラート** | [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | SLO Observability パターン、FPolicy イベント駆動パイプライン、容量ガードレール。 |

### 本アーキテクチャで監視すべき主要メトリクス

| メトリクス | 監視対象 | アラート条件例 |
|-----------|---------|--------------|
| DataSync / SnapMirror 同期遅延 | 同期パイプライン | lag > 1時間 |
| FSx S3 AP レイテンシー | S3 API 応答時間 | p99 > 5秒 |
| FlexCache ヒット率 | キャッシュ効率 | hit rate < 80% |
| ストレージ使用量 / dedup 率 | コスト最適化 | 使用率 > 85% |
| アクセス拒否イベント | セキュリティ | AccessDenied > 10回/10分 |
| 非構造化データアクセスパターン | DLP / 異常検知 | 通常の 10倍以上のダウンロード |

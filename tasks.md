# E2E Verification Tasks / E2E 検証タスク

🌐 [日本語](#日本語) | [English](#english)

---

<a id="english"></a>

## English

This document defines the end-to-end verification tasks for each vendor integration.
Each vendor follows the same 5-phase structure to ensure consistent quality.

### Task Structure (Per Vendor)

| Phase | Task | Description |
|-------|------|-------------|
| A | Vendor Account Preparation | Account setup, credentials, API keys |
| B | AWS Infrastructure Deploy | CloudFormation/Terraform, connectivity validation |
| C | Vendor UI Configuration | Platform-specific setup, screenshot capture |
| D | Demo Scenario Execution | End-to-end data flow verification |
| E | Verification & Final Check | Results recording, report generation |

---

### Databricks Integration Tasks

#### Task A: Vendor Account Preparation

- [ ] Create/confirm Databricks workspace (Unity Catalog enabled)
- [ ] Obtain Databricks Account ID and Workspace ID
- [ ] Verify Unity Catalog Metastore is configured
- [ ] Confirm Databricks AWS Account ID for cross-account trust (`414351767826`)
- [ ] Document workspace URL and admin credentials
- [ ] Verify Databricks CLI is installed and configured

#### Task B: AWS Infrastructure Deploy & Validation

- [ ] Deploy `shared/cloudformation/vpc-networking.yaml` stack
- [ ] Deploy `shared/cloudformation/fsxn-s3ap-base.yaml` stack
- [ ] Deploy `integrations/databricks/template.yaml` stack
- [ ] Verify S3 Access Point creation (alias, ARN)
- [ ] Verify IAM Role trust policy (External ID)
- [ ] Test S3 AP connectivity: `python shared/scripts/validate-access.py --access-point-alias <alias>`
- [ ] Verify VPC Endpoint routing (Interface endpoint for S3)
- [ ] Run CloudWatch Logs check for any errors
- [ ] Validate cross-account AssumeRole from Databricks account

#### Task C: Databricks UI Configuration & Screenshots

- [ ] Create Storage Credential in Databricks UI
  - Screenshot: Storage Credential creation dialog
  - Screenshot: Credential validation success
- [ ] Create External Location
  - Screenshot: External Location creation with S3 AP URL
  - Screenshot: Connection test success
- [ ] Create Catalog and Schemas (bronze/silver/gold)
  - Screenshot: Catalog Explorer showing hierarchy
- [ ] Configure Cluster Policy
  - Screenshot: Cluster policy with S3 AP settings

#### Task D: Demo Scenario Execution

**Scenario 1: External Table Query (Pattern A)**
- [ ] Upload sample Parquet data to FSxN via NFS
- [ ] Create External Table pointing to S3 AP
- [ ] Execute SELECT query and verify results
- [ ] Measure query latency

**Scenario 2: Delta Lake CRUD (Pattern B)**
- [ ] Create Delta table on FSxN via S3 AP
- [ ] Execute INSERT, UPDATE, DELETE operations
- [ ] Verify Delta Time Travel (VERSION AS OF)
- [ ] Run OPTIMIZE and verify file compaction

**Scenario 3: Iceberg Table (Cross-Platform)**
- [ ] Create Iceberg table on FSxN
- [ ] Verify metadata files on FSxN volume
- [ ] Query from Databricks
- [ ] (Optional) Query same table from Athena

**Scenario 4: ONTAP Snapshot + FlexClone**
- [ ] Create ONTAP Snapshot of silver volume
- [ ] Create FlexClone from snapshot
- [ ] Attach new S3 AP to clone
- [ ] Query cloned data from Databricks (verify isolation)

#### Task E: Verification & Final Check

- [ ] Record all test results in `integrations/databricks/tests/results/`
- [ ] Capture performance metrics (latency, throughput)
- [ ] Verify bilingual documentation accuracy
- [ ] Generate verification report (JA/EN)
- [ ] Screenshot comparison: expected vs actual UI states
- [ ] Confirm cleanup of test resources

---

### Snowflake Integration Tasks

#### Task A: Vendor Account Preparation

- [ ] Create/confirm Snowflake account (Enterprise Edition+)
- [ ] Verify ACCOUNTADMIN role access
- [ ] Confirm Snowflake region matches FSxN region (ap-northeast-1)
- [ ] Document Snowflake account locator and URL
- [ ] Install SnowSQL CLI
- [ ] Verify Snowflake AWS Account ID (from DESCRIBE INTEGRATION)

#### Task B: AWS Infrastructure Deploy & Validation

- [ ] Deploy `integrations/snowflake/template.yaml` stack
- [ ] Verify S3 Access Point creation
- [ ] Verify IAM Role (initial trust to own account)
- [ ] Test S3 AP connectivity
- [ ] (If Snowpipe) Deploy SNS Topic and verify
- [ ] Validate VPC Endpoint configuration

#### Task C: Snowflake UI Configuration & Screenshots

- [ ] Create Storage Integration (SQL)
  - Screenshot: DESCRIBE INTEGRATION output
- [ ] Update CloudFormation with Snowflake trust info
  - Screenshot: Updated stack parameters
- [ ] Create External Stage
  - Screenshot: LIST @stage output showing files
- [ ] Create File Formats
  - Screenshot: SHOW FILE FORMATS output
- [ ] Create External Tables
  - Screenshot: Query results from External Table

#### Task D: Demo Scenario Execution

**Scenario 1: External Table Query (Pattern A)**
- [ ] Create External Table on Parquet data
- [ ] Execute analytical query
- [ ] Verify partition pruning works
- [ ] Measure query performance

**Scenario 2: Iceberg Table (Pattern B)**
- [ ] Create Iceberg Table (Snowflake-managed catalog)
- [ ] Execute DML operations (INSERT, UPDATE, DELETE)
- [ ] Verify Iceberg Time Travel
- [ ] Check metadata files on FSxN

**Scenario 3: Snowpipe Auto-Ingest**
- [ ] Configure Lambda polling function
- [ ] Add new file to FSxN via NFS
- [ ] Verify Snowpipe detects and loads file
- [ ] Check COPY_HISTORY for load confirmation

**Scenario 4: Secure Data Sharing**
- [ ] Create Secure View on FSxN data
- [ ] Create Share and add consumer
- [ ] Verify consumer can query shared data
- [ ] Verify access revocation works

#### Task E: Verification & Final Check

- [ ] Record all test results
- [ ] Capture performance metrics
- [ ] Verify bilingual documentation accuracy
- [ ] Generate verification report (JA/EN)
- [ ] Confirm cleanup of test resources

---

### AWS Athena Integration Tasks

#### Task A: Vendor Account Preparation

- [ ] Verify AWS account has Athena access
- [ ] Configure Athena workgroup and result location
- [ ] Verify Glue Data Catalog permissions
- [ ] Confirm FSxN S3 AP has internet network origin (required for Athena)

#### Task B: AWS Infrastructure Deploy & Validation

- [ ] Deploy Athena integration CloudFormation stack
- [ ] Create S3 Access Point with internet network origin
- [ ] Configure Glue Crawler for S3 AP
- [ ] Verify IAM permissions for Athena → S3 AP
- [ ] Run Glue Crawler and verify table creation in Data Catalog

#### Task C: Athena UI Configuration & Screenshots

- [ ] Verify Glue Data Catalog tables
  - Screenshot: Glue console showing discovered tables
- [ ] Configure Athena workgroup
  - Screenshot: Athena workgroup settings
- [ ] Run first query
  - Screenshot: Athena query editor with results

#### Task D: Demo Scenario Execution

**Scenario 1: Direct Query on FSxN Data**
- [ ] Query Parquet files via Athena
- [ ] Query CSV files with SerDe
- [ ] Verify partition projection
- [ ] Measure query cost and latency

**Scenario 2: CTAS (Create Table As Select)**
- [ ] Create curated table from raw FSxN data
- [ ] Write results back to FSxN via S3 AP
- [ ] Verify data on FSxN volume

#### Task E: Verification & Final Check

- [ ] Record query results and performance
- [ ] Document cost analysis
- [ ] Generate verification report (JA/EN)

---

### AWS Glue Integration Tasks

#### Task A: Vendor Account Preparation

- [ ] Verify AWS Glue service access
- [ ] Configure Glue service role
- [ ] Verify Lake Formation permissions (if applicable)

#### Task B: AWS Infrastructure Deploy & Validation

- [ ] Deploy Glue integration CloudFormation stack
- [ ] Create Glue Connection for S3 AP
- [ ] Configure Glue Crawler
- [ ] Deploy Glue ETL Job (PySpark)
- [ ] Verify CloudWatch Events/EventBridge triggers

#### Task C: Glue UI Configuration & Screenshots

- [ ] Glue Crawler configuration
  - Screenshot: Crawler pointing to S3 AP
- [ ] Glue ETL Job
  - Screenshot: Job graph (visual ETL)
- [ ] Data Catalog tables
  - Screenshot: Discovered schema

#### Task D: Demo Scenario Execution

**Scenario 1: Medallion Architecture ETL**
- [ ] Run Crawler on bronze data (FSxN)
- [ ] Execute ETL Job: Bronze → Silver transformation
- [ ] Execute ETL Job: Silver → Gold aggregation
- [ ] Verify output on FSxN gold volume

**Scenario 2: Data Quality Checks**
- [ ] Configure Glue Data Quality rules
- [ ] Run quality checks on FSxN data
- [ ] Verify quality metrics

#### Task E: Verification & Final Check

- [ ] Record ETL job metrics (duration, DPU usage)
- [ ] Document data lineage
- [ ] Generate verification report (JA/EN)

---

### Redshift Spectrum Integration Tasks

#### Task A: Vendor Account Preparation

- [ ] Verify Redshift cluster or Serverless endpoint
- [ ] Configure Redshift IAM role for S3 AP access
- [ ] Verify Glue Data Catalog integration

#### Task B: AWS Infrastructure Deploy & Validation

- [ ] Deploy Redshift Spectrum integration stack
- [ ] Create external schema pointing to Glue catalog
- [ ] Verify S3 AP access from Redshift

#### Task C: Redshift UI Configuration & Screenshots

- [ ] External schema creation
  - Screenshot: Redshift Query Editor showing external tables
- [ ] Query execution
  - Screenshot: Query results with FSxN data

#### Task D: Demo Scenario Execution

**Scenario 1: Federated Query**
- [ ] Query FSxN data via Spectrum
- [ ] Join external (FSxN) and local Redshift tables
- [ ] Verify predicate pushdown

#### Task E: Verification & Final Check

- [ ] Record query performance
- [ ] Generate verification report (JA/EN)

---

## Verification Tools / 検証ツール

### Bilingual Comparison Tool

Validates that JA and EN documentation are synchronized:
- Checks section count matches
- Validates code blocks are identical
- Reports missing translations

### Screenshot Validator

Validates captured screenshots against expected states:
- UI element presence check
- Success/error state verification
- Timestamp and version annotation

### Report Renderer

Generates final verification reports:
- Markdown format (JA/EN)
- Includes screenshots, metrics, pass/fail status
- Exportable to PDF

---

<a id="日本語"></a>

## 日本語

各ベンダー統合の E2E 検証タスクを定義します。
全ベンダーで同じ5フェーズ構造に従い、品質の一貫性を確保します。

### タスク構造（ベンダーごと）

| フェーズ | タスク | 説明 |
|---------|--------|------|
| A | ベンダーアカウント準備 | アカウント設定、認証情報、API キー |
| B | AWS インフラデプロイ | CloudFormation/Terraform、接続検証 |
| C | ベンダー UI 設定 | プラットフォーム固有設定、スクリーンショット撮影 |
| D | デモシナリオ実行 | E2E データフロー検証 |
| E | 検証結果の記録と最終確認 | 結果記録、レポート生成 |

### Databricks 統合タスク

#### タスク A: ベンダーアカウント準備と認証情報設定

- [ ] Databricks ワークスペースの作成/確認（Unity Catalog 有効）
- [ ] Databricks Account ID と Workspace ID の取得
- [ ] Unity Catalog Metastore の設定確認
- [ ] クロスアカウント信頼用 Databricks AWS Account ID の確認（`414351767826`）
- [ ] ワークスペース URL と管理者認証情報の文書化
- [ ] Databricks CLI のインストールと設定確認

#### タスク B: AWS インフラデプロイと動作確認

- [ ] `shared/cloudformation/vpc-networking.yaml` スタックのデプロイ
- [ ] `shared/cloudformation/fsxn-s3ap-base.yaml` スタックのデプロイ
- [ ] `integrations/databricks/template.yaml` スタックのデプロイ
- [ ] S3 Access Point の作成確認（alias, ARN）
- [ ] IAM Role 信頼ポリシーの確認（External ID）
- [ ] S3 AP 接続テスト: `python shared/scripts/validate-access.py --access-point-alias <alias>`
- [ ] VPC Endpoint ルーティングの確認
- [ ] CloudWatch Logs のエラーチェック
- [ ] Databricks アカウントからのクロスアカウント AssumeRole 検証

#### タスク C: Databricks UI 設定とスクリーンショット撮影

- [ ] Storage Credential の作成
  - スクリーンショット: 作成ダイアログ
  - スクリーンショット: 検証成功
- [ ] External Location の作成
  - スクリーンショット: S3 AP URL での作成
  - スクリーンショット: 接続テスト成功
- [ ] Catalog とスキーマの作成（bronze/silver/gold）
  - スクリーンショット: Catalog Explorer の階層表示
- [ ] Cluster Policy の設定
  - スクリーンショット: S3 AP 設定を含むポリシー

#### タスク D: デモシナリオ実行

**シナリオ 1: External Table クエリ（パターン A）**
- [ ] NFS 経由で FSxN にサンプル Parquet データをアップロード
- [ ] S3 AP を指す External Table を作成
- [ ] SELECT クエリを実行し結果を検証
- [ ] クエリレイテンシを計測

**シナリオ 2: Delta Lake CRUD（パターン B）**
- [ ] S3 AP 経由で FSxN 上に Delta テーブルを作成
- [ ] INSERT, UPDATE, DELETE 操作を実行
- [ ] Delta Time Travel を検証（VERSION AS OF）
- [ ] OPTIMIZE を実行しファイル圧縮を確認

**シナリオ 3: Iceberg テーブル（クロスプラットフォーム）**
- [ ] FSxN 上に Iceberg テーブルを作成
- [ ] FSxN ボリューム上のメタデータファイルを確認
- [ ] Databricks からクエリ
- [ ] （オプション）同じテーブルを Athena からクエリ

**シナリオ 4: ONTAP Snapshot + FlexClone**
- [ ] silver ボリュームの ONTAP Snapshot を作成
- [ ] Snapshot から FlexClone を作成
- [ ] クローンに新しい S3 AP をアタッチ
- [ ] Databricks からクローンデータをクエリ（分離を確認）

#### タスク E: 検証結果の記録と最終確認

- [ ] 全テスト結果を `integrations/databricks/tests/results/` に記録
- [ ] パフォーマンスメトリクスの取得（レイテンシ、スループット）
- [ ] バイリンガルドキュメントの正確性確認
- [ ] 検証レポートの生成（日英）
- [ ] スクリーンショット比較: 期待値 vs 実際の UI 状態
- [ ] テストリソースのクリーンアップ確認

---

### Snowflake 統合タスク

（英語版と同一構造 — 詳細は英語セクション参照）

### AWS Athena 統合タスク

（英語版と同一構造 — 詳細は英語セクション参照）

### AWS Glue 統合タスク

（英語版と同一構造 — 詳細は英語セクション参照）

### Redshift Spectrum 統合タスク

（英語版と同一構造 — 詳細は英語セクション参照）

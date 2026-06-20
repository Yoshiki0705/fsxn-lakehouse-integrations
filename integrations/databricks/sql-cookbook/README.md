🌐 [English](#english) | [日本語](#日本語)

---

# 日本語

# Databricks UC ガバナンス SQL Cookbook

> **目的**: DataSync → S3 パスで FSx for ONTAP データを UC に取り込んだ後のガバナンス設定を、コピー＆ペーストで実行可能な SQL として提供します。
> **前提条件**: DataSync で FSx for ONTAP → S3 同期済み（[DataSync ガイド](../../docs/ja/datasync-to-s3-guide.md) Phase 1-3 完了）
> **対象**: Databricks SQL Warehouse または DBR 15.4+ クラスター

## レシピ一覧

| # | レシピ | ユースケース |
|:---:|---|---|
| 1 | [Storage Credential 作成](#1-storage-credential-作成) | IAM Role ベースの S3 認証設定 |
| 2 | [External Location 登録](#2-external-location-登録) | DataSync 同期先 S3 を UC に接続 |
| 3 | [External Table 作成](#3-external-table-作成parquet) | 同期済みデータのテーブル化 |
| 4 | [Managed Table 作成（Delta）](#4-managed-table-作成delta) | Delta 形式への変換 |
| 5 | [UC Volume 登録](#5-uc-volume-登録) | ファイルレベルアクセス（画像/PDF） |
| 6 | [Row Filter 設定](#6-row-filter-設定) | 行レベルアクセス制御 |
| 7 | [Column Mask 設定](#7-column-mask-設定) | 列レベルデータマスキング |
| 8 | [Tag 付与](#8-tag-付与) | メタデータ分類/ABAC |
| 9 | [Auto Loader（通知モード）](#9-auto-loader通知モード) | 増分取り込みパイプライン |
| 10 | [監査クエリ](#10-監査クエリ) | アクセス履歴の確認 |

---

## 1. Storage Credential 作成

> IAM Role の信頼ポリシーで Databricks の External ID を設定済みであること

```sql
-- Storage Credential: Databricks が S3 にアクセスするための IAM Role 紐付け
CREATE STORAGE CREDENTIAL IF NOT EXISTS fsxn_synced_credential
COMMENT 'DataSync destination S3 access for FSx for ONTAP synced data'
WITH (
  AWS_IAM_ROLE = 'arn:aws:iam::<ACCOUNT_ID>:role/DatabricksS3AccessRole'
);

-- 確認
DESCRIBE STORAGE CREDENTIAL fsxn_synced_credential;
```

> **最小権限** (IAM Security Architect lens): Databricks 用 IAM Role には `s3:GetObject` / `s3:ListBucket` / `s3:GetBucketLocation` のみ付与してください。`s3:PutObject` は DataSync サービスロール専用とし、Databricks からの書き込みは Managed Table（Databricks 管理 S3）に限定します。

---

## 2. External Location 登録

```sql
-- External Location: S3 プレフィックスを UC に登録
CREATE EXTERNAL LOCATION IF NOT EXISTS fsxn_synced
URL 's3://<BUCKET_NAME>/fsxn-sync/'
WITH (STORAGE CREDENTIAL fsxn_synced_credential)
COMMENT 'FSx for ONTAP data synced via DataSync';

-- 接続テスト
VALIDATE EXTERNAL LOCATION fsxn_synced;

-- ファイル確認
LIST 's3://<BUCKET_NAME>/fsxn-sync/sensor-data/';
```

> **プレフィックス分離** (Data Governance Specialist lens): DataSync 書き込みプレフィックスと Databricks 読み取りプレフィックスを同一にする場合、S3 バケットポリシーで Databricks IAM Role に `s3:PutObject` を明示的に Deny してください。書き込み権限は DataSync サービスロールのみに限定します。

---

## 3. External Table 作成（Parquet）

```sql
-- External Table: 同期済み Parquet データをテーブル化
CREATE TABLE IF NOT EXISTS catalog_name.schema_name.sensor_data_ext (
  timestamp TIMESTAMP,
  line_id STRING,
  equipment_id STRING,
  sensor_type STRING,
  value DOUBLE,
  unit STRING,
  status STRING
)
USING PARQUET
LOCATION 's3://<BUCKET_NAME>/fsxn-sync/sensor-data/'
COMMENT 'Sensor data synced from FSx for ONTAP via DataSync';

-- データ確認
SELECT * FROM catalog_name.schema_name.sensor_data_ext LIMIT 10;

-- 統計確認
SELECT status, COUNT(*) as cnt, AVG(value) as avg_value
FROM catalog_name.schema_name.sensor_data_ext
GROUP BY status;
```

---

## 4. Managed Table 作成（Delta）

```sql
-- Managed Table (Delta): フルガバナンス適用（lineage, time travel, optimize）
CREATE TABLE IF NOT EXISTS catalog_name.schema_name.sensor_data
COMMENT 'Production sensor data - Delta format with full UC governance'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true'
)
AS SELECT * FROM catalog_name.schema_name.sensor_data_ext;

-- Time Travel 確認
DESCRIBE HISTORY catalog_name.schema_name.sensor_data;

-- Optimize（大量データ投入後）
OPTIMIZE catalog_name.schema_name.sensor_data;
```

> **Managed vs External** (Databricks Governance Architect lens): Managed Table は Databricks が S3 上のストレージライフサイクルを完全管理します。Time Travel、OPTIMIZE、Z-ORDER が利用可能です。読み取り専用の分析には External Table で十分ですが、DML（UPDATE/DELETE/MERGE）が必要な場合は Managed Table にコピーしてください。

---

## 5. UC Volume 登録

```sql
-- External Volume: ファイルレベルアクセス（画像、PDF、Office 文書）
CREATE EXTERNAL VOLUME IF NOT EXISTS catalog_name.schema_name.fsxn_files
LOCATION 's3://<BUCKET_NAME>/fsxn-sync/'
WITH (STORAGE CREDENTIAL fsxn_synced_credential)
COMMENT 'FSx for ONTAP synced files - file-level access via /Volumes/';

-- ファイル一覧
LIST '/Volumes/catalog_name/schema_name/fsxn_files/quality-images/';

-- Python からのアクセス
-- df = spark.read.format("binaryFile").load("/Volumes/catalog_name/schema_name/fsxn_files/quality-images/*.jpg")
```

> **Volume vs External Table** (Data Engineering SA lens): UC Volume（2024 年導入）は構造化テーブルではなくファイルレベルのアクセスを提供します。画像/PDF/動画などの非構造化データには Volume を使用し、構造化データ（CSV/Parquet）には External Table または Managed Table を使用してください。

---

## 6. Row Filter 設定

```sql
-- Row Filter 関数: ユーザーのグループに基づいて行をフィルタ
CREATE OR REPLACE FUNCTION catalog_name.schema_name.filter_by_line(line_id STRING)
RETURN
  -- factory_a_group: LINE-A* のみ閲覧可能
  -- factory_b_group: LINE-B* のみ閲覧可能
  -- data_platform_group: 全行閲覧可能
  CASE
    WHEN is_account_group_member('factory_a_group') THEN line_id LIKE 'LINE-A%'
    WHEN is_account_group_member('factory_b_group') THEN line_id LIKE 'LINE-B%'
    WHEN is_account_group_member('data_platform_group') THEN TRUE
    ELSE FALSE
  END;

-- Row Filter をテーブルに適用
ALTER TABLE catalog_name.schema_name.sensor_data
SET ROW FILTER catalog_name.schema_name.filter_by_line ON (line_id);

-- 動作確認（factory_a_group メンバーとして）
SELECT DISTINCT line_id FROM catalog_name.schema_name.sensor_data;
-- 期待結果: LINE-A01, LINE-A02 のみ

-- Row Filter 解除（必要時）
-- ALTER TABLE catalog_name.schema_name.sensor_data DROP ROW FILTER;
```

> **Row Filter の設計原則** (Databricks Governance Architect lens): Row Filter は「テーブルを分割せずにアクセス制御を実現する」メカニズムです。工場単位、部門単位、地域単位でデータを分離する場合に有効です。ただし、Row Filter は UC 内エンジンでのみ強制されます。Athena や外部エンジンからの読み取りには適用されません。

---

## 7. Column Mask 設定

```sql
-- Column Mask 関数: 権限のないユーザーにはセンサー値をマスク
CREATE OR REPLACE FUNCTION catalog_name.schema_name.mask_sensor_value(value DOUBLE)
RETURN
  CASE
    WHEN is_account_group_member('data_platform_group') THEN value  -- フル閲覧
    WHEN is_account_group_member('factory_a_group') THEN value      -- 自工場データは閲覧可
    ELSE NULL  -- それ以外はマスク
  END;

-- Column Mask をテーブルに適用
ALTER TABLE catalog_name.schema_name.sensor_data
ALTER COLUMN value SET MASK catalog_name.schema_name.mask_sensor_value;

-- 動作確認
SELECT timestamp, line_id, sensor_type, value, status
FROM catalog_name.schema_name.sensor_data LIMIT 5;
-- 期待結果: 権限のない行の value は NULL

-- Column Mask 解除（必要時）
-- ALTER TABLE catalog_name.schema_name.sensor_data ALTER COLUMN value DROP MASK;
```

> **Column Mask vs Views** (Databricks Governance Architect lens): Column Mask はテーブルレベルで強制されるため、どのクエリからアクセスしてもマスクが適用されます。View ベースのマスキングは View を経由しないアクセスでバイパス可能なため、Column Mask を推奨します。

---

## 8. Tag 付与

```sql
-- Tag 作成（カタログレベル）
CREATE TAG IF NOT EXISTS catalog_name.data_classification
COMMENT 'Data classification for governance';

CREATE TAG IF NOT EXISTS catalog_name.data_source
COMMENT 'Data source system identifier';

CREATE TAG IF NOT EXISTS catalog_name.retention_policy
COMMENT 'Data retention policy';

-- テーブルに Tag 付与
ALTER TABLE catalog_name.schema_name.sensor_data
SET TAGS ('data_classification' = 'internal',
          'data_source' = 'fsxn-production-svm',
          'retention_policy' = '7-years');

-- 列に Tag 付与（PII マーキング等）
ALTER TABLE catalog_name.schema_name.sensor_data
ALTER COLUMN equipment_id SET TAGS ('pii_level' = 'none');

-- Tag 検索
SELECT * FROM system.information_schema.table_tags
WHERE tag_name = 'data_classification' AND tag_value = 'internal';

-- Tag によるテーブル発見
SELECT table_catalog, table_schema, table_name, tag_value
FROM system.information_schema.table_tags
WHERE tag_name = 'data_source' AND tag_value LIKE 'fsxn%';
```

> **Tag と S3 Annotations の関係** (Data Governance Specialist lens): UC Tags と S3 Annotations は並行する別メカニズムです。S3 Annotations はオブジェクトレベルの発見シグナル、UC Tags はテーブル/列レベルのガバナンスメタデータです。annotation → UC Tag のマッピングパイプラインは別途設計が必要です（[S3 Annotations 評価](../../docs/ja/s3-annotations-governance-evaluation.md) 参照）。

---

## 9. Auto Loader（通知モード）

```python
# Auto Loader: DataSync が S3 に同期した新規ファイルを自動検出・取り込み
# ※ Python notebook で実行（SQL ではなく PySpark）

from pyspark.sql.functions import current_timestamp, input_file_name

# 通知モード: S3 Event Notifications 使用（標準 S3 バケットで動作）
df = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.schemaLocation", "/Volumes/catalog_name/schema_name/checkpoints/sensor_schema/")
    .option("cloudFiles.useNotifications", "true")  # 通知モード（標準 S3 のみ）
    .option("cloudFiles.region", "ap-northeast-1")
    .option("header", "true")
    .option("inferSchema", "true")
    .load("s3://<BUCKET_NAME>/fsxn-sync/sensor-data/")
    .withColumn("_ingested_at", current_timestamp())
    .withColumn("_source_file", input_file_name())
)

# UC Managed Table に書き込み（streaming append）
(df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "/Volumes/catalog_name/schema_name/checkpoints/sensor_stream/")
    .trigger(availableNow=True)  # バッチ: 利用可能な新規ファイルを全て処理して停止
    # .trigger(processingTime="5 minutes")  # ストリーミング: 5分ごとに処理
    .toTable("catalog_name.schema_name.sensor_data")
)
```

> **通知モード vs リスティングモード** (Data Engineering SA lens): `cloudFiles.useNotifications = true` は S3 Event Notifications に依存するため、**DataSync → 標準 S3** パスでのみ動作します。FSx for ONTAP S3 AP 直接ではイベント通知が非サポートのため使用できません（[BLK-003](../../docs/ja/blocker-tracker.md)）。標準 S3 への同期はこの通知モードを有効化する主要なメリットの一つです。

---

## 10. 監査クエリ

```sql
-- 誰がどのテーブルにアクセスしたか（直近7日間）
SELECT
  event_time,
  user_identity.email as user_email,
  request_params.full_name_arg as table_name,
  action_name,
  response.status_code
FROM system.access.audit
WHERE action_name IN ('getTable', 'commandSubmit', 'generateTemporaryTableCredential')
  AND request_params.full_name_arg LIKE 'catalog_name.schema_name.sensor%'
  AND event_time > current_timestamp() - INTERVAL 7 DAYS
ORDER BY event_time DESC;

-- Row Filter/Column Mask の適用回数
SELECT
  event_time,
  user_identity.email,
  request_params.full_name_arg,
  action_name
FROM system.access.audit
WHERE action_name = 'generateTemporaryTableCredential'
  AND event_time > current_timestamp() - INTERVAL 30 DAYS
ORDER BY event_time DESC
LIMIT 100;
```

> **監査要件** (Security Audit Specialist lens): 製造データのガバナンスでは「誰が、いつ、どのデータに、どのような操作を行ったか」の追跡が必須です。UC 監査ログ（`system.access.audit`）と CloudTrail（DataSync 操作）を組み合わせることで、FSx for ONTAP → S3 → UC の全データフローを追跡できます。

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| `VALIDATE EXTERNAL LOCATION` 失敗 | IAM Role の信頼ポリシーに External ID 未設定 | [公式: 信頼ポリシー設定](https://docs.databricks.com/en/connect/unity-catalog/storage-credentials.html) |
| `LIST` で空結果 | DataSync 未実行 or プレフィックスの不一致 | DataSync タスクステータス確認 + S3 パス確認 |
| Row Filter が効かない | グループメンバーシップ未設定 | `SELECT is_account_group_member('group_name')` で確認 |
| Auto Loader がファイルを検出しない | 通知モードの SQS 設定不備 | CloudWatch で SQS メッセージ数を確認 |
| Column Mask で NULL が返る | マスク関数の条件に合致しない | 自分のグループを `current_groups()` で確認 |

---

## 関連ドキュメント

- [DataSync → S3 ガイド](../../docs/ja/datasync-to-s3-guide.md) — 前提手順（Phase 1-3）
- [UC 接続総合ガイド](../../docs/ja/fsxn-to-databricks-unity-catalog-guide.md) — 全接続パスの俯瞰
- [ブロッカー追跡](../../docs/ja/blocker-tracker.md) — BLK-001/003 の回避として本 Cookbook を使用
- [S3 Annotations 評価](../../docs/ja/s3-annotations-governance-evaluation.md) — annotation → UC Tag マッピング
- [サンプルデータ](../../samples/manufacturing/) — 本 Cookbook の入力データ

---
---

<a name="english"></a>

# English

# Databricks UC Governance SQL Cookbook

> **Purpose**: Provides copy-paste SQL for governance setup after ingesting FSx for ONTAP data into UC via the DataSync → S3 path.
> **Prerequisites**: DataSync FSx for ONTAP → S3 sync completed ([DataSync Guide](../../docs/en/datasync-to-s3-guide.md) Phase 1-3)
> **Target**: Databricks SQL Warehouse or DBR 15.4+ cluster

## Recipe List

| # | Recipe | Use Case |
|:---:|---|---|
| 1 | [Storage Credential](#1-storage-credential) | IAM Role-based S3 authentication |
| 2 | [External Location](#2-external-location) | Connect DataSync destination S3 to UC |
| 3 | [External Table (Parquet)](#3-external-table-parquet) | Tabularize synced data |
| 4 | [Managed Table (Delta)](#4-managed-table-delta) | Convert to Delta format |
| 5 | [UC Volume](#5-uc-volume) | File-level access (images/PDFs) |
| 6 | [Row Filter](#6-row-filter) | Row-level access control |
| 7 | [Column Mask](#7-column-mask) | Column-level data masking |
| 8 | [Tags](#8-tags) | Metadata classification/ABAC |
| 9 | [Auto Loader (Notification Mode)](#9-auto-loader-notification-mode) | Incremental ingestion pipeline |
| 10 | [Audit Queries](#10-audit-queries) | Access history verification |

---

## 1. Storage Credential

```sql
CREATE STORAGE CREDENTIAL IF NOT EXISTS fsxn_synced_credential
COMMENT 'DataSync destination S3 access for FSx for ONTAP synced data'
WITH (
  AWS_IAM_ROLE = 'arn:aws:iam::<ACCOUNT_ID>:role/DatabricksS3AccessRole'
);

DESCRIBE STORAGE CREDENTIAL fsxn_synced_credential;
```

> **Least privilege** (IAM Security Architect lens): Grant only `s3:GetObject` / `s3:ListBucket` / `s3:GetBucketLocation` to the Databricks IAM Role. Reserve `s3:PutObject` for the DataSync service role. Writes from Databricks should use Managed Tables (Databricks-managed S3).

---

## 2. External Location

```sql
CREATE EXTERNAL LOCATION IF NOT EXISTS fsxn_synced
URL 's3://<BUCKET_NAME>/fsxn-sync/'
WITH (STORAGE CREDENTIAL fsxn_synced_credential)
COMMENT 'FSx for ONTAP data synced via DataSync';

VALIDATE EXTERNAL LOCATION fsxn_synced;
LIST 's3://<BUCKET_NAME>/fsxn-sync/sensor-data/';
```

> **Prefix isolation** (Data Governance Specialist lens): If DataSync write prefix and Databricks read prefix are the same, explicitly Deny `s3:PutObject` for the Databricks IAM Role in the S3 bucket policy. Write permission should be exclusive to the DataSync service role.

---

## 3. External Table (Parquet)

```sql
CREATE TABLE IF NOT EXISTS catalog_name.schema_name.sensor_data_ext (
  timestamp TIMESTAMP,
  line_id STRING,
  equipment_id STRING,
  sensor_type STRING,
  value DOUBLE,
  unit STRING,
  status STRING
)
USING PARQUET
LOCATION 's3://<BUCKET_NAME>/fsxn-sync/sensor-data/'
COMMENT 'Sensor data synced from FSx for ONTAP via DataSync';

SELECT * FROM catalog_name.schema_name.sensor_data_ext LIMIT 10;
```

---

## 4. Managed Table (Delta)

```sql
CREATE TABLE IF NOT EXISTS catalog_name.schema_name.sensor_data
COMMENT 'Production sensor data - Delta format with full UC governance'
TBLPROPERTIES (
  'delta.autoOptimize.optimizeWrite' = 'true',
  'delta.autoOptimize.autoCompact' = 'true'
)
AS SELECT * FROM catalog_name.schema_name.sensor_data_ext;

DESCRIBE HISTORY catalog_name.schema_name.sensor_data;
OPTIMIZE catalog_name.schema_name.sensor_data;
```

> **Managed vs External** (Databricks Governance Architect lens): Managed Tables provide full storage lifecycle management by Databricks — Time Travel, OPTIMIZE, Z-ORDER. Use External Tables for read-only analytics; use Managed Tables when DML (UPDATE/DELETE/MERGE) is needed.

---

## 5. UC Volume

```sql
CREATE EXTERNAL VOLUME IF NOT EXISTS catalog_name.schema_name.fsxn_files
LOCATION 's3://<BUCKET_NAME>/fsxn-sync/'
WITH (STORAGE CREDENTIAL fsxn_synced_credential)
COMMENT 'FSx for ONTAP synced files - file-level access via /Volumes/';

LIST '/Volumes/catalog_name/schema_name/fsxn_files/quality-images/';
```

---

## 6. Row Filter

```sql
CREATE OR REPLACE FUNCTION catalog_name.schema_name.filter_by_line(line_id STRING)
RETURN
  CASE
    WHEN is_account_group_member('factory_a_group') THEN line_id LIKE 'LINE-A%'
    WHEN is_account_group_member('factory_b_group') THEN line_id LIKE 'LINE-B%'
    WHEN is_account_group_member('data_platform_group') THEN TRUE
    ELSE FALSE
  END;

ALTER TABLE catalog_name.schema_name.sensor_data
SET ROW FILTER catalog_name.schema_name.filter_by_line ON (line_id);
```

> **Row Filter enforcement scope** (Databricks Governance Architect lens): Row Filters are enforced only within UC engines. External engines (Athena, EMR reading via Iceberg REST) will NOT have these filters applied. For cross-engine enforcement, use S3 bucket policies or Lake Formation.

---

## 7. Column Mask

```sql
CREATE OR REPLACE FUNCTION catalog_name.schema_name.mask_sensor_value(value DOUBLE)
RETURN
  CASE
    WHEN is_account_group_member('data_platform_group') THEN value
    WHEN is_account_group_member('factory_a_group') THEN value
    ELSE NULL
  END;

ALTER TABLE catalog_name.schema_name.sensor_data
ALTER COLUMN value SET MASK catalog_name.schema_name.mask_sensor_value;
```

---

## 8. Tags

```sql
CREATE TAG IF NOT EXISTS catalog_name.data_classification;
CREATE TAG IF NOT EXISTS catalog_name.data_source;
CREATE TAG IF NOT EXISTS catalog_name.retention_policy;

ALTER TABLE catalog_name.schema_name.sensor_data
SET TAGS ('data_classification' = 'internal',
          'data_source' = 'fsxn-production-svm',
          'retention_policy' = '7-years');

-- Discover tables by tag
SELECT table_catalog, table_schema, table_name, tag_value
FROM system.information_schema.table_tags
WHERE tag_name = 'data_source' AND tag_value LIKE 'fsxn%';
```

---

## 9. Auto Loader (Notification Mode)

```python
from pyspark.sql.functions import current_timestamp, input_file_name

df = (spark.readStream
    .format("cloudFiles")
    .option("cloudFiles.format", "csv")
    .option("cloudFiles.schemaLocation", "/Volumes/catalog_name/schema_name/checkpoints/sensor_schema/")
    .option("cloudFiles.useNotifications", "true")
    .option("cloudFiles.region", "ap-northeast-1")
    .option("header", "true")
    .option("inferSchema", "true")
    .load("s3://<BUCKET_NAME>/fsxn-sync/sensor-data/")
    .withColumn("_ingested_at", current_timestamp())
    .withColumn("_source_file", input_file_name())
)

(df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "/Volumes/catalog_name/schema_name/checkpoints/sensor_stream/")
    .trigger(availableNow=True)
    .toTable("catalog_name.schema_name.sensor_data")
)
```

> **Notification mode dependency** (Data Engineering SA lens): `cloudFiles.useNotifications = true` depends on S3 Event Notifications and works **only on standard S3** (the DataSync destination). It does NOT work on FSx for ONTAP S3 AP directly ([BLK-003](../../docs/en/blocker-tracker.md)).

---

## 10. Audit Queries

```sql
SELECT
  event_time,
  user_identity.email as user_email,
  request_params.full_name_arg as table_name,
  action_name,
  response.status_code
FROM system.access.audit
WHERE action_name IN ('getTable', 'commandSubmit', 'generateTemporaryTableCredential')
  AND request_params.full_name_arg LIKE 'catalog_name.schema_name.sensor%'
  AND event_time > current_timestamp() - INTERVAL 7 DAYS
ORDER BY event_time DESC;
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `VALIDATE EXTERNAL LOCATION` fails | External ID missing in IAM trust policy | [Docs: Trust policy setup](https://docs.databricks.com/en/connect/unity-catalog/storage-credentials.html) |
| `LIST` returns empty | DataSync not run or prefix mismatch | Check DataSync task status + S3 path |
| Row Filter not applied | Group membership not configured | Verify with `SELECT is_account_group_member('group_name')` |
| Auto Loader not detecting files | SQS notification misconfigured | Check SQS message count in CloudWatch |
| Column Mask returns NULL | Mask function condition not met | Check your groups with `current_groups()` |

---

## Related Documents

- [DataSync → S3 Guide](../../docs/en/datasync-to-s3-guide.md) — Prerequisite steps (Phase 1-3)
- [UC Connection Guide](../../docs/en/fsxn-to-databricks-unity-catalog-guide.md) — All connection paths overview
- [Blocker Tracker](../../docs/en/blocker-tracker.md) — Using this Cookbook as BLK-001/003 workaround
- [S3 Annotations Evaluation](../../docs/en/s3-annotations-governance-evaluation.md) — annotation → UC Tag mapping
- [Sample Data](../../samples/manufacturing/) — Input data for this Cookbook

🌐 [English](README.md) | **日本語**

# モジュール 04: Databricks 統合 (DataSync → S3 → Unity Catalog)

## 概要

Databricks Unity Catalog は FSx for ONTAP S3 Access Points に直接アクセスできません（セッションポリシー制限）。推奨される本番パス:

```
FSx for ONTAP (NFS) → DataSync → S3 バケット → Auto Loader → UC Managed Table
```

## 前提条件

- NFS アクセス可能なボリュームを持つ FSx for ONTAP
- 同一リージョンの S3 バケット（DataSync 宛先）
- Unity Catalog 有効な Databricks ワークスペース
- DataSync 用 IAM ロール（FSx NFS 読み取り、S3 書き込み）

## 手順

### 1. DataSync タスク作成

```bash
# CloudFormation テンプレートは datasync-task.yaml を参照
aws cloudformation deploy \
  --template-file datasync-task.yaml \
  --stack-name fsxn-databricks-sync \
  --parameter-overrides \
    SvmArn=<SVM_ARN> \
    TargetBucket=<BUCKET_NAME> \
  --capabilities CAPABILITY_IAM
```

### 2. UC External Location + テーブル作成

```sql
-- uc-setup.sql を参照
CREATE EXTERNAL LOCATION fsxn_synced
  URL 's3://<BUCKET>/fsxn-sync/'
  WITH (STORAGE CREDENTIAL <credential_name>);

CREATE TABLE catalog.schema.sensor_data
USING DELTA
AS SELECT * FROM parquet.`s3://<BUCKET>/fsxn-sync/sensor-data/`;
```

### 3. Auto Loader 設定（増分取り込み）

同期済み S3 データの増分取り込みには、宛先 S3 プレフィックスに対して Databricks Auto Loader
（`cloudFiles`）を使用します:

```python
(spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "parquet")
    .option("cloudFiles.schemaLocation", "s3://<BUCKET>/_schema/sensor-data/")
    .load("s3://<BUCKET>/fsxn-sync/sensor-data/")
    .writeStream
    .option("checkpointLocation", "s3://<BUCKET>/_checkpoint/sensor-data/")
    .toTable("main.default.sensor_data"))
```

FSx for ONTAP S3 Access Points は S3 Event Notifications を発行しないため、Auto Loader の
ファイル通知モードは利用できません。DataSync の書き込み先である標準 S3 バケットに対して、
ディレクトリリストモードで実行してください。

## コスト

| コンポーネント | 見積もり |
|------------|---------|
| DataSync (1 TB 初回) | ~$12.50 |
| DataSync (10 GB/日 増分) | ~$0.125/日 |
| S3 ストレージ (同期コピー) | ~$23/TB/月 |
| Databricks コンピュート | DBU 単位 |

## ガバナンス

データが UC に入った後:
- ✅ テーブル/カラム Grants
- ✅ Row Filters + Column Masks
- ✅ 自動リネージ
- ✅ Delta Sharing（オープンプロトコル）
- ✅ Mosaic AI（ML トレーニング、Feature Store）

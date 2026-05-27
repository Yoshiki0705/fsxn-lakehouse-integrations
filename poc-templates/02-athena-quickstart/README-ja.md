🌐 [English](README.md) | **日本語**

# モジュール 02: Athena クイックスタート

## エンドツーエンドフロー（15分）

```
Step 1: S3 AP 接続確認 (validate.sh)
  ↓
Step 2: Glue データベース + テーブル作成 (sample-queries.sql, Steps 1-2)
  ↓
Step 3: 最初のクエリ実行 (sample-queries.sql, Step 3)
  ↓
Step 4: 集計 + CTAS 書き戻し (sample-queries.sql, Steps 4-7)
```

## 前提条件

- [ ] S3 Access Point が `AVAILABLE`（先に `../scripts/validate.sh` を実行）
- [ ] サンプルデータが FSx for ONTAP にアップロード済み（`sensor-data/sensor_data.parquet`）
- [ ] Athena + Glue + S3 AP 権限付きの AWS CLI 設定済み
- [ ] 結果出力先が設定された Athena ワークグループ

## ステップバイステップ

### 1. サンプルデータ生成・アップロード（未実施の場合）

```bash
# 10K 行 Parquet ファイル生成
cd ../sample-data
python generate-sensor-data.py --rows 10000 --output sensor_data.parquet

# S3 AP 経由でアップロード
aws s3 cp sensor_data.parquet s3://<AP_ALIAS>/sensor-data/sensor_data.parquet --region ap-northeast-1
```

### 2. Glue テーブル作成

Athena コンソールまたは AWS CLI で `sample-queries.sql` の Steps 1-2 を実行:

```sql
CREATE DATABASE IF NOT EXISTS fsxn_poc;

CREATE EXTERNAL TABLE IF NOT EXISTS fsxn_poc.sensor_data (
  timestamp TIMESTAMP, device_id STRING, sensor_id STRING,
  temperature DOUBLE, humidity DOUBLE, pressure DOUBLE,
  status STRING, location STRING
)
STORED AS PARQUET
LOCATION 's3://<AP_ALIAS>/sensor-data/'
TBLPROPERTIES ('parquet.compression'='SNAPPY');
```

### 3. 最初のクエリ実行

```sql
SELECT COUNT(*) AS total_rows FROM fsxn_poc.sensor_data;
-- 期待値: 10000
```

### 4. 集計クエリ

```sql
SELECT status, COUNT(*) as count, ROUND(AVG(temperature),2) as avg_temp
FROM fsxn_poc.sensor_data GROUP BY status ORDER BY count DESC;
```

### 5. (オプション) CTAS 書き戻し

```sql
CREATE TABLE fsxn_poc.sensor_summary
WITH (external_location = 's3://<AP_ALIAS>/gold/sensor-summary/', format = 'PARQUET')
AS SELECT device_id, status, COUNT(*) as readings, ROUND(AVG(temperature),2) as avg_temp
FROM fsxn_poc.sensor_data GROUP BY device_id, status;
```

## このモジュールの後

- **ガバナンス追加**: [モジュール 07 (Lake Formation)](../07-governance/) で同じテーブルにカラム/行/タグ権限を追加
- **AI デモ実行**: Glue テーブルは Redshift Spectrum からもアクセス可能（同じカタログ）
- **詳細ドキュメント**: [ブログ Part 1](https://dev.to/aws-builders/query-nas-data-in-place-with-athena-and-fsx-for-ontap-s3-access-points-3lhh)

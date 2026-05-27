🌐 [English](README.md) | **日本語**

# モジュール 07: エンタープライズガバナンス (Lake Formation)

## 概要

AWS Lake Formation を使用して FSx for ONTAP S3 AP データに細粒度アクセス制御を追加。同じガバナンスが Athena、Redshift Spectrum、EMR に同時適用。

```
Lake Formation (テーブル/カラム/行/タグ権限)
        │
        ├── Athena クエリ → ガバナンス適用
        ├── Redshift Spectrum クエリ → ガバナンス適用
        └── EMR Spark 読み取り → ガバナンス適用
        
全て同じ Glue Catalog + Lake Formation 権限を共有
```

## 前提条件

- FSx S3 AP を指す Glue Catalog テーブル（モジュール 02 から）
- Lake Formation 管理者権限を持つ IAM ユーザー/ロール

## 手順

### 1. Lake Formation 管理者設定

```bash
aws lakeformation put-data-lake-settings \
  --data-lake-settings '{
    "DataLakeAdmins": [{"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT>:user/<ADMIN>"}]
  }'
```

### 2. テーブルレベル権限付与

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT>:role/<ANALYST_ROLE>"}' \
  --resource '{"Table": {"DatabaseName": "fsxn_poc", "Name": "sensor_data"}}' \
  --permissions '["SELECT", "DESCRIBE"]'
```

### 3. カラムレベル権限（特定カラムを制限）

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT>:role/<RESTRICTED_ROLE>"}' \
  --resource '{"TableWithColumns": {"DatabaseName": "fsxn_poc", "Name": "sensor_data", "ColumnNames": ["device_id", "temperature", "status"]}}' \
  --permissions '["SELECT"]'
```

### 4. 行フィルタ (Data Cells Filter)

```bash
aws lakeformation create-data-cells-filter \
  --table-data '{
    "TableCatalogId": "<ACCOUNT>",
    "DatabaseName": "fsxn_poc",
    "TableName": "sensor_data",
    "Name": "normal_only",
    "RowFilter": {"FilterExpression": "status = '\''normal'\''"},
    "ColumnNames": ["device_id", "timestamp", "temperature", "status"]
  }'
```

### 5. LF-Tag（タグベースアクセス制御）

```bash
# タグ作成
aws lakeformation create-lf-tag --tag-key sensitivity --tag-values '["public","internal","confidential"]'

# テーブルにタグ割り当て
aws lakeformation add-lf-tags-to-resource \
  --resource '{"Table": {"DatabaseName": "fsxn_poc", "Name": "sensor_data"}}' \
  --lf-tags '[{"TagKey": "sensitivity", "TagValues": ["internal"]}]'

# タグによるアクセス付与
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT>:role/<ROLE>"}' \
  --resource '{"LFTagPolicy": {"ResourceType": "TABLE", "Expression": [{"TagKey": "sensitivity", "TagValues": ["public", "internal"]}]}}' \
  --permissions '["SELECT", "DESCRIBE"]'
```

## 検証

```sql
-- 制限ロールとして、許可されたカラム/行のみ返されるべき
SELECT device_id, temperature, status FROM fsxn_poc.sensor_data LIMIT 10;

-- 拒否されたカラムはエラーになるべき
SELECT humidity FROM fsxn_poc.sensor_data;  -- エラー: カラムを解決できない
```

## 重要な知見

Lake Formation 権限は **Athena と Redshift Spectrum の両方に同時適用**。一度設定すれば全エンジンでガバナンス。

## コスト

Lake Formation 自体は**無料** — 基盤サービス（Athena、Glue Catalog）以外の追加料金なし。

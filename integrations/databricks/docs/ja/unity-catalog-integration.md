# Unity Catalog 統合詳細

## 概要

Databricks Unity Catalog は、データガバナンスとアクセス制御の統一レイヤーです。
FSx for ONTAP を External Location として登録することで、Unity Catalog のガバナンス機能を
FSx for ONTAP 上のデータに適用できます。

## Unity Catalog オブジェクト階層

```
Metastore
└── Catalog: fsxn_lakehouse
    ├── Schema: bronze
    │   ├── Table: transactions (External, Parquet)
    │   ├── Table: customers_csv (External, CSV)
    │   └── Table: iot_sensors (External, Parquet, Partitioned)
    ├── Schema: silver
    │   ├── Table: orders (Managed, Delta Lake)
    │   └── Table: products (Managed, Iceberg)
    ├── Schema: gold
    │   └── Table: daily_revenue (Managed, Delta Lake)
    └── Schema: features
        └── Table: customer_features (Managed, Delta Lake)
```

## Storage Credential の仕組み

```
Databricks Control Plane
    │
    │ AssumeRole (with ExternalId)
    ▼
IAM Role: fsxn-lakehouse-databricks-s3-role
    │
    │ S3 API calls
    ▼
S3 Access Point: fsxn-databricks-ap
    │
    │ VPC-scoped access
    ▼
FSx for NetApp ONTAP Volume
```

### セキュリティレイヤー

1. **Unity Catalog ACL**: ユーザー/グループ単位のテーブルアクセス制御
2. **IAM Role**: AWS レベルの認証（External ID で保護）
3. **S3 AP Policy**: アクセスポイントレベルのポリシー
4. **VPC Restriction**: ネットワークレベルの制限
5. **ONTAP Export Policy**: ボリュームレベルのアクセス制御

## External Table vs Managed Table

### External Table（パターン A: 読み取り専用）

```sql
CREATE TABLE fsxn_lakehouse.bronze.raw_data
USING PARQUET
LOCATION 's3://<s3ap-alias>/bronze/raw_data/'
```

- データは FSx for ONTAP 上に存在（Databricks が管理しない）
- DROP TABLE してもデータは削除されない
- NFS/SMB 経由で同じデータにアクセス可能
- 既存データの分析に最適

### Managed Table（パターン B: 読み書き）

```sql
CREATE TABLE fsxn_lakehouse.silver.processed_data
USING DELTA
LOCATION 's3://<s3ap-alias>/silver/processed_data/'
```

- Databricks がデータライフサイクルを管理
- Delta Lake / Iceberg フォーマット
- ACID トランザクション対応
- Time Travel + ONTAP Snapshot の組み合わせ

## データアクセスパターン

### パターン 1: SQL クエリ

```sql
-- Unity Catalog 経由でクエリ
SELECT * FROM fsxn_lakehouse.bronze.transactions
WHERE transaction_date >= '2024-01-01';
```

### パターン 2: DataFrame API

```python
# PySpark DataFrame
df = spark.table("fsxn_lakehouse.bronze.transactions")
df.filter(df.amount > 1000).show()
```

### パターン 3: 直接パスアクセス

```python
# S3 AP 経由で直接読み取り
df = spark.read.parquet("s3://<s3ap-alias>/bronze/transactions/")
```

## クラスタ設定

### Spark 設定（S3 AP アクセス用）

```
spark.hadoop.fs.s3a.endpoint = s3.<YOUR_REGION>.amazonaws.com
spark.hadoop.fs.s3a.path.style.access = true
```

### クラスタポリシー

Terraform で作成されるクラスタポリシーにより、
FSx for ONTAP アクセスに必要な設定が自動的に適用されます。

## ガバナンス機能

### データリネージ

Unity Catalog は FSx for ONTAP 上のテーブル間のリネージを自動追跡:

```
bronze.raw_data → (ETL) → silver.cleaned_data → (Aggregate) → gold.summary
```

### 監査ログ

すべてのアクセスが Unity Catalog の監査ログに記録:
- 誰が、いつ、どのテーブルにアクセスしたか
- クエリの実行履歴
- スキーマ変更の履歴

### Row-Level Security

```sql
-- 行レベルセキュリティ（Unity Catalog）
CREATE FUNCTION fsxn_lakehouse.bronze.region_filter(region STRING)
RETURN IF(IS_ACCOUNT_GROUP_MEMBER('japan_team'), true, region = 'global');

ALTER TABLE fsxn_lakehouse.bronze.transactions
SET ROW FILTER fsxn_lakehouse.bronze.region_filter ON (region);
```

## パフォーマンス最適化

### 推奨設定

| 設定 | 値 | 理由 |
|------|-----|------|
| ファイルサイズ | 128MB-256MB | FSx for ONTAP の最適 I/O サイズ |
| パーティション | 日付ベース | FabricPool 階層化と相性良好 |
| 圧縮 | ZSTD | 高圧縮率 + ONTAP 圧縮と補完 |
| Delta OPTIMIZE | 週次 | 小ファイル統合 |

### FSx for ONTAP スループット考慮

- FSx for ONTAP のスループットキャパシティに応じてクラスタサイズを調整
- 大規模クエリは並列度を制限（`spark.sql.shuffle.partitions`）
- キャッシュ活用で FSx for ONTAP への読み取り回数を削減

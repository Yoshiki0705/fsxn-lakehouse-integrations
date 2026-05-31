# Iceberg メタデータカタログ — PoC ガイド

🌐 日本語 | [English](poc-guide.md)

## 概要

本ガイドは、Iceberg メタデータカタログの PoC デプロイを S3 Tables 作成から Athena クエリ検証まで一通り実施する手順書です。2026-05-31 の実際のデプロイ結果に基づいています。

**所要時間**: 約1時間  
**コスト**: < $1 (S3 Tables ストレージ + Athena クエリ)  
**前提条件**: FSx for ONTAP + S3 Access Point 設定済み

---

## Step 1: S3 Tables テーブルバケット作成 (2分)

```bash
# テーブルバケット作成
aws s3tables create-table-bucket \
  --name fsxn-metadata-catalog \
  --region ap-northeast-1

# 期待される出力:
# {
#     "arn": "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog"
# }
```

### Namespace 作成

```bash
aws s3tables create-namespace \
  --table-bucket-arn "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog" \
  --namespace metadata \
  --region ap-northeast-1
```

### Iceberg テーブル作成（PyIceberg でスキーマ定義）

```bash
pip install boto3 pyarrow 'pyiceberg[s3tables]'
```

```python
from pyiceberg.catalog import load_catalog
from pyiceberg.schema import Schema
from pyiceberg.types import *
from pyiceberg.partitioning import PartitionSpec, PartitionField
from pyiceberg.transforms import IdentityTransform

catalog = load_catalog('s3tables', **{
    'type': 'rest',
    'uri': 'https://s3tables.ap-northeast-1.amazonaws.com/iceberg',
    'warehouse': 'arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog',
    'rest.sigv4-enabled': 'true',
    'rest.signing-region': 'ap-northeast-1',
    'rest.signing-name': 's3tables',
})

schema = Schema(
    NestedField(1, 'file_id', StringType(), required=True),
    NestedField(2, 'file_path', StringType(), required=True),
    NestedField(3, 'file_name', StringType(), required=True),
    NestedField(4, 'file_type', StringType(), required=False),
    NestedField(5, 'file_size', LongType(), required=False),
    NestedField(6, 'created_at', TimestamptzType(), required=False),
    NestedField(7, 'modified_at', TimestamptzType(), required=False),
    # ... (完全なスキーマは scripts/initial-metadata-scan.py を参照)
    NestedField(19, 'enrichment_status', StringType(), required=False),
    NestedField(21, 'is_deleted', BooleanType(), required=True),
)

table = catalog.create_table(
    identifier='metadata.unstructured_files',
    schema=schema,
    partition_spec=PartitionSpec(
        PartitionField(source_id=4, field_id=1000,
                       transform=IdentityTransform(), name='file_type_partition')
    ),
)
print(f'✅ テーブル作成完了: {table.name()}')
```

> **注意**: `aws s3tables create-table --format ICEBERG` はスキーマなしの空テーブルを作成します。PyIceberg の `create_table()` でスキーマ定義付きテーブルを作成してください。

---

## Step 2: 初期メタデータスキャン実行 (30秒)

```bash
python scripts/initial-metadata-scan.py \
  --access-point-arn "<YOUR-AP-ALIAS-ext-s3alias>" \
  --table-bucket-arn "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog" \
  --max-files 1000
```

### 期待される出力

```
============================================================
FSx for ONTAP → Iceberg Metadata Catalog: Initial Scan
============================================================
  Access Point: verification-tes-...-ext-s3alias
  Max files:    1000
  Region:       ap-northeast-1
============================================================

[1/3] Listing objects from FSx S3 Access Point...
  Found 38 objects
[2/3] Building metadata records...
  Built 38 metadata records (skipped 0 directory markers)

  Sample record:
    file_id:   ce9b8af6-f50a-56ab-9e58-2de973d4f425
    file_name: athena-s3cp-test.txt
    file_type: text/plain
    file_size: 24 bytes
    enrichment_status: pending

[3/3] Writing to Iceberg metadata table...
  ✅ Wrote 38 records to metadata.unstructured_files

============================================================
  Total files scanned:    38
  Metadata records:       38
  Enrichment pending:     38
============================================================
```

---

## Step 3: Glue フェデレーテッドカタログ登録 (1分)

S3 Tables を Athena からクエリするには Glue フェデレーテッドカタログの登録が必要:

```bash
aws glue create-catalog \
  --name "s3tablescatalog" \
  --catalog-input '{
    "FederatedCatalog": {
      "Identifier": "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/*",
      "ConnectionName": "aws:s3tables"
    },
    "CreateDatabaseDefaultPermissions": [],
    "CreateTableDefaultPermissions": []
  }' \
  --region ap-northeast-1
```

> **重要**: カタログ名 `s3tablescatalog` は S3 Tables フェデレーション用の予約名です。この名前を正確に使用してください。

---

## Step 4: Lake Formation 権限付与 (1分)

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT_ID>:user/<YOUR_USER>"}' \
  --resource '{"Table": {"CatalogId": "s3tablescatalog/fsxn-metadata-catalog", "DatabaseName": "metadata", "Name": "unstructured_files"}}' \
  --permissions '["SELECT", "DESCRIBE"]' \
  --region ap-northeast-1
```

> **注意**: この手順なしでは Athena が `COLUMN_NOT_FOUND: Relation contains no accessible columns` を返します。これはスキーマの問題ではなく Lake Formation の権限問題です。

---

## Step 5: Athena でクエリ実行 (即時)

### クエリ構文

```sql
-- S3 Tables カタログ構文:
-- "s3tablescatalog/<テーブルバケット名>"."<namespace>"."<テーブル名>"

SELECT file_name, file_type, file_size, enrichment_status
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
LIMIT 10;
```

### 検証済みクエリ結果 (2026-05-31)

**クエリ 1: 基本メタデータ取得** (799ms, 4.6KB スキャン)

| file_name | file_type | file_size | enrichment_status | source_volume |
|-----------|-----------|-----------|-------------------|---------------|
| sensor_data_large.parquet | application/x-parquet | 108,002,572 | pending | benchmark |
| sensor_data_large.parquet | application/x-parquet | 108,002,572 | pending | bronze |
| sensor_data.parquet | application/x-parquet | 250,880 | pending | sensor-data |
| write-test.parquet | application/x-parquet | 250,880 | pending | neg-test |
| sensor_data.parquet | application/x-parquet | 250,880 | pending | bronze |

**クエリ 2: ファイルタイプ分布** (GROUP BY 集計)

| file_type | file_count | total_bytes |
|-----------|-----------|-------------|
| application/x-parquet | 26 | 217,777,490 |
| text/csv | 2 | 58,143 |
| image/png | 3 | 27,898 |
| application/json | 2 | 3,471 |
| application/octet-stream | 4 | 1,455 |
| text/plain | 1 | 24 |

### その他のクエリ例

```sql
-- ソースボリューム別ファイル分布
SELECT source_volume, COUNT(*) AS count, SUM(file_size) AS total_bytes
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE is_deleted = false
GROUP BY source_volume
ORDER BY total_bytes DESC;

-- 画像ファイル検索 (AI Vision 処理候補)
SELECT file_name, file_path, file_size
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE file_type LIKE 'image/%'
  AND is_deleted = false;

-- AI エンリッチメント待ちファイル数 (Phase 3 入力)
SELECT COUNT(*) AS pending_count
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
WHERE enrichment_status = 'pending'
  AND is_deleted = false;
```

---

## 性能特性 (実測値)

| メトリクス | 値 | 備考 |
|----------|---|------|
| テーブル作成 | < 1秒 | PyIceberg REST API |
| 初期スキャン (38ファイル) | < 30秒 | ListObjectsV2 + PyIceberg append |
| Athena クエリレイテンシ | 799-1351 ms | 全テストクエリでサブ2秒 |
| クエリあたりスキャンデータ | 1-5 KB | メタデータのみ（非常に効率的） |
| Athena エンジン | Version 3 | Iceberg ネイティブサポート |

---

## トラブルシューティング

| 症状 | 原因 | 解決策 |
|------|------|--------|
| `CATALOG_NOT_FOUND: Catalog 's3tablescatalog' does not exist` | Glue フェデレーテッドカタログ未登録 | Step 3 (create-catalog) を実行 |
| `COLUMN_NOT_FOUND: Relation contains no accessible columns` | Lake Formation 権限なし | Step 4 (grant-permissions) を実行 |
| `invalid_metadata_location` (PyIceberg 書き込み時) | CLI でスキーマなしテーブル作成 | 削除して PyIceberg `create_table()` で再作成 |
| `Mismatch in fields: value: required string vs optional string` | PyArrow map 型の value が nullable | `pa.field('value', pa.string(), nullable=False)` を使用 |
| `ModuleNotFoundError: pyiceberg` | PyIceberg 未インストール | `pip install 'pyiceberg[s3tables]'` |

---

## クリーンアップ

```bash
# テーブル削除
aws s3tables delete-table \
  --table-bucket-arn "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog" \
  --namespace metadata --name unstructured_files --region ap-northeast-1

# Namespace 削除
aws s3tables delete-namespace \
  --table-bucket-arn "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog" \
  --namespace metadata --region ap-northeast-1

# テーブルバケット削除
aws s3tables delete-table-bucket \
  --table-bucket-arn "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog" \
  --region ap-northeast-1

# Glue カタログ削除 (オプション — 全 S3 Tables で共有)
aws glue delete-catalog --name s3tablescatalog --region ap-northeast-1
```

---

## PoC 後の次のステップ

1. **Phase 2**: FPolicy → SQS → Lambda パイプラインでリアルタイムメタデータ同期
2. **Phase 3**: AI エンリッチメント有効化 (Bedrock 分類 + embedding 生成)
3. **Phase 4**: クロスプラットフォームアクセス設定 (Databricks, Snowflake)
4. **Phase 5**: ベクトル類似検索追加 (OpenSearch Serverless)
5. **Phase 6**: PII 含有ファイルの匿名化パイプライン実装

詳細な設計は [アーキテクチャドキュメント](../../docs/ja/iceberg-metadata-catalog.md) を参照。

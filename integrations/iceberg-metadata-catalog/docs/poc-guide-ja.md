# Iceberg メタデータカタログ — PoC ガイド

🌐 日本語 | [English](poc-guide.md)

## 概要

本ガイドは、Iceberg メタデータカタログの PoC デプロイを S3 Tables 作成から Athena クエリ検証まで一通り実施する手順書です。2026-05-31 の実際のデプロイ結果に基づいています。

**所要時間**: 約1時間  
**コスト**: < $1 (S3 Tables ストレージ + Athena クエリ)  
**前提条件**: FSx for ONTAP + S3 Access Point 設定済み

### 実施方法の選択

| 方法 | 対象者 | 所要時間 | 難易度 |
|------|--------|---------|--------|
| **方法 A: AWS コンソール (GUI)** | データアナリスト、非インフラエンジニア | 1時間 | ★☆☆ |
| **方法 B: CloudFormation** | インフラ管理者、再現性重視 | 30分 | ★★☆ |
| **方法 C: CLI + スクリプト** | 開発者、自動化志向 | 20分 | ★★★ |

---

## 方法 A: AWS マネジメントコンソール (GUI) での実施

### A-1: S3 Tables テーブルバケット作成

1. AWS マネジメントコンソールにログイン
2. **S3** サービスを開く
3. 左メニューから **「テーブルバケット」** を選択
4. **「テーブルバケットを作成」** をクリック
5. 以下を入力:
   - バケット名: `fsxn-metadata-catalog`
   - リージョン: アジアパシフィック (東京) `ap-northeast-1`
6. **「テーブルバケットを作成」** をクリック

```
┌─────────────────────────────────────────────────────────────┐
│ Amazon S3 > テーブルバケット > テーブルバケットを作成         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  テーブルバケット名: [fsxn-metadata-catalog          ]      │
│                                                             │
│  AWS リージョン:    [アジアパシフィック (東京) ▼     ]      │
│                                                             │
│                    [テーブルバケットを作成]                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### A-2: Athena でクエリ実行

> **前提**: Step A-1 完了後、CLI で Namespace/Table 作成と初期スキャンを実行済み（方法 C の Step 1-2 を参照）。GUI のみでのテーブル作成は現時点で未サポート（PyIceberg が必要）。

1. **Athena** サービスを開く
2. 左メニューから **「クエリエディタ」** を選択
3. ワークグループ: `primary` または `fsxn-metadata-catalog` を選択
4. **データソース**: `AwsDataCatalog` を選択
5. 以下のクエリを入力して **「実行」** をクリック:

```sql
SELECT file_name, file_type, file_size, enrichment_status
FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
LIMIT 10;
```

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Amazon Athena > クエリエディタ                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ ワークグループ: [primary ▼]  データソース: [AwsDataCatalog ▼]           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1 │ SELECT file_name, file_type, file_size, enrichment_status          │
│  2 │ FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"            │
│  3 │      ."unstructured_files"                                         │
│  4 │ LIMIT 10;                                                          │
│                                                                         │
│                              [▶ 実行]                                   │
├─────────────────────────────────────────────────────────────────────────┤
│ 結果 (10 行, 実行時間: 1.35 秒, スキャンデータ: 1.19 KB)               │
├──────────────────────────────┬──────────────────────┬──────────┬────────┤
│ file_name                    │ file_type            │file_size │status  │
├──────────────────────────────┼──────────────────────┼──────────┼────────┤
│ sensor_data_large.parquet    │ application/x-parquet│108002572 │pending │
│ sensor_data.parquet          │ application/x-parquet│  250880  │pending │
│ customers.csv                │ text/csv             │   58132  │pending │
│ invoice_sample.png           │ image/png            │   11338  │pending │
│ product_inspection.png       │ image/png            │    7180  │pending │
└──────────────────────────────┴──────────────────────┴──────────┴────────┘
```

### A-3: Lake Formation 権限設定 (GUI)

1. **Lake Formation** サービスを開く
2. 左メニューから **「データ権限」** を選択
3. **「付与」** をクリック
4. 以下を設定:
   - プリンシパル: IAM ユーザーまたはロールを選択
   - カタログ: `s3tablescatalog/fsxn-metadata-catalog`
   - データベース: `metadata`
   - テーブル: `unstructured_files`
   - テーブル権限: ✅ Select, ✅ Describe
5. **「付与」** をクリック

```
┌─────────────────────────────────────────────────────────────────────────┐
│ AWS Lake Formation > データ権限 > 付与                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  プリンシパル                                                           │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ IAM ユーザーとロール: [yoshiki0705 ▼]                           │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  LF タグまたはカタログリソース                                          │
│  ○ LF タグを使用した名前付きデータカタログリソース                      │
│  ● 名前付きデータカタログリソース                                       │
│                                                                         │
│  カタログ:    [s3tablescatalog/fsxn-metadata-catalog ▼]                 │
│  データベース: [metadata ▼]                                             │
│  テーブル:    [unstructured_files ▼]                                    │
│                                                                         │
│  テーブル権限                                                           │
│  ☑ Select    ☑ Describe    ☐ Alter    ☐ Drop    ☐ Insert               │
│                                                                         │
│                              [付与]                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 方法 B: CloudFormation テンプレートでの実施

### B-1: CloudFormation スタックのデプロイ

1. **CloudFormation** サービスを開く
2. **「スタックの作成」** > **「新しいリソースを使用」** をクリック
3. テンプレートソース: **「テンプレートファイルのアップロード」** を選択
4. ファイル: `cloudformation/s3-tables-setup.yaml` をアップロード
5. パラメータを入力:

| パラメータ | 値 | 説明 |
|----------|---|------|
| TableBucketName | `fsxn-metadata-catalog` | テーブルバケット名 |
| AthenaResultsBucket | `fsxn-athena-verification-results-ap-northeast-1` | Athena 結果出力先 |
| QueryUserArn | `arn:aws:iam::<ACCOUNT_ID>:user/yoshiki0705` | クエリ実行ユーザー |

6. **「次へ」** → **「次へ」** → IAM リソース作成の確認にチェック → **「送信」**

```
┌─────────────────────────────────────────────────────────────────────────┐
│ CloudFormation > スタックの作成                                        　  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  テンプレートの指定                                                  　    │
│  ● テンプレートファイルのアップロード                               　　　     │
│    [s3-tables-setup.yaml]  [ファイルを選択]                               │
│                                                                         │
│  スタック名: [fsxn-metadata-catalog-stack]                               │
│                                                                         │
│  パラメータ:                                                             │
│  ┌───────────────────────────────────────────────────────────────┐     │
│  │ テーブルバケット名:        [fsxn-metadata-catalog        ]       │      │
│  │ Athena 結果出力先バケット: [fsxn-athena-verification-... ]       │      │
│  │ クエリ実行ユーザー ARN:   [arn:aws:iam::178625...        ]       │      │
│  └───────────────────────────────────────────────────────────────┘      │
│                                                                         │
│  ☑ AWS CloudFormation によって IAM リソースが作成される場合があること           │
│    を承認します。                                                          │
│                                                                         │
│                              [送信]                                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### B-2: スタック作成後の手順

CloudFormation スタック作成後、以下の追加手順が必要です:

1. **Glue フェデレーテッドカタログ登録** (CLI — 現時点で GUI 未対応):
```bash
aws glue create-catalog --name "s3tablescatalog" --catalog-input '{
  "FederatedCatalog": {
    "Identifier": "arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/*",
    "ConnectionName": "aws:s3tables"
  },
  "CreateDatabaseDefaultPermissions": [],
  "CreateTableDefaultPermissions": []
}' --region ap-northeast-1
```

2. **Iceberg テーブル作成** (PyIceberg — 方法 C の Step 1 を参照)

3. **初期メタデータスキャン** (方法 C の Step 2 を参照)

4. **Lake Formation 権限付与** (方法 A の A-3 を GUI で実施可能)

---

## 方法 C: CLI + スクリプトでの実施

> 開発者・自動化志向の方向け。最も高速（約20分）。

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

### 本番推奨設定（テスト結果から得られた知見）

以下の設定は Phase 1+2 のテスト結果から導出された本番環境向けの推奨値です:

```yaml
# Lambda 設定
reserved_concurrency: 1       # Iceberg commit conflict 回避（最重要）
memory_size: 512              # PyIceberg + PyArrow に必要
timeout: 120                  # S3 Tables 書き込みに十分な時間

# SQS 設定
batch_size: 10                # 1回の Lambda で10メッセージ処理
max_batching_window: 30       # 30秒間メッセージを蓄積してからバッチ処理
visibility_timeout: 300       # Lambda timeout の5倍
max_receive_count: 3          # DLQ 送信前のリトライ回数

# Athena クエリ（重複排除付き — 本番では必ず使用）
# Iceberg append-only のため、同一 file_id に複数レコードが存在する場合がある
# ROW_NUMBER() で最新レコードのみ取得
SELECT * FROM (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY file_id ORDER BY modified_at DESC) as rn
  FROM "s3tablescatalog/fsxn-metadata-catalog"."metadata"."unstructured_files"
) WHERE rn = 1 AND is_deleted = false;
```

**重要な制約**:
| 制約 | 影響 | 回避策 |
|------|------|--------|
| Lambda 並行実行で commit conflict | バースト時に一部失敗 → リトライ | `reserved_concurrency: 1` |
| append-only で重複レコード | クエリ結果に重複 | `ROW_NUMBER()` dedup |
| Lake Formation 列レベル制御が未サポート | フェデレーテッドカタログでは列制御不可 | Athena View で列フィルタ |

### 簡易 Runbook: 障害対応手順

#### DLQ メッセージ確認 → リドライブ

```bash
# 1. DLQ メッセージ数確認
aws sqs get-queue-attributes \
  --queue-url "https://sqs.ap-northeast-1.amazonaws.com/<ACCOUNT_ID>/fsxn-metadata-sync-dlq" \
  --attribute-names All \
  --query 'Attributes.ApproximateNumberOfMessages' \
  --region ap-northeast-1

# 2. DLQ メッセージ内容確認（原因特定）
aws sqs receive-message \
  --queue-url "https://sqs.ap-northeast-1.amazonaws.com/<ACCOUNT_ID>/fsxn-metadata-sync-dlq" \
  --max-number-of-messages 5 \
  --region ap-northeast-1

# 3. 原因修正後、DLQ → メインキューにリドライブ
aws sqs start-message-move-task \
  --source-arn "arn:aws:sqs:ap-northeast-1:<ACCOUNT_ID>:fsxn-metadata-sync-dlq" \
  --destination-arn "arn:aws:sqs:ap-northeast-1:<ACCOUNT_ID>:fsxn-metadata-sync" \
  --region ap-northeast-1
```

#### Lambda エラー確認

```bash
# 最新のエラーログ確認
aws logs filter-log-events \
  --log-group-name /aws/lambda/fsxn-metadata-sync \
  --filter-pattern "ERROR" \
  --start-time $(date -v-1H +%s000) \
  --region ap-northeast-1 \
  --query 'events[*].message' --output text
```

#### メタデータ整合性確認（リコンシリエーション）

```bash
# FSx for ONTAP S3 AP のファイル数とメタデータテーブルのレコード数を比較
# 差分がある場合は initial-metadata-scan.py を再実行
python scripts/initial-metadata-scan.py \
  --access-point-arn "<AP_ALIAS>" \
  --table-bucket-arn "<TABLE_BUCKET_ARN>" \
  --max-files 10000
```

---

1. **Phase 2**: FPolicy → SQS → Lambda パイプラインでリアルタイムメタデータ同期
2. **Phase 3**: AI エンリッチメント有効化 (Bedrock 分類 + embedding 生成)
3. **Phase 4**: クロスプラットフォームアクセス設定 (Databricks, Snowflake)
4. **Phase 5**: ベクトル類似検索追加 (OpenSearch Serverless)
5. **Phase 6**: PII 含有ファイルの匿名化パイプライン実装

詳細な設計は [アーキテクチャドキュメント](../../docs/ja/iceberg-metadata-catalog.md) を参照。

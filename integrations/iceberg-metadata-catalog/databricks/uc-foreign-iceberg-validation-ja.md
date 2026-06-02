# UC Foreign Iceberg 検証計画

🌐 日本語 | [English](uc-foreign-iceberg-validation.md)

## 目的

Unity Catalog Foreign Iceberg が AWS Glue Iceberg REST エンドポイント経由で S3 Tables メタデータにアクセスできるかを検証し、DataSync やフォーマット変換なしでガバナンス付きメタデータアクセスを実現する。

## 背景

- Databricks [Foreign Iceberg が GA](https://www.databricks.com/blog/unity-catalog-and-next-era-apache-icebergtm) (2026年6月)
- AWS が [Glue Iceberg REST 経由で Databricks から S3 Iceberg テーブルにアクセスするガイダンス](https://aws.amazon.com/blogs/big-data/access-amazon-s3-iceberg-tables-from-databricks-using-aws-glue-iceberg-rest-catalog-in-amazon-sagemaker-lakehouse) を公開
- Databricks の [カタログフェデレーションが AWS Glue をサポート](https://docs.databricks.com/aws/en/query-federation/hms-federation-glue)

## 既知の制約（Databricks ドキュメントより）

| 制約 | 影響 | ソース |
|---|---|---|
| Foreign Iceberg tables では credential vending 非対応 | 外部ストレージ credentials を別途設定する必要あり | [docs](https://docs.databricks.com/aws/external-access/iceberg) |
| Foreign Iceberg tables は自動リフレッシュされない | 最新スナップショットを見るには `REFRESH FOREIGN TABLE` が必要 | [docs](https://docs.databricks.com/aws/external-access/iceberg) |
| 読み取り専用アクセス | Databricks から Foreign Iceberg tables への書き込み不可 | [docs](https://docs.databricks.com/aws/iceberg/) |

## 検証ステップ

### B-4: S3 Tables Direct REST 経由の UC Foreign Iceberg

```sql
-- ステップ 1: S3 Tables アクセス用サービス credential 作成
CREATE SERVICE CREDENTIAL s3tables_cred
WITH (
  -- s3tables:* 権限を持つ IAM ロール
);

-- ステップ 2: S3 Tables REST エンドポイントへの接続作成
CREATE CONNECTION s3tables_rest TYPE iceberg_rest
OPTIONS (
  uri = 'https://s3tables.ap-northeast-1.amazonaws.com/iceberg',
  warehouse = 'arn:aws:s3tables:ap-northeast-1:<ACCOUNT_ID>:bucket/fsxn-metadata-catalog',
  credential_name = 's3tables_cred'
  -- SigV4 署名設定 TBD
);

-- ステップ 3: Foreign catalog 作成
CREATE FOREIGN CATALOG s3tables_metadata
USING CONNECTION s3tables_rest;

-- ステップ 4: クエリ
SELECT * FROM s3tables_metadata.metadata.unstructured_files LIMIT 10;
```

### B-5: Glue Iceberg REST 経由の UC Foreign Iceberg

```sql
-- ステップ 1: Glue アクセス用サービス credential 作成
CREATE SERVICE CREDENTIAL glue_cred
WITH (
  -- glue:* 権限を持つ IAM ロール
);

-- ステップ 2: Glue Iceberg REST エンドポイントへの接続作成
CREATE CONNECTION glue_iceberg_rest TYPE iceberg_rest
OPTIONS (
  uri = 'https://glue.ap-northeast-1.amazonaws.com/iceberg',
  warehouse = '<ACCOUNT_ID>:s3tablescatalog/fsxn-metadata-catalog',
  credential_name = 'glue_cred'
  -- SigV4 署名設定 TBD
);

-- ステップ 3: Foreign catalog 作成
CREATE FOREIGN CATALOG glue_metadata
USING CONNECTION glue_iceberg_rest;

-- ステップ 4: クエリ
SELECT * FROM glue_metadata.metadata.unstructured_files LIMIT 10;
```

## 成功基準

| 基準 | 期待値 |
|---|---|
| Foreign catalog 作成 | エラーなし |
| 名前空間が表示される | `metadata` 名前空間がリスト |
| テーブルが表示される | `unstructured_files` テーブルがリスト |
| SELECT クエリ動作 | ファイルメタデータの行が返される |
| タイムトラベル動作 | `FOR SYSTEM_TIME AS OF` で履歴データ返却 |
| REFRESH FOREIGN TABLE 動作 | リフレッシュ後に最新スナップショットが表示 |
| UC ガバナンス適用 | UC grants がアクセスを制御 |
| UC リネージ記録 | クエリが UC リネージグラフに表示 |

## リフレッシュセマンティクス検証

```sql
-- 1. 現在の状態をクエリ
SELECT COUNT(*) FROM glue_metadata.metadata.unstructured_files;

-- 2. PyIceberg で新レコード追加（Lambda またはローカルから）

-- 3. リフレッシュなしで再クエリ — 古いカウントを期待
SELECT COUNT(*) FROM glue_metadata.metadata.unstructured_files;

-- 4. リフレッシュ実行
REFRESH FOREIGN TABLE glue_metadata.metadata.unstructured_files;

-- 5. 再クエリ — 更新されたカウントを期待
SELECT COUNT(*) FROM glue_metadata.metadata.unstructured_files;
```

### 詳細スナップショット鮮度テスト

```sql
-- append 前の snapshot_id を記録
SELECT snapshot_id FROM glue_metadata.metadata.unstructured_files.history LIMIT 1;

-- AWS 側から PyIceberg で append 後:
-- 1. Databricks でクエリ — 新しいスナップショットが見えるか？
SELECT snapshot_id FROM glue_metadata.metadata.unstructured_files.history LIMIT 1;
-- 期待値: 以前と同じ（自動リフレッシュなし）

-- 2. REFRESH 実行
REFRESH FOREIGN TABLE glue_metadata.metadata.unstructured_files;

-- 3. 再クエリ
SELECT snapshot_id FROM glue_metadata.metadata.unstructured_files.history LIMIT 1;
-- 期待値: 新しい snapshot_id（リフレッシュ後）

-- 4. Athena と比較
-- Athena で同じクエリを実行 — 常に最新スナップショットが表示されるはず
-- Athena（常に最新）と Databricks（リフレッシュ依存）の差分を記録
```

## ステータス

- B-4 (S3 Tables direct REST): Databricks サポートにフォローアップ送信済み (2026-06-01)
- B-5 (Glue Iceberg REST): Databricks サポートにフォローアップ送信済み (2026-06-01)
- サポートからの接続タイプと credential 設定に関するガイダンス待ち

## 参考資料

- [Databricks Foreign Iceberg ドキュメント](https://docs.databricks.com/aws/external-access/iceberg)
- [AWS Glue Iceberg REST → Databricks ブログ](https://aws.amazon.com/blogs/big-data/access-amazon-s3-iceberg-tables-from-databricks-using-aws-glue-iceberg-rest-catalog-in-amazon-sagemaker-lakehouse)
- [Databricks カタログフェデレーション](https://docs.databricks.com/aws/en/query-federation/catalog-federation)
- [AWS Glue → UC フェデレーション](https://docs.aws.amazon.com/lake-formation/latest/dg/catalog-federation-databricks.html)

# Snowflake + FSx for ONTAP S3 Access Point: トラブルシューティングガイド

🌐 日本語 | [English](troubleshooting-guide.md)

> Snowflake と Amazon FSx for ONTAP（S3 Access Point 経由）および AWS Glue Iceberg REST カタログ連携時のよくあるエラーと解決策。
>
> 最終検証日: 2026-06-02 | リージョン: ap-northeast-1

---

## TO_FILE 関連の問題

### エラー: "SQL compilation error: invalid argument for function [TO_FILE]"

**症状:**

```
SQL compilation error: invalid argument for function [TO_FILE]
```

**原因:** ステージ参照が文字列リテラルではなく、SQL 識別子として渡されている。

**修正方法:** ステージパスをシングルクォートで囲む（文字列リテラル構文）。

```sql
-- ❌ 間違い: ステージを識別子として渡す（SQL compilation error が発生）
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'claude-sonnet-4-5',
  'このファイルを説明してください',
  TO_FILE(@DB.SCHEMA.STAGE, 'path/to/file.txt')
);

-- ✅ 正しい: ステージを文字列リテラルとして渡す
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'claude-sonnet-4-5',
  'このファイルを説明してください',
  TO_FILE('@DB.SCHEMA.STAGE', 'path/to/file.txt')
);
```

**ポイント:** `TO_FILE` の第一引数は **文字列リテラル** (`'@...'`) である必要があります。`LIST @stage` や `SELECT ... FROM @stage` で使う識別子（`@...`）とは異なります。

---

### エラー: "Remote file was not found"

**症状:**

```
Remote file was not found. Please check the file path and try again.
```

**原因:** `TO_FILE` で指定したファイルパスがステージ上に存在しない。

**診断手順:**

```sql
-- ステップ 1: ステージ上の全ファイルを一覧表示
LIST @DB.SCHEMA.STAGE;

-- ステップ 2: ファイルパスを確認（大文字小文字区別あり、先頭スラッシュなし）
LIST @DB.SCHEMA.STAGE PATTERN = '.*your-file.*';

-- ステップ 3: ステージ参照のデータベースとスキーマを確認
SHOW STAGES IN SCHEMA DB.SCHEMA;
```

**よくある間違い:**

| 間違い | 例 | 修正 |
|--------|---|------|
| ファイル名の間違い | `'_sample.png'`（存在しない） | `LIST` 出力の正確な名前を使用 |
| 先頭スラッシュ | `'/path/to/file.txt'` | 先頭スラッシュを削除: `'path/to/file.txt'` |
| DB/スキーマの間違い | `'@WRONG_DB.PUBLIC.STAGE'` | `SHOW STAGES` で確認 |
| ステージプレフィックスの重複 | `'@STAGE/folder/file.txt'` が重複 | パスはステージルートからの相対パス |

**動作確認済みの例:**

```sql
-- 1. ファイルの存在を確認
LIST @FSXN_LAKEHOUSE.PUBLIC.FSXN_AP_ARN_TEST_STAGE;
-- 結果: athena-results/athena-s3cp-test.txt

-- 2. LIST 出力の正確なパスを使用
SELECT SNOWFLAKE.CORTEX.COMPLETE(
  'claude-sonnet-4-5',
  'このファイルの内容は何ですか？',
  TO_FILE('@FSXN_LAKEHOUSE.PUBLIC.FSXN_AP_ARN_TEST_STAGE', 'athena-results/athena-s3cp-test.txt')
) AS result;
-- ✅ 成功
```

---

## Iceberg カタログ統合の問題

### エラー: "Failed to retrieve credentials from the Catalog" (004174)

**症状:**

```
004174 (S1009): Failed to retrieve credentials from the Catalog.
Please verify that the catalog supports VENDED_CREDENTIALS and has been configured properly.
```

**原因:** AWS Glue Iceberg REST エンドポイントはクレデンシャル・ベンディングを**実装していません**。Snowflake の `VENDED_CREDENTIALS` 認証タイプでは、カタログの `loadTable` レスポンスに以下が含まれている必要があります:

- `s3.access-key-id`
- `s3.secret-access-key`
- `s3.session-token`

AWS Glue REST は `/credentials` 操作に対して `UnknownOperationException` を返します。これは設定エラーではなく、サービスの制限事項です。

**検証:**

```sql
-- 接続性自体は正常:
SELECT SYSTEM$VERIFY_CATALOG_INTEGRATION('S3TABLES_GLUE_REST_INT');
-- 結果: "Statement executed successfully"

-- しかしテーブル作成は失敗:
CREATE ICEBERG TABLE test_table
  EXTERNAL_VOLUME = 'my_volume'
  CATALOG = 's3tables_glue_rest_int'
  CATALOG_TABLE_NAME = 'metadata';
-- エラー 004174
```

**SYSTEM$VERIFY_CATALOG_INTEGRATION が成功する理由:** このコマンドは Glue エンドポイントへのネットワーク接続性と IAM 認証のみを検証します。クレデンシャル・ベンディング（loadTable でのクレデンシャル取得）はテスト**しません**。

**回避策:**

| アプローチ | 説明 | トレードオフ |
|-----------|------|------------|
| **メタデータ同期** | スケジュールタスクで精選メタデータを Snowflake テーブルに同期 | ゼロコピーではない; 同期パイプラインが必要 |
| **Object Store カタログ** | S3 上の Iceberg メタデータファイルを直接参照 | メタデータパスの手動管理; 自動更新なし |
| **Snowflake Open Catalog (Polaris)** | Snowflake 管理のカタログを使用 | AWS Glue とは別カタログ |
| **AWS サポートの対応待ち** | Glue REST のクレデンシャル・ベンディング対応が将来追加される可能性 | タイムライン不明 |

**推奨パス:** メタデータ同期パターン。詳細は [path-decision-guide.md](path-decision-guide.md) を参照。

---

### エラー: "Insufficient Lake Formation permission(s)" (004139)

**症状:**

```
004139: Insufficient Lake Formation permission(s) on <table_arn>
```

**原因:** Snowflake の IAM ロールに対象テーブルの Lake Formation 権限が付与されていない。

**修正方法:**

1. Snowflake の外部関数ロールに Lake Formation 権限を付与:

```bash
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipal": {"DataLakePrincipalIdentifier": "arn:aws:iam::<ACCOUNT_ID>:role/<snowflake-role>"}}' \
  --resource '{"Table": {"DatabaseName": "<db>", "Name": "<table>", "CatalogId": "<ACCOUNT_ID>"}}' \
  --permissions "SELECT" "DESCRIBE" \
  --region ap-northeast-1
```

2. ロールの IAM ポリシーに `lakeformation:GetDataAccess` を追加:

```json
{
  "Effect": "Allow",
  "Action": [
    "lakeformation:GetDataAccess"
  ],
  "Resource": "*"
}
```

3. S3 Tables フェデレーテッドカタログを使用している場合、カタログが Lake Formation に登録されていることを確認:

```bash
aws glue get-database --name <catalog_database_name> --region ap-northeast-1
```

---

## 診断コマンド

### SYSTEM$VERIFY_CATALOG_INTEGRATION

カタログエンドポイントへのネットワーク接続性と IAM 認証をテストします。

```sql
SELECT SYSTEM$VERIFY_CATALOG_INTEGRATION('<integration_name>');
-- 成功: "Statement executed successfully"
-- 失敗: エラー詳細を返す（ネットワーク、IAM など）
```

**重要:** 成功してもクレデンシャル・ベンディングが動作することは保証しません。カタログエンドポイントへの到達性のみを検証します。

### SYSTEM$LIST_NAMESPACES_FROM_CATALOG

カタログ統合を通じて見えるネームスペースを一覧表示します。

```sql
SELECT SYSTEM$LIST_NAMESPACES_FROM_CATALOG('<integration_name>');
```

### LIST @stage

外部ステージを通じてアクセス可能なファイルを確認します。

```sql
-- 全ファイル一覧
LIST @DB.SCHEMA.STAGE_NAME;

-- パターンでフィルタ
LIST @DB.SCHEMA.STAGE_NAME PATTERN = '.*\.txt';
```

### DESCRIBE CATALOG INTEGRATION

IAM ユーザー ARN や外部 ID（信頼ポリシーに必要）を含む設定詳細を表示します。

```sql
DESCRIBE CATALOG INTEGRATION <integration_name>;
-- 主要フィールド:
-- API_AWS_IAM_USER_ARN: Snowflake 管理の IAM ユーザー
-- API_AWS_EXTERNAL_ID: IAM 信頼ポリシー用の外部 ID
```

### SHOW STAGES

ステージ設定を確認します。

```sql
SHOW STAGES IN SCHEMA DB.SCHEMA;
DESCRIBE STAGE DB.SCHEMA.STAGE_NAME;
```

---

## クイックリファレンス: エラーコード一覧

| エラーコード | メッセージ | セクション |
|------------|---------|---------|
| — | SQL compilation error: invalid argument for function [TO_FILE] | [TO_FILE 構文](#エラー-sql-compilation-error-invalid-argument-for-function-to_file) |
| — | Remote file was not found | [ファイル未検出](#エラー-remote-file-was-not-found) |
| 004174 | Failed to retrieve credentials from the Catalog | [クレデンシャル・ベンディング](#エラー-failed-to-retrieve-credentials-from-the-catalog-004174) |
| 004139 | Insufficient Lake Formation permission(s) | [Lake Formation 権限](#エラー-insufficient-lake-formation-permissions-004139) |

---

## 関連ドキュメント

- [外部ステージ検証（FSx S3 AP）](external-stage-fsx-s3ap-validation.md)
- [Glue REST クレデンシャル・ベンディング検証](glue-rest-vended-credentials-validation.md)
- [統合パス決定ガイド](path-decision-guide.md)
- [Snowflake: TO_FILE 関数](https://docs.snowflake.com/en/sql-reference/functions/to_file)
- [Snowflake: Iceberg REST カタログ統合](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-rest)
- [AWS: Glue Iceberg REST エンドポイント](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-glue-endpoint.html)

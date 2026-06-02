# Snowflake Glue REST + Vended Credentials 検証

🌐 日本語 | [English](glue-rest-vended-credentials-validation.md)

## 目的

S3 Tables アクセスのための vended credentials を使用した AWS Glue Iceberg REST エンドポイントとの Snowflake CATALOG INTEGRATION の検証を文書化する。

## 現在のステータス

| ステップ | 状態 | 備考 |
|---|---|---|
| CATALOG INTEGRATION 作成 | ✅ | `ICEBERG_REST` + `AWS_GLUE` + `VENDED_CREDENTIALS` |
| DESCRIBE CATALOG INTEGRATION | ✅ | 有効な IAM credentials を返す |
| CREATE ICEBERG TABLE | ❌ | "Failed to retrieve credentials from the Catalog" |
| サポートケース対応中 | 🔄 | Snowflake + AWS サポートに連絡済み |

## 設定

### Catalog Integration

```sql
CREATE OR REPLACE CATALOG INTEGRATION s3tables_glue_rest_int
  CATALOG_SOURCE = ICEBERG_REST
  TABLE_FORMAT = ICEBERG
  CATALOG_NAMESPACE = 'metadata'
  REST_CONFIG = (
    CATALOG_URI = 'https://glue.ap-northeast-1.amazonaws.com/iceberg'
    WAREHOUSE = '<ACCOUNT_ID>:s3tablescatalog/fsxn-metadata-catalog'
    CATALOG_API_TYPE = AWS_GLUE
  )
  REST_AUTHENTICATION = (
    TYPE = VENDED_CREDENTIALS
    CATALOG_IAM_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/fsxn-snowflake-verification-role'
  )
  ENABLED = TRUE;
```

## 検証チェックリスト

| 確認項目 | 状態 | エビデンス |
|---|---|---|
| IAM trust policy に Snowflake user ARN を含む | ✅ | Trust policy 更新済み |
| IAM ロールに Glue 権限あり | ✅ | ポリシーアタッチ済み |
| IAM ロールに S3 Tables 権限あり | ✅ | s3tables:* 付与 |
| IAM ロールに Lake Formation 権限あり | ✅ | lakeformation:GetDataAccess |
| Lake Formation AllowFullTableExternalDataAccess = true | ✅ | テスト用に設定 |
| Glue REST エンドポイントが Snowflake に応答 | ✅ | DESCRIBE が credentials を返す |
| Credential vending がストレージ credentials を返す | ❌ | これが失敗ポイント |

## 仮説: 失敗ポイント

**2026-06-01 確認済み**: AWS Glue Iceberg REST エンドポイントは Iceberg REST `/credentials` エンドポイントを実装していません。`POST /v1/.../credentials` を呼び出すと `UnknownOperationException` が返されます。`loadTable` の `X-Iceberg-Access-Delegation: vended-credentials` ヘッダーもレスポンス config にストレージ credentials を返しません。

**Snowflake が期待する credential 形式（サポートにより 2026-06-02 確認）**:
`ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS` の場合、Snowflake は loadTable レスポンスの config に以下を期待:
- `s3.access-key-id`（必須）
- `s3.secret-access-key`（必須）
- `s3.session-token`（必須）
- `s3.session-token-expires-at-ms`（オプション）

Error 004174 はこれらのフィールドがレスポンスに存在しない場合に発生。

これが Snowflake の「Failed to retrieve credentials from the Catalog」エラーの根本原因です:
- Snowflake の `VENDED_CREDENTIALS` モードは REST catalog が短期ストレージ credentials を返すことを期待
- Glue REST は代わりに SigV4 認証を使用 — 呼び出し元が S3 データアクセス用の独自 IAM credentials を持つ必要がある
- これは Snowflake の vended credentials モデルと Glue REST の SigV4 モデル間の根本的な非互換性

**影響**:
1. Snowflake は Glue REST で S3 Tables に対して `VENDED_CREDENTIALS` を使用できない（確認された制限）
2. Trino/Spark は独自の IAM credentials (SigV4) を使用するため Glue REST にアクセス可能
3. Snowflake は vended credentials の代わりに External Volume（独自のストレージ credentials）を使用する必要がある可能性
4. Snowflake と AWS の両サポートに確認された相互運用性ギャップとして報告すべき

**Snowflake サポートによる正式確認 (2026-06-02, Case #01364260)**:
`ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS` の場合、Snowflake は Iceberg REST `loadTable` レスポンスの config マップに標準 Apache Iceberg credential フィールドが含まれることを期待します:
- `s3.access-key-id`（必須）
- `s3.secret-access-key`（必須）
- `s3.session-token`（必須）
- `s3.session-token-expires-at-ms`（任意）

Error 004174 はこれらのフィールドが欠落している場合に発生します。

**Snowflake サポートのエラー進行分析 (2026-06-02)**:
アカウントから確認できるエラー進行:
1. 004139（Lake Formation 権限エラー）→ メタデータアクセスブロック
2. 004174（credential 取得失敗）→ メタデータ解決成功、ストレージ credentials なし

これにより証明: Glue REST 到達可能、カタログとテーブル解決成功、メタデータ認証を超えて進行、しかし利用可能な credential ペイロードを取得できない。

## Snowflake サポートが提案した代替パス

### 1. Object Store Catalog Integration（読み取り専用、credential vending 不要）

Snowflake は External Volume を使用して Iceberg メタデータファイルから直接テーブルを読み取ることができます。REST catalog の credential vending を完全にバイパスします。

```sql
-- Object Store catalog integration を作成
CREATE OR REPLACE CATALOG INTEGRATION iceberg_object_store_int
  CATALOG_SOURCE = OBJECT_STORE
  TABLE_FORMAT = ICEBERG
  ENABLED = TRUE;

-- メタデータファイルを直接指す Iceberg テーブルを作成
CREATE ICEBERG TABLE FSXN_LAKEHOUSE.PUBLIC.s3tables_metadata
  EXTERNAL_VOLUME = 's3tables_metadata_vol'
  CATALOG = 'iceberg_object_store_int'
  METADATA_FILE_PATH = 'metadata/00001-fcb8fb99-20cb-4b72-84bb-012d2c85891c.metadata.json';
```

**制限事項**:
- 読み取り専用アクセス
- メタデータファイルの場所が変わるたびに手動リフレッシュが必要
- 現在のメタデータファイルパスを知る必要あり（コミットごとに変更）

**S3 Tables に対する課題**: S3 Tables 内部バケットのパス形式が Snowflake の External Volume で正しく解決できるか追加調査が必要。

### 2. 解決に向けた次のステップ

| アクション | 担当 | 状態 |
|---|---|---|
| loadTable レスポンス証拠を Snowflake に提供 | 顧客（我々） | ✅ 完了 (2026-06-02) |
| SYSTEM$VERIFY_CATALOG_INTEGRATION 実行 | 顧客（我々） | 未実行 |
| Object Store catalog ワークアラウンドの評価 | 顧客（我々） | 未実行 |
| Glue REST に credential vending が追加される予定か確認 | AWS | オープン (case 178031980800349) |
| Snowflake プロダクトチームのトラッキング | Snowflake | 質問済み (2026-06-02) |

## 参考資料

- [Snowflake: Iceberg 用 Vended credentials](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-vended-credentials)
- [Snowflake: REST catalog integration](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-rest)
- [Snowflake: Credentials vending の仕組み](https://www.snowflake.com/en/engineering-blog/iceberg-catalog-credentials/)
- [AWS: S3 Tables + Glue REST エンドポイント](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-glue-endpoint.html)

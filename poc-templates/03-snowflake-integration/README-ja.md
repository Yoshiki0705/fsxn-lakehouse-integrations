🌐 [English](README.md) | **日本語**

# モジュール 03: Snowflake 統合（External Table + Cortex AI）

## エンドツーエンドフロー（30分）

```
Step 1: Storage Integration 作成 (01-storage-integration.sql)
  ↓
Step 2: IAM trust policy を Snowflake の IAM ユーザー ARN で更新
  ↓
Step 3: Stage + External Table 作成 (02-stage-and-table.sql)
  ↓
Step 4: Cortex AI デモ実行 (03-cortex-ai-demo.sql)
```

## 前提条件

- [ ] FSx for ONTAP と同じ AWS リージョンの Snowflake アカウント（Standard 以上）
- [ ] FSx for ONTAP S3 Access Point（`AVAILABLE` ライフサイクル）
- [ ] S3 AP 権限（GetObject, ListBucket）付き Snowflake 用 IAM ロール
- [ ] FSx for ONTAP 上のサンプルデータ（`sensor-data/sensor_data.parquet`）

## ステップバイステップ

### Step 1: Storage Integration

Snowflake で `01-storage-integration.sql` を実行:

```sql
CREATE OR REPLACE STORAGE INTEGRATION fsxn_poc_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/<ROLE_NAME>'
  STORAGE_ALLOWED_LOCATIONS = ('s3://<AP_ALIAS>/');
```

`DESC INTEGRATION fsxn_poc_integration;` を実行し、以下をメモ:
- `STORAGE_AWS_IAM_USER_ARN` → IAM ロール trust policy に追加
- `STORAGE_AWS_EXTERNAL_ID` → IAM ロール trust policy の condition に追加

### Step 2: IAM Trust Policy 更新

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"AWS": "<Step 1 の STORAGE_AWS_IAM_USER_ARN>"},
    "Action": "sts:AssumeRole",
    "Condition": {"StringEquals": {"sts:ExternalId": "<Step 1 の STORAGE_AWS_EXTERNAL_ID>"}}
  }]
}
```

### Step 3: Stage + External Table 作成

`02-stage-and-table.sql` を実行:

```sql
-- 重要: AWS_ACCESS_POINT_ARN を含める — なしでは SELECT が失敗
CREATE OR REPLACE STAGE fsxn_poc_stage
  STORAGE_INTEGRATION = fsxn_poc_integration
  URL = 's3://<AP_ALIAS>/'
  AWS_ACCESS_POINT_ARN = 'arn:aws:s3:<REGION>:<ACCOUNT_ID>:accesspoint/<AP_NAME>'
  FILE_FORMAT = (TYPE = PARQUET);

-- 検証
LIST @fsxn_poc_stage/sensor-data/;
SELECT $1 FROM @fsxn_poc_stage/sensor-data/sensor_data.parquet LIMIT 3;
```

### Step 4: Cortex AI デモ

`03-cortex-ai-demo.sql` で FSx データ上の AI 関数を実行（ゼロコピー）:
- SUMMARIZE — テキスト要約
- SENTIMENT — 感情スコアリング
- TRANSLATE — 多言語翻訳
- COMPLETE — AI 分析
- PARSE_DOCUMENT — 画像の OCR

## デモガイドとの接続

Steps 1-3 完了後、[AI デモガイド](../../integrations/snowflake/docs/ja/ai-demo-guide.md)の全デモを実行可能。オブジェクト名の対応:

| デモガイドが使用 | PoC テンプレートが作成 | 一致させるには |
|---|---|---|
| `@fsxn_stage` | `@fsxn_poc_stage` | 同じ名前を使用、または `ALTER STAGE RENAME` |
| `fsxn_sensor_ext_table` | `fsxn_poc_sensor_ext` | CREATE EXTERNAL TABLE で同じ名前を使用 |
| `fsxn_verification_integration` | `fsxn_poc_integration` | 同じ名前を使用 |

**ヒント**: デモガイドと完全に一致させるには、全 SQL スクリプトで `fsxn_poc_` を `fsxn_` に置換してから実行。

## このモジュールの後

- **Dynamic Table**: `CREATE DYNAMIC TABLE ... AS SELECT ... FROM fsxn_poc_sensor_ext` で自動エンリッチメント
- **Cortex Search (RAG)**: `COPY INTO` → 内部テーブル → `CREATE CORTEX SEARCH SERVICE`
- **Data Sharing**: `GRANT SELECT ON TABLE fsxn_poc_sensor_ext TO SHARE ...`
- **詳細ドキュメント**: [ブログ Part 3](https://dev.to/aws-builders/snowflake-and-fsx-for-ontap-s3-access-points-from-access-denied-to-working-external-tables-9k8)
- **内部テーブルガイド**: [Internal Table Ingestion Guide](../../integrations/snowflake/docs/ja/internal-table-ingestion-guide.md)

## トラブルシューティング

| 症状 | 原因 | 修正 |
|------|------|------|
| LIST は動作、SELECT が "access denied" | `AWS_ACCESS_POINT_ARN` が未設定 | ステージに ARN パラメータを追加 |
| Integration 作成失敗 | IAM ロール ARN が不正 | ロールの存在と ARN 形式を確認 |
| "Insufficient privileges" | ACCOUNTADMIN/SYSADMIN を使用していない | 適切なロールに切り替え |
| External Table が 0 行返す | ファイルパス不一致 | `LIST @stage/sensor-data/` で確認 |
| Cortex 関数エラー | リージョンでモデル利用不可 | Cross-Region Inference を有効化 |

# Snowflake External Stage と FSx for ONTAP S3 Access Point

🌐 日本語 | [English](external-stage-fsx-s3ap-validation.md)

## 目的

FSx for ONTAP S3 Access Point エイリアスを Snowflake External Stage として使用する検証済み設定を文書化する。

## ステータス: ✅ 検証済み (2026-05-31)

External Stage の作成と LIST/SELECT 操作は FSx for ONTAP S3 Access Point エイリアスで動作。TO_FILE 操作は Engineering 対応中。

## 設定

### Storage Integration

```sql
CREATE OR REPLACE STORAGE INTEGRATION fsxn_s3ap_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<ACCOUNT_ID>:role/fsxn-snowflake-verification-role'
  STORAGE_ALLOWED_LOCATIONS = ('s3://verification-tes-fpg5t76dgh3xchkrudk6yc4jhgzz1apn1b-ext-s3alias/');
```

### 検証済み操作

```sql
-- S3 AP 経由で FSx 上のファイルをリスト
LIST @fsxn_external_stage;
-- ✅ ファイルリストを返す

-- ステージされたファイルから SELECT
SELECT $1, $2 FROM @fsxn_external_stage/path/to/file.csv;
-- ✅ ファイル内容を返す

-- Snowflake テーブルへの COPY INTO
COPY INTO target_table FROM @fsxn_external_stage/path/to/file.csv;
-- ✅ サポートされるファイルフォーマットで動作
```

### 既知の制限: TO_FILE

```sql
-- S3 AP からの COPY FILES (TO_FILE)
COPY FILES INTO @another_stage FROM @fsxn_external_stage;
-- ⚠️ Engineering 対応中 — S3 AP パスではまだ非対応
```

## 重要な注意事項

- この検証では S3 AP **エイリアス**（ARN ではない）を URL に使用
- 標準 Snowflake ドキュメントは `s3://bucket-name/` 形式を前提; S3 AP エイリアスはバケット名の代替として動作
- FSx for ONTAP S3 AP は S3 プロトコル経由で NFS/SMB ボリュームへの読み取りアクセスを提供
- S3 AP に関連付けられたファイルシステムアイデンティティがアクセス可能なファイルを決定
- ap-northeast-1 リージョンで 2026-05-31 にテスト

## 参考資料

- [Snowflake: External stages](https://docs.snowflake.com/en/sql-reference/sql/create-stage)
- [Snowflake: Storage integrations](https://docs.snowflake.com/en/sql-reference/sql/create-storage-integration)
- [AWS: FSx for ONTAP S3 Access Points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-access-points.html)

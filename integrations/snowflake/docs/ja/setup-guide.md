# Snowflake セットアップガイド

## 概要

FSx for NetApp ONTAP を Snowflake の External Stage として設定し、
External Table / Iceberg Table のストレージレイヤーとして使用する手順です。

## 前提条件

- AWS アカウントに FSx for NetApp ONTAP がデプロイ済み
- FSx for ONTAP SVM で S3 プロトコルが有効化済み
- Snowflake アカウント（Enterprise Edition 以上推奨）
- AWS CLI v2 設定済み
- ACCOUNTADMIN ロールへのアクセス

## セットアップフロー

```
Step 1: CloudFormation デプロイ
    ↓
Step 2: Snowflake Storage Integration 作成
    ↓
Step 3: DESCRIBE INTEGRATION で AWS 情報取得
    ↓
Step 4: CloudFormation 更新（信頼ポリシー）
    ↓
Step 5: External Stage 作成
    ↓
Step 6: External Table / Iceberg Table 作成
```

## Step 1: CloudFormation スタックのデプロイ

```bash
aws cloudformation deploy \
  --template-file integrations/snowflake/template.yaml \
  --stack-name fsxn-snowflake-integration \
  --parameter-overrides \
    S3BucketName=svm-lakehouse \
    VpcId=vpc-0123456789abcdef0 \
    SubnetIds=subnet-xxx,subnet-yyy \
  --capabilities CAPABILITY_NAMED_IAM \
  --region <YOUR_REGION>
```

出力値を確認:
```bash
aws cloudformation describe-stacks \
  --stack-name fsxn-snowflake-integration \
  --query 'Stacks[0].Outputs' \
  --output table
```

## Step 2: Storage Integration の作成

`sql/01_storage_integration.sql` を実行します。

```sql
CREATE STORAGE INTEGRATION fsxn_storage_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '<SnowflakeRoleArn>'
  STORAGE_ALLOWED_LOCATIONS = ('s3://<S3AccessPointAlias>/');
```

## Step 3: 信頼ポリシー情報の取得

```sql
DESCRIBE INTEGRATION fsxn_storage_integration;
```

以下の値をメモ:
- `STORAGE_AWS_IAM_USER_ARN` → Snowflake の AWS アカウント ID
- `STORAGE_AWS_EXTERNAL_ID` → External ID

## Step 4: CloudFormation の更新

```bash
aws cloudformation update-stack \
  --stack-name fsxn-snowflake-integration \
  --use-previous-template \
  --parameter-overrides \
    SnowflakeAccountId=<account-id-from-arn> \
    SnowflakeExternalId=<external-id> \
  --capabilities CAPABILITY_NAMED_IAM
```

## Step 5: External Stage の作成

`sql/02_external_stage.sql` を実行:

```sql
CREATE STAGE FSXN_BRONZE_STAGE
  STORAGE_INTEGRATION = fsxn_storage_integration
  URL = 's3://<S3AccessPointAlias>/bronze/';
```

## Step 6: テーブルの作成

SQL スクリプトを順番に実行:
1. `03_file_format.sql` — ファイルフォーマット定義
2. `04_external_table.sql` — External Table 作成
3. `05_iceberg_table.sql` — Iceberg Table 作成
4. `06_snowpipe.sql` — Snowpipe 設定（オプション）
5. `07_data_sharing.sql` — データ共有設定（オプション）

## トラブルシューティング

### 問題: LIST @stage が空を返す

**原因**: Storage Integration の信頼ポリシーが未設定

**解決**: Step 3-4 を再実行して信頼ポリシーを更新

### 問題: "Failure using stage area" エラー

**原因**: S3 AP ポリシーまたは IAM ロールの権限不足

**解決**:
1. IAM ロールのポリシーに S3 AP ARN が含まれているか確認
2. S3 AP ポリシーの Principal が正しいか確認
3. VPC 条件が正しいか確認

### 問題: Snowpipe がファイルを検出しない

**原因**: FSx for ONTAP は S3 Event Notification を直接サポートしない

**解決**: Lambda ポーリングパターンを使用（`06_snowpipe.sql` 参照）

## 次のステップ

- [Snowpipe 統合詳細](snowpipe-integration.md)

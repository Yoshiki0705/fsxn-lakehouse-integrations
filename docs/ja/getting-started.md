# クイックスタートガイド

🌐 [English](../en/getting-started.md)

## 前提条件

- AWS アカウント
- FSx for NetApp ONTAP ファイルシステム（デプロイ済み）
- FSxN SVM で S3 Access Point が有効
- AWS CLI v2 設定済み
- Python 3.12+

## Step 1: リポジトリのクローン

```bash
git clone https://github.com/Yoshiki0705/fsxn-lakehouse-integrations.git
cd fsxn-lakehouse-integrations
```

## Step 2: 基本インフラのデプロイ

### VPC + ネットワーク

```bash
aws cloudformation deploy \
  --template-file shared/cloudformation/vpc-networking.yaml \
  --stack-name fsxn-lakehouse-vpc \
  --capabilities CAPABILITY_IAM \
  --region ap-northeast-1
```

### FSxN + S3 Access Point

```bash
aws cloudformation deploy \
  --template-file shared/cloudformation/fsxn-s3ap-base.yaml \
  --stack-name fsxn-lakehouse-base \
  --parameter-overrides \
    VpcId=<vpc-id> \
    PreferredSubnetId=<subnet-1> \
    StandbySubnetId=<subnet-2> \
    FSxNSecurityGroupId=<sg-id> \
    S3BucketName=<svm-bucket-name> \
  --capabilities CAPABILITY_IAM \
  --region ap-northeast-1
```

## Step 3: 接続テスト

```bash
# S3 AP alias を CloudFormation 出力から取得
AP_ALIAS=$(aws cloudformation describe-stacks \
  --stack-name fsxn-lakehouse-base \
  --query 'Stacks[0].Outputs[?OutputKey==`S3AccessPointAlias`].OutputValue' \
  --output text)

# 接続テスト実行
python shared/scripts/validate-access.py --access-point-alias $AP_ALIAS
```

## Step 4: ベンダー統合の選択

| ベンダー | ディレクトリ | ステータス |
|---------|------------|----------|
| Databricks | `integrations/databricks/` | ✅ 実装済み |
| Snowflake | `integrations/snowflake/` | ✅ 実装済み |
| Athena | `integrations/athena/` | 🚧 計画中 |
| Glue | `integrations/glue/` | 🚧 計画中 |

各ベンダーの `README.md` と `docs/ja/setup-guide.md` を参照してください。

## 次のステップ

- [アーキテクチャ概要](architecture.md)
- [S3 AP 基礎](s3ap-fundamentals.md)
- [ベンダー比較](vendor-comparison.md)

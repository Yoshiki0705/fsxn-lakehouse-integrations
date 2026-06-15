# PoC インフラストラクチャ

🌐 [English](README.md) | **日本語**

---

## 概要

製造データプラットフォーム PoC インフラストラクチャ用の CloudFormation テンプレート。

## コンポーネント

| テンプレート | サービス | 目的 |
|------------|---------|------|
| `msk-serverless.yaml` | Amazon MSK Serverless | Kafka イベントバックボーン |

## 前提条件

- 適切な権限で設定済みの AWS CLI
- 異なる AZ に最低 2 つのプライベートサブネットを持つ VPC
- S3 および STS 用 VPC エンドポイント（推奨）

## デプロイ

### ステップ 1: MSK Serverless デプロイ

```bash
# プレースホルダー値を自身の VPC/サブネット ID に置き換え
aws cloudformation deploy \
  --template-file msk-serverless.yaml \
  --stack-name manufacturing-poc-msk \
  --parameter-overrides \
    VpcId=vpc-xxxxxxxxx \
    SubnetIds=subnet-aaa,subnet-bbb \
    ClusterName=manufacturing-poc-msk \
    Environment=poc \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-northeast-1
```

### ステップ 2: ブートストラップサーバー取得

```bash
# スタック出力からクラスター ARN を取得
CLUSTER_ARN=$(aws cloudformation describe-stacks \
  --stack-name manufacturing-poc-msk \
  --query 'Stacks[0].Outputs[?OutputKey==`ClusterArn`].OutputValue' \
  --output text \
  --region ap-northeast-1)

# ブートストラップサーバーを取得
aws kafka get-bootstrap-brokers \
  --cluster-arn "$CLUSTER_ARN" \
  --region ap-northeast-1
```

出力の `BootstrapBrokerStringSaslIam` を `KAFKA_BOOTSTRAP_SERVERS` として使用する。

### ステップ 3: ClickHouse Cloud 接続設定

1. ClickHouse Cloud コンソール → サービス → Settings → Networking
2. MSK エンドポイント向けに PrivateLink または IP 許可リストを設定
3. ClickHouse で Kafka Engine テーブルを作成

> **注意**: ClickHouse Cloud + MSK IAM 認証の接続性は検証が必要。
> [仮説] MSK IAM 認証は ClickHouse BYOC またはセルフマネージドで VPC ローカルアクセスが必要な場合あり。
> フォールバックオプションは ADR-006 を参照。

### ステップ 4: Databricks 接続設定

1. Databricks ワークスペースで、MSK を含む VPC への VPC ピアリングまたは PrivateLink を設定
2. Structured Streaming 設定を使用

## クリーンアップ

```bash
aws cloudformation delete-stack \
  --stack-name manufacturing-poc-msk \
  --region ap-northeast-1
```

## アーキテクチャ参照

- [ADR-001](../../docs/adr/ADR-001.md) — Kafka を工場イベントバックボーンとして使用
- [ADR-006](../../docs/adr/ADR-006.md) — ClickHouse Cloud を PoC デプロイモデルとして使用
- [DES-003](../../docs/ja/03_architecture_design.md) — Kafka トピック設計
- [DES-008](../../docs/ja/03_architecture_design.md) — ネットワークアーキテクチャ

## セキュリティノート

- MSK Serverless は IAM 認証のみ使用（ユーザー名/パスワードなし）
- セキュリティグループは VPC CIDR (10.0.0.0/16) へのアクセスを制限
- パブリックアクセスエンドポイントなし
- 全認証情報は IAM ロールで管理（静的キーなし）

## コスト見積もり

MSK Serverless 料金（PoC ワークロード）:
- クラスター時間: ~$0.75/時間（パーティション時間あたり、トピックごとに最小1パーティション）
- ストレージ: $0.10/GB-月
- データ入出力: $0.10/GB

見積もり PoC コスト: **$50-150/月**（低スループットテスト時）

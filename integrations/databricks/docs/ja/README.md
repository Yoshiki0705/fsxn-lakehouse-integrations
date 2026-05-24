# Databricks 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: 実験的**
> - Unity Catalog External Location と FSx for ONTAP S3 Access Point の組み合わせは、テスト環境においてセッションポリシー境界により成功しませんでした。
> - Instance Profile + boto3 は、制御されたドライバーノード PoC としてのみ成功しました。
> - 本リポジトリは Databricks + FSx S3 Access Points の本番サポートを主張するものではありません。

## 概要

Amazon FSx for NetApp ONTAP（FSx for ONTAP）と Databricks を S3 Access Points 経由で統合する実験的検証パッケージです。

Unity Catalog External Location は現在セッションポリシーの制約により動作しないため、本番環境での Delta Lake テーブルには [Databricks がサポートするクラウドストレージパターン](https://docs.databricks.com/aws/en/connect/storage/amazon-s3) を使用してください。

## 検証結果 (2026-05-17)

| アプローチ | 結果 | 備考 |
|----------|------|------|
| S3 AP + Unity Catalog | ❌ | セッションポリシーが S3 AP ARN をサポートしない |
| S3 AP + boto3 (Managed VPC) | ❌ | IMDS ブロック |
| NFS マウント (Managed VPC) | ❌ | Egress 制限 + seccomp |
| NFS マウント (Customer VPC) | ❌ | seccomp フィルターが NFS マウントをブロック |
| NFS RPC 直接 (Customer VPC) | ✅ | Python RPC で全操作成功 |
| ONTAP REST API (Customer VPC) | ✅ | 認証・設定変更可能 |
| Instance Profile + boto3 (Customer VPC, Dedicated) | ✅ | S3 AP 読み取り成功。UC ガバナンスをバイパス — PoC のみ |

## 非構造化データ対応

Databricks は Unity Catalog のボリューム機能を通じて非構造化データを管理できますが、FSx S3 AP との統合ではセッションポリシーの制約により現在動作しません。

**代替アプローチ:**
- Instance Profile + boto3 で S3 AP 経由のファイルアクセスは PoC レベルで可能
- NFS RPC 直接アクセスで非構造化ファイルの読み書きが可能（Customer VPC 環境）
- 本番環境では Databricks がサポートする S3 バケット直接パスを推奨

## ONTAP の価値

| ONTAP 機能 | Databricks へのメリット |
|-----------|---------------------|
| FlexClone | フルコピーなしの即時 dev/test データセットプロビジョニング |
| Snapshot | テーブルレベルのポイントインタイムリカバリ（Delta Time Travel を補完） |
| FabricPool | コールドパーティションの S3 自動階層化（Databricks に透過的） |
| 重複排除 | Delta バージョンファイルと類似データセットのストレージ削減 |
| SnapMirror | レイクハウスデータのクロスリージョン DR |

## クイックスタート

```bash
# 1. CloudFormation テンプレートをデプロイ
cp params.example.json params.json  # パラメータを編集
./deploy.sh

# 2. Databricks Storage Credential を設定（Terraform または UI）
cd terraform/
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply

# 3. External Location を作成して S3 AP を指定
# 4. ノートブックを順番に実行 (01 → 06)
```

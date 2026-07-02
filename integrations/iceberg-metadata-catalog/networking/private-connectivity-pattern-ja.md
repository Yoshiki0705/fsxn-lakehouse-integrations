# プライベート接続パターン

🌐 [English](private-connectivity-pattern.md) | 日本語

## 目的

本アーキテクチャにおいて、本番環境でプライベート接続のために VPC エンドポイントが必要な AWS サービスを文書化する。

## 必要な VPC エンドポイント

| サービス | エンドポイントタイプ | 用途 |
|---------|:---:|------|
| S3 | Gateway | FSx for ONTAP S3 AP アクセス、S3 Tables データ、バッチ I/O |
| Bedrock Runtime | Interface | リアルタイム AI 分類 + エンベディング |
| Bedrock | Interface | バッチ推論ジョブ管理 |
| SQS | Interface | FPolicy イベントキュー |
| Lambda（VPC 内の場合） | — | NAT またはエンドポイント経由のアウトバウンド |
| Glue | Interface | Glue Iceberg REST エンドポイント |
| OpenSearch Serverless | Interface | ベクトル検索インデキシング + クエリ |
| CloudWatch Logs | Interface | Lambda ロギング |
| STS | Interface | クロスサービスアクセスの AssumeRole |

## ネットワークアーキテクチャ

```
┌─────────────────────────────────────────────────────────┐
│  VPC（プライベートサブネット）                              │
│                                                          │
│  Lambda ──→ S3 Gateway Endpoint ──→ FSx for ONTAP S3 AP           │
│         ──→ Bedrock Interface Endpoint ──→ Bedrock      │
│         ──→ SQS Interface Endpoint ──→ SQS             │
│         ──→ Glue Interface Endpoint ──→ Glue REST      │
│         ──→ OpenSearch Interface Endpoint ──→ AOSS      │
│                                                          │
│  AWS サービスアクセスに NAT Gateway は不要                  │
└─────────────────────────────────────────────────────────┘
```

## 本番チェックリスト

- [ ] すべての Lambda 関数をプライベートサブネットに配置
- [ ] S3 Gateway エンドポイントとルートテーブルの関連付け
- [ ] Bedrock、SQS、Glue、OpenSearch、CloudWatch Logs、STS のインターフェースエンドポイント
- [ ] VPC エンドポイントポリシーで必要なアクションのみに制限
- [ ] インターフェースエンドポイントのセキュリティグループ（ソースを Lambda SG に制限）
- [ ] 監査のための VPC Flow Logs の有効化
- [ ] データプレーン操作でのパブリックインターネットエグレスなし

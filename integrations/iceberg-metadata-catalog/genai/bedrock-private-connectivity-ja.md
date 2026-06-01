# Bedrock プライベート接続

🌐 [English](bedrock-private-connectivity.md) | 日本語

## 目的

機密性の高いワークロードにおいて、Bedrock API 呼び出しとバッチ推論データがパブリックインターネットを経由しないことを保証する。

## 構成

### VPC インターフェースエンドポイント

| サービス | エンドポイント | 目的 |
|---------|-------------|------|
| Bedrock Runtime | `com.amazonaws.<region>.bedrock-runtime` | リアルタイム推論（Vision、Embeddings） |
| Bedrock | `com.amazonaws.<region>.bedrock` | バッチ推論ジョブ管理 |
| S3 | `com.amazonaws.<region>.s3`（Gateway） | バッチ入出力データ |

### セキュリティコントロール

- Bedrock Runtime には VPC インターフェースエンドポイントを使用
- バッチ入出力には S3 VPC ゲートウェイエンドポイントを使用
- S3 バケットポリシーを VPC エンドポイント ID で制限（`aws:sourceVpce`）
- ネットワーク証跡のために VPC Flow Logs を有効化
- Lambda 関数はプライベートサブネットに配置（パブリック IP なし）

### バッチ推論のセキュリティ

```
Lambda（プライベートサブネット）
  → VPC エンドポイント → Bedrock（バッチジョブ作成）
  → S3 VPC エンドポイント → 入力 JSONL / 出力結果
  
Bedrock または S3 アクセスに NAT ゲートウェイは不要。
```

## 参考資料

- [Bedrock VPC endpoints](https://docs.aws.amazon.com/bedrock/latest/userguide/usingVPC.html)
- [Bedrock batch inference VPC](https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-vpc.html)

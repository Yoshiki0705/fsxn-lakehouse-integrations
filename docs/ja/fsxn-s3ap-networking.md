# FSx S3 AP ネットワーキング考慮事項

## 概要

FSx for ONTAP S3 Access Points には、通常の S3 バケットアクセスとは異なるネットワーキング要件があります。本ドキュメントは複数の検証ラウンドからの知見を集約しています。

## 主な発見

### 1. S3 Gateway エンドポイントと FSx S3 AP

**既知の問題**（[FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) で文書化済み）:

> VPC 内 Lambda からタイムアウト | Internet Origin AP に S3 Gateway EP 経由でアクセス | Lambda を VPC 外に配置、または NAT Gateway 経由に変更

**説明**: VPC アタッチされた Lambda または EC2 インスタンスが internet-origin FSx S3 AP にアクセスする際、S3 Gateway VPC エンドポイントがトラフィックをインターセプトするが、FSx S3 AP バックエンドに正しくルーティングできない場合があります。FSx S3 AP alias は `s3-r-w.<region>.amazonaws.com` に解決され、Gateway エンドポイントが通常の S3 バケットトラフィックと同じ方法で処理できない可能性があるためです。

**回避策**:
1. Lambda を VPC 外に配置（VPC アタッチメントなし）— internet-origin AP に最もシンプル
2. S3 AP トラフィックに NAT Gateway を使用
3. 特定のルートテーブルから S3 Gateway エンドポイントを削除（本番非推奨 — 通常の S3 アクセス最適化が失われる）

### 2. Internet-Origin vs VPC-Origin

| AP タイプ | VPC Lambda からのアクセス | 非 VPC Lambda からのアクセス | EC2（パブリックサブネット）からのアクセス |
|---------|----------------------|---------------------------|-------------------------------|
| Internet-origin | ⚠️ Gateway EP 経由でタイムアウトの可能性 | ✅ 動作 | ✅ 動作（IGW 経由） |
| VPC-origin | ✅ 動作（Interface EP 経由） | ❌ 設計上ブロック | ✅ 動作（同一 VPC） |

### 3. AWS サービスアクセスパターン

| サービス | ネットワークパス | FSx S3 AP 互換性 |
|---------|-------------|------------------------|
| Athena | AWS マネージド（顧客 VPC なし） | ✅ Internet-origin 必須 |
| Glue ETL | AWS マネージドまたは VPC アタッチ | ✅ Internet-origin（非 VPC）または NAT Gateway（VPC） |
| EMR Serverless | AWS マネージド | ✅ Internet-origin 必須 |
| Lambda（VPC なし） | インターネット | ✅ Internet-origin で直接動作 |
| Lambda（VPC アタッチ） | VPC ルーティング | ⚠️ NAT Gateway または S3 Gateway EP なしが必要 |
| Redshift Spectrum | AWS マネージド | ✅ Internet-origin 必須 |
| Databricks | Customer-managed VPC | ⚠️ セッションポリシーでブロック（別問題） |

### 4. DNS 解決

FSx S3 AP alias は通常の S3 バケットとは異なる解決をします:

```
通常の S3 バケット:
  my-bucket.s3.ap-northeast-1.amazonaws.com → S3 サービス IP（プレフィックスリスト内）

FSx S3 AP alias:
  my-ap-alias-ext-s3alias.s3.ap-northeast-1.amazonaws.com → s3-r-w.ap-northeast-1.amazonaws.com
```

`s3-r-w` ホスト名は FSx S3 AP バックエンドです。その IP アドレスは、S3 Gateway エンドポイントが使用する S3 プレフィックスリスト（ap-northeast-1 では `pl-61a54008`）に含まれている場合と含まれていない場合があります。

### 5. トラブルシューティングチェックリスト

FSx S3 AP アクセスがタイムアウトする場合:

1. **DNS 解決を確認**: `nslookup <alias>.s3.<region>.amazonaws.com`
2. **TCP 接続性を確認**: `curl -s -o /dev/null -w '%{http_code}' --max-time 5 https://<alias>.s3.<region>.amazonaws.com/`
3. **通常の S3 をテスト**: `aws s3 ls s3://<regular-bucket>/` — これが動作すれば問題は S3 AP 固有
4. **S3 Gateway エンドポイントを確認**: ルートテーブルが Gateway エンドポイントに関連付けられているか？ はいの場合、一時的に削除を試行
5. **AP ライフサイクルを確認**: `aws fsx describe-s3-access-point-attachments` — AVAILABLE であるべき
6. **ボリュームステータスを確認**: `aws fsx describe-volumes --volume-ids <vol-id>` — CREATED/AVAILABLE であるべき
7. **SVM S3 プロトコルを確認**: SVM で S3 プロトコルが有効で、ボリュームがマウントされていることを確認

### 6. VPC 内アクセスの推奨アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│  VPC                                                             │
│                                                                  │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │ プライベートサブネット │────▶│ NAT Gateway       │────▶ IGW ──▶ FSx S3 AP
│  │ (Lambda/EC2)      │     │                   │                  │
│  └──────────────────┘     └──────────────────┘                  │
│         │                                                        │
│         │ S3 Gateway EP（通常の S3 バケットアクセス用）            │
│         └──────────────────────────────────────▶ S3 サービス      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

通常の S3 と FSx S3 AP の両方が必要な VPC 内ワークロード向け:
- 通常の S3 バケットアクセスには S3 Gateway エンドポイントを維持（無料、低レイテンシ）
- FSx S3 AP トラフィックは NAT Gateway 経由でルーティング（またはコンピュートを VPC 外に配置）

## 参考資料

- [FSx for ONTAP S3 Access Points ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)
- [S3 アクセスポイントのネットワークアクセス設定](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
- [S3 Gateway エンドポイント](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)
- [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns — s3ap-authorization-model.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/s3ap-authorization-model.md)

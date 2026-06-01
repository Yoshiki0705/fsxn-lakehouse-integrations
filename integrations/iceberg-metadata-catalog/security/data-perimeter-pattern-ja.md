# データペリメーターパターン

🌐 [English](data-perimeter-pattern.md) | 日本語

## 目的

規制環境において、生ファイルアクセスとメタデータクエリに対するネットワークおよびアイデンティティ境界を定義する。

## レイヤー

| レイヤー | コントロール | 目的 |
|---------|------------|------|
| S3 Access Point ポリシー | AP 上のリソースポリシー | ファイルにアクセスできる IAM プリンシパルを制限 |
| S3 AP の VPC オリジン | ネットワーク制限 | リクエストが特定の VPC から来ることを保証 |
| VPC エンドポイントポリシー | エンドポイントレベルのフィルター | 許可する S3/Glue/Bedrock アクションを制限 |
| IAM アイデンティティポリシー | プリンシパル権限 | ロールごとの最小権限 |
| IAM 権限バウンダリー | ガードレール | 権限昇格の防止 |
| SCP (Organizations) | アカウントレベルのガードレール | コントロールの無効化を防止 |
| Lake Formation | データガバナンス | メタデータに対するテーブル/カラム/行アクセス |

## 推奨構成

```
規制環境では、以下を組み合わせる:
1. S3 Access Point ポリシー（プリンシパル + プレフィックスの制限）
2. VPC エンドポイントポリシー（特定バケット/テーブルへのアクション制限）
3. IAM アイデンティティポリシー（Lambda/ロールごとの最小権限）
4. AWS Organizations SCP（CloudTrail、LF 等の無効化防止）
5. Lake Formation グラント（メタデータクエリガバナンス）
```

## 参考資料

- [S3 Access Points VPC origin](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points-vpc.html)
- [VPC endpoint policies](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-access.html)
- [Data perimeter on AWS](https://docs.aws.amazon.com/whitepapers/latest/building-a-data-perimeter-on-aws/building-a-data-perimeter-on-aws.html)

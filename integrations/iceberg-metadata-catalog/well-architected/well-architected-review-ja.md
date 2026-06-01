# Well-Architected レビューサマリー

🌐 [English](well-architected-review.md) | 日本語

## 目的

本 PoC を AWS Well-Architected 6 つの柱に照らし合わせ、検証済みの項目と本番環境前に追加作業が必要な項目を特定する。

## 柱別評価

| 柱 | 現在のカバレッジ | 残りの検証項目 |
|---|----------------|--------------|
| **運用上の優秀性** | CloudWatch メトリクス/アラーム、メンテナンスランブック、エビデンス YAML、名前付きクエリ | インシデントランブック、ゲームデイ、自動修復 |
| **セキュリティ** | Lake Formation、IAM、S3 AP アイデンティティマトリクス、データペリメーターパターン、PII 検出 | KMS ポリシー、SCP 適用、ペネトレーションテスト、VPC エンドポイントポリシー |
| **信頼性** | SQS/DLQ、リトライ、部分バッチレスポンス、ソフトデリート | マルチ AZ 障害テスト、DR リバインド検証、カオスエンジニアリング |
| **パフォーマンス効率** | Athena vs リスティング比較、FSx メトリクス、パフォーマンス境界の文書化 | 100 万ファイル以上でのスケールテスト、同時アクセスの影響、マニフェスト増大 |
| **コスト最適化** | デモコスト、月次予測、バックフィルモデル、ユニットエコノミクス | リザーブドキャパシティ評価、Bedrock 向け Savings Plans、コスト異常アラート |
| **サステナビリティ** | S3 コピーの重複なし、選択的 AI エンリッチメント、ゼロスケール | クエリあたりのカーボン測定、エンベディング次元の最適化、バッチスケジューリング |

## 主要リスク（本番前）

1. **クレデンシャルベンディング**: Snowflake Glue REST パスが未解決
2. **スケールテスト**: 10 万ファイル以上でのテスト未実施
3. **DR リバインド**: 実際の SnapMirror フェイルオーバーでのテスト未実施
4. **カラムレベル LF**: フェデレーテッドカタログパスでの制限を確認
5. **FPolicy**: 本番 NFS/SMB 負荷下でのイベントボリューム未測定

## 参考資料

- [AWS Well-Architected Framework](https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html)
- [Well-Architected Tool](https://aws.amazon.com/well-architected-tool/)

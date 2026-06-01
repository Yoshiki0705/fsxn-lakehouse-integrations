# SQS → Lambda 処理パターン

🌐 [English](sqs-lambda-processing-pattern.md) | 日本語

## 設計原則

- `visibility_timeout` >= 6 × `lambda_timeout`
- `maxReceiveCount` >= 5（DLQ 移行前）
- 部分バッチレスポンスを有効化（`ReportBatchItemFailures`）
- 冪等性キー: `file_id + change_type + event_time`
- 通常運用時は `reserved_concurrency = 1` に設定（Iceberg コミット競合を回避）
- バックフィル時のみ明示的な調整のもとで並行度を増加
- ポイズンメッセージはリドライブ手順付きで DLQ にルーティング

## メッセージスキーマ

```json
{
  "event_type": "create | close_modified | rename | delete",
  "file_path": "/vol1/media/documents/invoice.pdf",
  "file_size": 1024,
  "timestamp": "2026-06-01T10:00:00Z",
  "svm_name": "svm1",
  "volume_name": "vol1",
  "access_point_arn": "arn:aws:s3:ap-northeast-1:<ACCOUNT>:accesspoint/...",
  "idempotency_key": "<file_id>:<change_type>:<event_time>"
}
```

## 冪等性

- `file_id + change_type + event_time` を重複排除キーとして使用
- 書き込み前に同じキーのレコードが既に存在するか確認
- 重複検出時はサクセスを返す（再処理しない）
- Iceberg の追記専用特性により、重複はクエリ時に `latest_records.sql` で処理

## ポイズンピル処理

- `maxReceiveCount` 回失敗したメッセージは DLQ に移動
- DLQ アラームが調査をトリガー
- リドライブ: 根本原因を修正 → `start-message-move-task` でソースキューに戻す
- 調査なしの自動リドライブは禁止

## 参考資料

- [Lambda + SQS event source mapping](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [Partial batch responses](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#services-sqs-batchfailurereporting)

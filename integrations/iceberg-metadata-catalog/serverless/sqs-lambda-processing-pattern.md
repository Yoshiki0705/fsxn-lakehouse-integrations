# SQS → Lambda Processing Pattern

## Design Principles

- `visibility_timeout` >= 6 × `lambda_timeout`
- `maxReceiveCount` >= 5 (before DLQ)
- Enable partial batch response (`ReportBatchItemFailures`)
- Idempotency key: `file_id + change_type + event_time`
- Set `reserved_concurrency = 1` during normal operation (avoid Iceberg commit conflicts)
- Increase concurrency only for backfill with explicit coordination
- Route poison messages to DLQ with redrive instructions

## Message Schema

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

## Idempotency

- Use `file_id + change_type + event_time` as dedup key
- Check if record with same key already exists before write
- If duplicate detected, return success (don't reprocess)
- Iceberg append-only means duplicates are handled at query time via `latest_records.sql`

## Poison Pill Handling

- Messages that fail `maxReceiveCount` times go to DLQ
- DLQ alarm triggers investigation
- Redrive: fix root cause → `start-message-move-task` to move back to source queue
- Never auto-redrive without investigation

## References

- [Lambda + SQS event source mapping](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [Partial batch responses](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html#services-sqs-batchfailurereporting)

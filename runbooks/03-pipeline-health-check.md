# Runbook 03: Pipeline Health Check / パイプライン健全性チェック

> 🌐 Bilingual (JA/EN)

## Trigger / トリガー

- 週次定期実行（推奨: 月曜午前）
- CloudWatch ダッシュボードで異常値を検出した場合
- 新規パイプライン追加/変更後の確認

## Purpose / 目的

FSx for ONTAP → S3 → Databricks UC パイプライン全体の健全性を確認し、潜在的問題を早期発見する。

---

## Health Check Checklist / 健全性チェック項目

### Section A: FSx for ONTAP ソース

- [ ] **A1**: ファイルシステムステータス確認:
  ```bash
  aws fsx describe-file-systems --file-system-ids <FS_ID> \
    --query 'FileSystems[0].{Status:Lifecycle,Storage:StorageCapacity,Throughput:ThroughputCapacity}'
  ```
  - 期待: `Lifecycle = AVAILABLE`

- [ ] **A2**: ストレージ使用率確認（80% 超は警告）:
  ```bash
  aws cloudwatch get-metric-statistics --namespace AWS/FSx \
    --metric-name StorageUsed --dimensions Name=FileSystemId,Value=<FS_ID> \
    --period 3600 --start-time <24H_AGO> --end-time <NOW> --statistics Average
  ```

- [ ] **A3**: スループット使用率確認（70% 超は調査推奨）:
  ```bash
  aws cloudwatch get-metric-statistics --namespace AWS/FSx \
    --metric-name ThroughputUtilization --dimensions Name=FileSystemId,Value=<FS_ID> \
    --period 3600 --start-time <24H_AGO> --end-time <NOW> --statistics Maximum
  ```

- [ ] **A4**: Snapshot 領域確認（過剰な Snapshot 蓄積がないか）

### Section B: DataSync 同期

- [ ] **B1**: 直近 7 日間のタスク実行ステータス:
  ```bash
  aws datasync list-task-executions --task-arn <TASK_ARN> --max-results 50 \
    | jq '.TaskExecutions[] | {Status, StartTime}'
  ```
  - 期待: 全て `SUCCESS`。1 件でも `ERROR` があれば Runbook #01 を実行

- [ ] **B2**: 転送バイト数のトレンド確認（急増/急減は異常の兆候）:
  ```bash
  aws cloudwatch get-metric-statistics --namespace AWS/DataSync \
    --metric-name BytesTransferred --dimensions Name=TaskArn,Value=<TASK_ARN> \
    --period 86400 --start-time <7D_AGO> --end-time <NOW> --statistics Sum
  ```

- [ ] **B3**: タスク実行時間のトレンド（増加傾向はファイル増加/性能劣化の兆候）

- [ ] **B4**: スケジュール実行漏れがないか（EventBridge ルール実行回数と DataSync 実行回数の一致）

### Section C: S3 宛先

- [ ] **C1**: S3 バケットのオブジェクト数/サイズが期待通りか:
  ```bash
  aws s3 ls s3://<BUCKET>/fsxn-sync/ --summarize --recursive | tail -2
  ```

- [ ] **C2**: S3 Lifecycle ルールが正常動作しているか（意図しない削除/階層化がないか）

- [ ] **C3**: S3 バケットポリシーが変更されていないか:
  ```bash
  aws s3api get-bucket-policy --bucket <BUCKET> | jq '.Policy | fromjson'
  ```

### Section D: Databricks UC

- [ ] **D1**: External Location が有効か:
  ```sql
  VALIDATE EXTERNAL LOCATION fsxn_synced;
  ```

- [ ] **D2**: テーブルのデータ鮮度確認:
  ```sql
  SELECT MAX(timestamp) as latest_data, current_timestamp() as check_time,
         TIMESTAMPDIFF(MINUTE, MAX(timestamp), current_timestamp()) as lag_minutes
  FROM catalog_name.schema_name.sensor_data;
  ```
  - 期待: `lag_minutes` < DataSync スケジュール間隔 × 2

- [ ] **D3**: Auto Loader の checkpoint 健全性:
  ```sql
  -- ストリーミングジョブのステータス確認
  SELECT * FROM system.lakeflow.streaming_executions
  WHERE pipeline_name LIKE '%sensor%'
  ORDER BY update_time DESC LIMIT 5;
  ```

- [ ] **D4**: Row Filter / Column Mask が正常適用されているか（テストユーザーで確認）

### Section E: コスト

- [ ] **E1**: DataSync 転送コスト（月次予算内か）:
  ```bash
  aws ce get-cost-and-usage --time-period Start=<MONTH_START>,End=<TODAY> \
    --granularity DAILY --metrics UnblendedCost \
    --filter '{"Dimensions":{"Key":"SERVICE","Values":["AWS DataSync"]}}'
  ```

- [ ] **E2**: S3 ストレージコスト（Lifecycle で最適化されているか）

- [ ] **E3**: 不要な DataSync タスク実行がないか（全ファイル転送 `TransferMode: ALL` になっていないか）

### Section F: セキュリティ

- [ ] **F1**: IAM ロールの最終使用日確認（不使用ロールの検出）:
  ```bash
  aws iam get-role --role-name <DATASYNC_ROLE> \
    --query 'Role.RoleLastUsed'
  ```

- [ ] **F2**: CloudTrail で不正な `StartTaskExecution` がないか

- [ ] **F3**: S3 アクセスログで unexpected なソースからのアクセスがないか

---

## Health Dashboard Metrics / 推奨ダッシュボードメトリクス

CloudWatch ダッシュボードに以下を含めることを推奨:

| ウィジェット | メトリクス | アラーム閾値 |
|---|---|---|
| DataSync 成功率 | TaskExecutions (SUCCESS / ERROR 比) | 成功率 < 95% |
| DataSync 転送量 | BytesTransferred (日次) | 前日比 ±50% |
| DataSync 実行時間 | Duration (p95) | > 前週 p95 × 2 |
| FSx for ONTAP ストレージ | StorageUsed / StorageCapacity | > 80% |
| FSx for ONTAP スループット | ThroughputUtilization | > 70% |
| Lambda エラー率 | Errors / Invocations | > 5% |
| DLQ 深度 | SQS ApproximateNumberOfMessages | > 100 |
| UC データ鮮度 | Custom metric (lag_minutes) | > スケジュール × 3 |

---

## Result Recording / 結果記録

```markdown
## Health Check Report - [DATE]

### Summary
- Overall Status: ✅ Healthy / ⚠️ Degraded / ❌ Unhealthy
- Checked by: [Role]
- Duration: [minutes]

### Findings
| Section | Status | Notes |
|---------|--------|-------|
| A: FSx for ONTAP | ✅ / ⚠️ / ❌ | |
| B: DataSync | ✅ / ⚠️ / ❌ | |
| C: S3 | ✅ / ⚠️ / ❌ | |
| D: UC | ✅ / ⚠️ / ❌ | |
| E: Cost | ✅ / ⚠️ / ❌ | |
| F: Security | ✅ / ⚠️ / ❌ | |

### Action Items
- [ ] ...
```

---

## Related Runbooks / 関連 Runbook

- [Runbook #01: DataSync Failure Triage](./01-datasync-failure-triage.md) — B1 で ERROR 検出時
- [Runbook #02: FPolicy Lambda Failure](./02-fpolicy-lambda-failure.md) — Lambda エラー検出時

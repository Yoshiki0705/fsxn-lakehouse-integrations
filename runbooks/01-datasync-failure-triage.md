# Runbook 01: DataSync Task Failure Triage / DataSync タスク失敗トリアージ

> 🌐 Bilingual (JA/EN)

## Trigger / トリガー

- CloudWatch アラーム `DataSyncTaskExecutionFailed` が発報
- `aws datasync describe-task-execution` で `Status: ERROR` を検出
- 手動確認で同期データの欠落を発見

## Severity / 重大度

| レイテンシ影響 | データ欠損リスク | 対応目標 |
|:---:|:---:|:---:|
| 同期遅延（分〜時間） | 低（再実行で回復可能） | 30 分以内に原因特定、1 時間以内に復旧 |

---

## Triage Checklist / トリアージ手順

### Step 1: タスク実行ステータス確認

```bash
# 最新のタスク実行を取得
aws datasync list-task-executions \
  --task-arn <TASK_ARN> \
  --max-results 5

# 失敗したタスク実行の詳細
aws datasync describe-task-execution \
  --task-execution-arn <TASK_EXECUTION_ARN>
```

- [ ] `Status` を確認: `ERROR` / `CANCELLED` / `TIMEOUT`
- [ ] `Result.ErrorCode` を確認
- [ ] `Result.ErrorDetail` のメッセージを記録

### Step 2: エラーコード別の原因特定

| ErrorCode | 原因（EN） | 原因（JA） | 対処 |
|-----------|-----------|-----------|------|
| `SourceNotFound` | Source location unreachable | ソースロケーションへのアクセス不可 | → Step 3a |
| `DestinationNotFound` | Destination S3 unreachable | 宛先 S3 へのアクセス不可 | → Step 3b |
| `InsufficientPermissions` | IAM role lacks permissions | IAM ロール権限不足 | → Step 3c |
| `NetworkError` | VPC/Security Group issue | ネットワーク接続問題 | → Step 3d |
| `Timeout` | Task exceeded timeout | タスクタイムアウト | → Step 3e |
| `InternalError` | AWS service error | AWS 内部エラー | → Step 3f |

### Step 3a: ソースロケーション問題

- [ ] FSx for ONTAP ファイルシステムが `AVAILABLE` か確認:
  ```bash
  aws fsx describe-file-systems --file-system-ids <FS_ID> \
    --query 'FileSystems[0].Lifecycle'
  ```
- [ ] SVM が `CREATED` 状態か確認
- [ ] NFS エクスポートが存在するか確認（ONTAP CLI）
- [ ] Security Group が DataSync エージェントからの NFS (2049) を許可しているか確認
- [ ] FlexClone ボリュームが削除されていないか確認（Snapshot ステージングパターン使用時）

### Step 3b: 宛先 S3 問題

- [ ] S3 バケットが存在するか確認:
  ```bash
  aws s3 ls s3://<BUCKET_NAME>/fsxn-sync/ --max-items 1
  ```
- [ ] バケットポリシーが DataSync サービスロールを許可しているか確認
- [ ] S3 VPC Endpoint が正常か確認（VPC Endpoint 使用時）
- [ ] バケットのリージョンがタスクと一致しているか確認

### Step 3c: IAM 権限問題

- [ ] DataSync サービスロールの IAM ポリシーを確認:
  ```bash
  aws iam get-role-policy --role-name <DATASYNC_ROLE> --policy-name <POLICY>
  ```
- [ ] 必要権限: `s3:PutObject`, `s3:DeleteObject`, `s3:ListBucket`, `s3:GetBucketLocation`
- [ ] Resource ARN がバケット/プレフィックスに制限されている場合、パスが正しいか確認
- [ ] STS AssumeRole が成功しているか CloudTrail で確認

### Step 3d: ネットワーク問題

- [ ] DataSync 用 Security Group のアウトバウンドルールを確認
- [ ] FSx for ONTAP のデータ LIF に到達可能か確認（VPC 内）
- [ ] VPC Flow Logs で Reject を確認:
  ```bash
  aws logs filter-log-events --log-group-name /aws/vpc/flowlogs/<VPC_ID> \
    --filter-pattern "REJECT"
  ```
- [ ] DNS 解決が正常か確認（Private Hosted Zone 使用時）

### Step 3e: タイムアウト問題

- [ ] 前回成功時の転送バイト数と比較:
  ```bash
  aws datasync describe-task-execution --task-execution-arn <PREV_SUCCESS_ARN> \
    --query 'BytesTransferred'
  ```
- [ ] ファイル数が急増していないか確認（新規大量ファイル投入等）
- [ ] FSx for ONTAP のスループット使用率を確認:
  ```bash
  aws cloudwatch get-metric-statistics --namespace AWS/FSx \
    --metric-name ThroughputUtilization \
    --dimensions Name=FileSystemId,Value=<FS_ID> \
    --period 300 --start-time <TIME> --end-time <TIME> --statistics Average
  ```
- [ ] 対策: includes/excludes フィルタで対象を絞る、スケジュール間隔を延長する

### Step 3f: AWS 内部エラー

- [ ] AWS Health Dashboard を確認
- [ ] DataSync サービスのリージョン別ステータスを確認
- [ ] 30 分待って再実行:
  ```bash
  aws datasync start-task-execution --task-arn <TASK_ARN>
  ```
- [ ] 再発する場合は AWS Support ケースを起票

---

## Recovery / 復旧手順

### 即時復旧（手動再実行）

```bash
# 手動でタスクを再実行
aws datasync start-task-execution --task-arn <TASK_ARN>

# 実行ステータスを監視
watch -n 30 "aws datasync describe-task-execution \
  --task-execution-arn <NEW_EXECUTION_ARN> \
  --query 'Status'"
```

### スケジュール重複回避

- [ ] 失敗時にスケジュールが継続実行されていないか確認
- [ ] 重複実行のリスクがある場合、一時的にスケジュールを停止:
  ```bash
  aws datasync update-task --task-arn <TASK_ARN> --schedule ""
  ```
- [ ] 手動復旧完了後にスケジュールを再設定

---

## Escalation / エスカレーション

| 条件 | エスカレーション先 |
|------|----------------|
| 1 時間以内に復旧しない | チームリーダー |
| データ欠損が確認された | データオーナー + セキュリティチーム |
| AWS 内部エラーが継続 | AWS Support（Severity 3 以上） |
| FSx for ONTAP 自体が `MISCONFIGURED` | AWS Support + ストレージチーム |

---

## Post-Incident / インシデント後

- [ ] 根本原因を記録（5 Why 分析）
- [ ] CloudWatch アラームの閾値を見直し
- [ ] 再発防止策を実装（IAM 修正、SG 修正、スケジュール調整等）
- [ ] Runbook の更新が必要か確認

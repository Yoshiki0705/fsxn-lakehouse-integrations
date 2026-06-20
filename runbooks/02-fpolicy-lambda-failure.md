# Runbook 02: FPolicy Lambda Failure & DLQ Reprocessing / FPolicy Lambda 障害と DLQ 再処理

> 🌐 Bilingual (JA/EN)

## Trigger / トリガー

- CloudWatch アラーム `FPolicyLambdaErrors` が発報（エラー率 > 5%）
- CloudWatch アラーム `FPolicyDLQDepth` が発報（DLQ メッセージ数 > 100）
- Lambda 同時実行数の throttling が検出
- 下流の S3 / Kafka にイベントが到達しない

## Severity / 重大度

| レイテンシ影響 | データ欠損リスク | 対応目標 |
|:---:|:---:|:---:|
| イベント遅延（秒〜分） | 中（DLQ に退避されるが再処理が必要） | 15 分以内に原因特定、30 分以内に復旧 |

---

## Triage Checklist / トリアージ手順

### Step 1: Lambda 関数の健全性確認

```bash
# Lambda エラーメトリクス確認（直近1時間）
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=<FPOLICY_LAMBDA_NAME> \
  --period 300 --start-time <1H_AGO> --end-time <NOW> \
  --statistics Sum

# Lambda throttle 確認
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Throttles \
  --dimensions Name=FunctionName,Value=<FPOLICY_LAMBDA_NAME> \
  --period 300 --start-time <1H_AGO> --end-time <NOW> \
  --statistics Sum

# 最新の Lambda 呼び出しログ
aws logs tail /aws/lambda/<FPOLICY_LAMBDA_NAME> --since 30m --format short
```

- [ ] `Errors` が急増しているか確認
- [ ] `Throttles` が発生しているか確認
- [ ] `Duration` が制限時間（15分）に近づいているか確認
- [ ] ログのエラーメッセージを記録

### Step 2: エラーパターン別の原因特定

| エラーパターン | 原因（EN） | 原因（JA） | 対処 |
|---|---|---|---|
| `Task timed out after 900s` | Lambda timeout (15 min limit) | Lambda タイムアウト | → Step 3a |
| `TooManyRequestsException` | Throttling (concurrency limit) | スロットリング | → Step 3b |
| `AccessDeniedException` on S3 | IAM permission issue | S3 権限不足 | → Step 3c |
| `NetworkError` / `ConnectionTimeout` | VPC/ENI issue | ネットワーク問題 | → Step 3d |
| `KafkaProducerError` | MSK unreachable | Kafka 接続失敗 | → Step 3e |
| `JSONDecodeError` / `KeyError` | Malformed FPolicy event | 不正な FPolicy イベント | → Step 3f |

### Step 3a: Lambda タイムアウト

- [ ] 処理対象ファイルのサイズを確認（大容量ファイルが投入された可能性）
- [ ] Lambda メモリ設定を確認（メモリ不足で処理が遅延する場合あり）
- [ ] バッチサイズが大きすぎないか確認（SQS バッチサイズ削減を検討）
- [ ] 対策:
  - 大容量ファイルはスキップし、DataSync パスに委ねる設計に変更
  - Lambda メモリを増強（128MB → 512MB / 1024MB）
  - SQS バッチサイズを 10 → 1 に削減（1 イベント/呼び出し）

### Step 3b: スロットリング（同時実行制限）

- [ ] Reserved Concurrency の設定値を確認:
  ```bash
  aws lambda get-function-concurrency --function-name <FPOLICY_LAMBDA_NAME>
  ```
- [ ] アカウント全体の同時実行使用率を確認
- [ ] 勤務時間帯のバースト（シフト開始時にファイル大量生成）か確認
- [ ] 対策:
  - Reserved Concurrency を引き上げ（現在値 → 2x）
  - SQS バッファの `VisibilityTimeout` を延長（再配信防止）
  - EventBridge Pipe でスロットリング制御を追加

### Step 3c: S3 権限問題

- [ ] Lambda 実行ロールの IAM ポリシーを確認:
  ```bash
  aws iam list-attached-role-policies --role-name <LAMBDA_ROLE>
  ```
- [ ] `s3:PutObject` が対象バケット/プレフィックスに対して許可されているか
- [ ] S3 バケットポリシーで Lambda ロールが Deny されていないか
- [ ] KMS 権限（SSE-KMS 使用時に `kms:GenerateDataKey` が必要）

### Step 3d: ネットワーク問題（VPC Lambda）

- [ ] Lambda の VPC 設定を確認:
  ```bash
  aws lambda get-function-configuration --function-name <FPOLICY_LAMBDA_NAME> \
    --query 'VpcConfig'
  ```
- [ ] サブネットの利用可能 IP アドレス数を確認（ENI 枯渇）
- [ ] Security Group のアウトバウンドルールを確認
- [ ] NAT Gateway / VPC Endpoint の健全性確認
- [ ] 対策: サブネットを追加（ENI 枯渇対策）、SG ルール修正

### Step 3e: Kafka (MSK) 接続失敗

- [ ] MSK クラスターの状態確認:
  ```bash
  aws kafka describe-cluster --cluster-arn <MSK_ARN> --query 'ClusterInfo.State'
  ```
- [ ] Bootstrap servers の DNS 解決を確認
- [ ] MSK の Security Group が Lambda Security Group からの Inbound を許可しているか
- [ ] MSK の IAM 認証設定が正しいか
- [ ] 対策: MSK クラスターの再起動、SG ルール修正

### Step 3f: 不正な FPolicy イベント

- [ ] DLQ のメッセージボディを確認:
  ```bash
  aws sqs receive-message --queue-url <DLQ_URL> --max-number-of-messages 5
  ```
- [ ] イベントペイロードのフォーマットが期待通りか確認
- [ ] FSx for ONTAP の ONTAP バージョンアップでイベント形式が変わっていないか
- [ ] 対策: Lambda のパーサーを修正、不正イベントはログ記録後に廃棄

---

## DLQ Reprocessing / DLQ 再処理手順

### 前提確認

- [ ] 根本原因が解決されていることを確認（解決前に再処理すると再度 DLQ に戻る）
- [ ] DLQ 内のメッセージ数を確認:
  ```bash
  aws sqs get-queue-attributes --queue-url <DLQ_URL> \
    --attribute-names ApproximateNumberOfMessages
  ```

### 再処理実行

```bash
# Option A: DLQ からメインキューに移動（AWS CLI）
# ※ aws sqs start-message-move-task は 2023年6月以降利用可能
aws sqs start-message-move-task \
  --source-arn <DLQ_ARN> \
  --destination-arn <MAIN_QUEUE_ARN>

# 移動ステータス確認
aws sqs list-message-move-tasks --source-arn <DLQ_ARN>
```

```bash
# Option B: スクリプトで1件ずつ再処理（Lambda を直接 invoke）
# ※ メッセージ数が少ない場合（<100）に推奨
while true; do
  MSG=$(aws sqs receive-message --queue-url <DLQ_URL> --max-number-of-messages 1 --query 'Messages[0]' --output json)
  [ "$MSG" = "null" ] && break
  BODY=$(echo $MSG | jq -r '.Body')
  RECEIPT=$(echo $MSG | jq -r '.ReceiptHandle')
  
  # Lambda を直接呼び出し
  aws lambda invoke --function-name <FPOLICY_LAMBDA_NAME> \
    --payload "$BODY" /tmp/response.json
  
  # 成功したら DLQ から削除
  if [ $? -eq 0 ]; then
    aws sqs delete-message --queue-url <DLQ_URL> --receipt-handle "$RECEIPT"
  fi
done
```

### 再処理後の確認

- [ ] DLQ が空になったか確認
- [ ] メインキューの処理が正常に進んでいるか確認
- [ ] 下流（S3 / Kafka）にデータが到達しているか確認
- [ ] 重複イベントが発生していないか確認（冪等性チェック）

---

## Monitoring Setup / モニタリング設定

以下のアラームが設定済みであることを確認:

| アラーム名 | メトリクス | 閾値 | アクション |
|-----------|-----------|------|----------|
| `FPolicyLambdaErrors` | Lambda Errors | > 5/5min | SNS → オペレーター通知 |
| `FPolicyLambdaThrottle` | Lambda Throttles | > 10/5min | SNS → オペレーター通知 |
| `FPolicyDLQDepth` | SQS ApproximateNumberOfMessages (DLQ) | > 100 | SNS → オペレーター通知 |
| `FPolicyLambdaDuration` | Lambda Duration p95 | > 300000ms (5min) | SNS → 早期警告 |

---

## Escalation / エスカレーション

| 条件 | エスカレーション先 |
|------|----------------|
| DLQ が 1000 メッセージ超 | データエンジニアリングリーダー |
| Lambda が 1 時間以上エラー継続 | インフラチーム |
| MSK クラスター障害 | AWS Support + ストリーミングチーム |
| データ欠損が確認された | データオーナー + セキュリティチーム |

---

## Post-Incident / インシデント後

- [ ] 根本原因を記録
- [ ] DLQ 再処理後のデータ整合性を確認
- [ ] Reserved Concurrency / メモリ / タイムアウトの見直し
- [ ] 大容量ファイルの除外パターン見直し
- [ ] アラーム閾値の妥当性確認

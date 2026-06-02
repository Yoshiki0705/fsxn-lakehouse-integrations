# Databricks + AWS 監査相関ガイド

🌐 日本語 | [English](audit-correlation-guide.md)

## 目的

Databricks Unity Catalog と AWS サービス間の監査イベントを相関させ、エンドツーエンドのインシデント調査を可能にする方法を定義する。

## 監査ソース

| ソース | 記録内容 | 保持期間 |
|---|---|---|
| Databricks `system.access.audit` | UC メタデータクエリ、credential 発行、テーブルアクセス | システムテーブル（設定可能） |
| AWS CloudTrail | API コール (Glue, S3, Lake Formation, Bedrock) | 90日（イベント履歴）または S3 Trail（設定可能） |
| S3 Access Logs | S3 AP 上のオブジェクトレベル読み書き | S3 バケット（設定可能） |
| Lake Formation 監査 | LF ガバナンス下テーブルへのデータアクセス | CloudTrail |
| OpenSearch 監査 | 検索クエリとインデックス操作 | CloudWatch Logs |

## 相関キー

| Databricks フィールド | AWS フィールド | 相関方法 |
|---|---|---|
| `user_identity.email` | CloudTrail `userIdentity.arn` | Databricks ユーザー → 引き受けた IAM ロールのマッピング |
| `service_name = 'uniformIcebergRestCatalog'` | — | 外部エンジンアクセスの識別 |
| `action_name = 'loadTableCredentials'` | CloudTrail `AssumeRole` | Credential 発行 → ロール引き受け |
| `request_params.table_name` | Glue `GetTable` / S3 `GetObject` | テーブル → 基盤 S3 パス |
| `source_ip_address` | CloudTrail `sourceIPAddress` | ネットワーク相関 |
| `event_time` | CloudTrail `eventTime` | 時間相関（±5分ウィンドウ） |

## 調査ワークフロー

### シナリオ: 「Databricks から機密メタデータにアクセスしたのは誰か？」

```sql
-- ステップ 1: メタデータテーブルアクセスの Databricks 監査クエリ
SELECT
  event_time,
  user_identity.email,
  action_name,
  request_params.full_name_arg AS table_accessed,
  source_ip_address
FROM system.access.audit
WHERE service_name = 'unityCatalog'
  AND request_params.full_name_arg LIKE '%unstructured_files%'
  AND event_date >= '2026-06-01'
ORDER BY event_time DESC;
```

```sql
-- ステップ 2: 対応する AWS API コールの CloudTrail クエリ
-- (CloudTrail ログ上の Athena 経由)
SELECT
  eventtime,
  useridentity.arn,
  eventsource,
  eventname,
  requestparameters
FROM cloudtrail_logs
WHERE eventsource = 'glue.amazonaws.com'
  AND eventname IN ('GetTable', 'GetDatabase')
  AND eventtime >= '2026-06-01'
ORDER BY eventtime DESC;
```

## 監査ギャップ: Credential 発行後のファイルアクセス

Databricks UC 監査ログは **credential 発行** を記録するが、credential 発行後の個別 S3 ファイル読み取りは記録しない。ファイルレベル監査を実現するには:

1. S3 Tables バケットで S3 Access Logging を有効化
2. S3 の CloudTrail データイベントを有効化
3. credential 発行時の assumed role ARN と S3 アクセスログを相関
4. コンプライアンス監視に AWS Config ルールを検討

## 参考資料

- [Databricks system.access.audit](https://docs.databricks.com/aws/en/admin/system-tables/audit)
- [AWS CloudTrail](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/)
- [Lake Formation 監査ログ](https://docs.aws.amazon.com/lake-formation/latest/dg/cloudtrail-logging.html)

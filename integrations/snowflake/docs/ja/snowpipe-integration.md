# Snowpipe + FSxN 統合ガイド

## 概要

Snowpipe を使用して FSx for NetApp ONTAP に新しいファイルが追加された際に
自動的に Snowflake テーブルにデータを取り込む方法を説明します。

## 課題: FSxN と S3 Event Notification

FSxN の S3 プロトコルは S3 Event Notification を直接サポートしていません。
そのため、Snowpipe の `AUTO_INGEST` を使用するには代替パターンが必要です。

## 推奨パターン

### パターン A: Lambda ポーリング（推奨）

```
┌──────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐    ┌──────────┐
│EventBridge│──▶│  Lambda  │──▶│  SNS    │──▶│Snowflake │──▶│Snowpipe  │
│(Schedule) │   │(List new │   │  Topic  │   │  SQS     │   │(COPY INTO)│
│ 1min/5min │   │ files)   │   │         │   │          │   │          │
└──────────┘    └──────────┘    └─────────┘    └──────────┘    └──────────┘
                     │
                     ▼
              ┌──────────────┐
              │ S3 AP → FSxN │
              │ (ListObjects)│
              └──────────────┘
```

**メリット:**
- シンプルな実装
- EventBridge でスケジュール制御
- 検出遅延は最大ポーリング間隔

**デメリット:**
- リアルタイムではない（1-5分の遅延）
- ListObjects のコスト（大量ファイル時）

### パターン B: ONTAP FPolicy（高度）

```
┌──────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
│  ONTAP   │──▶│ FPolicy  │──▶│  Lambda │──▶│   SNS   │──▶ Snowpipe
│  Volume  │   │  Server  │   │         │   │         │
│(file ops)│   │(external)│   │         │   │         │
└──────────┘    └──────────┘    └─────────┘    └─────────┘
```

**メリット:**
- リアルタイム検出
- ファイル操作レベルの粒度

**デメリット:**
- FPolicy サーバーの運用が必要
- 設定が複雑

### パターン C: 手動リフレッシュ（開発用）

```sql
ALTER PIPE FSXN_EVENTS_PIPE REFRESH;
```

## Lambda ポーリング実装例

```python
import boto3
import json
from datetime import datetime, timedelta

s3 = boto3.client('s3')
sns = boto3.client('sns')

def handler(event, context):
    ap_alias = os.environ['S3_ACCESS_POINT_ALIAS']
    sns_topic = os.environ['SNS_TOPIC_ARN']
    prefix = os.environ.get('PREFIX', 'bronze/events/')
    
    # List files modified in last polling interval
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    
    response = s3.list_objects_v2(
        Bucket=ap_alias,
        Prefix=prefix
    )
    
    new_files = []
    for obj in response.get('Contents', []):
        if obj['LastModified'].replace(tzinfo=None) > cutoff:
            new_files.append(obj['Key'])
    
    if new_files:
        # Publish to SNS for Snowpipe
        message = {
            'Records': [
                {
                    's3': {
                        'bucket': {'name': ap_alias},
                        'object': {'key': f}
                    }
                }
                for f in new_files
            ]
        }
        sns.publish(
            TopicArn=sns_topic,
            Message=json.dumps(message)
        )
    
    return {'new_files': len(new_files)}
```

## 設定手順

1. CloudFormation で `EnableSnowpipe=true` を設定
2. Snowpipe を作成（`06_snowpipe.sql`）
3. `SHOW PIPES` で notification_channel を取得
4. SNS Topic に Snowflake SQS をサブスクライブ
5. Lambda ポーリング関数をデプロイ
6. EventBridge ルールでスケジュール設定

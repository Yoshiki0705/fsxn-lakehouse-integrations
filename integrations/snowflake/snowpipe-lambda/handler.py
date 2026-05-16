"""
Snowpipe Lambda Polling Function

Detects new files on FSxN via S3 Access Point and publishes notifications
to SNS for Snowpipe auto-ingest. Required because FSxN S3 AP does not
support native S3 Event Notifications.

Architecture:
    EventBridge (every 1-5 min) → This Lambda → List new files → SNS → Snowpipe

Environment Variables:
    S3_ACCESS_POINT_ALIAS: S3 AP alias (bucket-style access)
    SNS_TOPIC_ARN: SNS Topic ARN for Snowpipe notifications
    PREFIX: S3 key prefix to monitor (default: "bronze/events/")
    POLLING_INTERVAL_MINUTES: How far back to look for new files (default: 5)
    STATE_TABLE: DynamoDB table for tracking last-seen files (optional)
"""

import json
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Configuration from environment
S3_AP_ALIAS = os.environ["S3_ACCESS_POINT_ALIAS"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]
PREFIX = os.environ.get("PREFIX", "bronze/events/")
POLLING_INTERVAL = int(os.environ.get("POLLING_INTERVAL_MINUTES", "5"))
STATE_TABLE = os.environ.get("STATE_TABLE", "")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

# AWS clients
s3 = boto3.client("s3", region_name=AWS_REGION)
sns = boto3.client("sns", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION) if STATE_TABLE else None


def get_last_processed_time() -> datetime:
    """Get the last processed timestamp from DynamoDB or use polling interval."""
    if STATE_TABLE and dynamodb:
        try:
            table = dynamodb.Table(STATE_TABLE)
            response = table.get_item(
                Key={"partition_key": "snowpipe_state", "sort_key": PREFIX}
            )
            if "Item" in response:
                return datetime.fromisoformat(response["Item"]["last_processed"])
        except Exception as e:
            logger.warning(f"Failed to read state from DynamoDB: {e}")

    # Fallback: look back by polling interval
    return datetime.now(timezone.utc) - timedelta(minutes=POLLING_INTERVAL)


def update_last_processed_time(timestamp: datetime) -> None:
    """Update the last processed timestamp in DynamoDB."""
    if STATE_TABLE and dynamodb:
        try:
            table = dynamodb.Table(STATE_TABLE)
            table.put_item(
                Item={
                    "partition_key": "snowpipe_state",
                    "sort_key": PREFIX,
                    "last_processed": timestamp.isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to update state in DynamoDB: {e}")


def list_new_files(cutoff_time: datetime) -> list[dict]:
    """List files modified after cutoff_time via S3 AP."""
    new_files = []
    continuation_token = None

    while True:
        kwargs = {
            "Bucket": S3_AP_ALIAS,
            "Prefix": PREFIX,
            "MaxKeys": 1000,
        }
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token

        response = s3.list_objects_v2(**kwargs)

        for obj in response.get("Contents", []):
            last_modified = obj["LastModified"]
            if last_modified.replace(tzinfo=timezone.utc) > cutoff_time.replace(
                tzinfo=timezone.utc
            ):
                new_files.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": last_modified.isoformat(),
                    }
                )

        if response.get("IsTruncated"):
            continuation_token = response["NextContinuationToken"]
        else:
            break

    return new_files


def publish_to_sns(new_files: list[dict]) -> int:
    """Publish file notifications to SNS for Snowpipe."""
    if not new_files:
        return 0

    # Snowpipe expects S3 event notification format
    # Batch files into groups of 100 (SNS message size limit)
    batch_size = 100
    published = 0

    for i in range(0, len(new_files), batch_size):
        batch = new_files[i : i + batch_size]

        message = {
            "Records": [
                {
                    "eventVersion": "2.1",
                    "eventSource": "aws:s3",
                    "eventName": "ObjectCreated:Put",
                    "eventTime": file["last_modified"],
                    "s3": {
                        "bucket": {"name": S3_AP_ALIAS},
                        "object": {
                            "key": file["key"],
                            "size": file["size"],
                        },
                    },
                }
                for file in batch
            ]
        }

        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps(message),
            Subject="FSxN Snowpipe Notification",
        )
        published += len(batch)

    return published


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler — detect new files and notify Snowpipe."""
    logger.info(f"Starting Snowpipe polling for prefix: {PREFIX}")

    # Get cutoff time
    cutoff_time = get_last_processed_time()
    logger.info(f"Looking for files modified after: {cutoff_time.isoformat()}")

    # List new files
    new_files = list_new_files(cutoff_time)
    logger.info(f"Found {len(new_files)} new files")

    # Publish to SNS
    published = 0
    if new_files:
        published = publish_to_sns(new_files)
        logger.info(f"Published {published} file notifications to SNS")

        # Update state
        latest_time = max(
            datetime.fromisoformat(f["last_modified"]) for f in new_files
        )
        update_last_processed_time(latest_time)

    return {
        "statusCode": 200,
        "body": {
            "prefix": PREFIX,
            "cutoff_time": cutoff_time.isoformat(),
            "new_files_found": len(new_files),
            "notifications_published": published,
        },
    }

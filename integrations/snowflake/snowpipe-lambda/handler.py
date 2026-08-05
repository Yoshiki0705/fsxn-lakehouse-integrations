"""
Snowpipe Lambda Polling Function

Detects new files on FSx for ONTAP via S3 Access Point and publishes notifications
to SNS for Snowpipe auto-ingest. Required because FSx for ONTAP S3 AP does not
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
    """Get the last processed timestamp from DynamoDB, or fall back to a window.

    !! DATA LOSS WARNING (DEFECT-2, verified 2026-08-05)
    The fallback below returns ``now - POLLING_INTERVAL``. Because that cutoff
    tracks wall clock, any object whose LastModified predates it is skipped and
    never revisited. Reproduced: an object written at 05:07:52Z was invisible to
    an invocation at 05:09:33Z whose cutoff was 05:08:33Z.

    Set STATE_TABLE to use the DynamoDB checkpoint instead. Note that
    template.yaml does not currently expose STATE_TABLE, so a
    CloudFormation-deployed poller always runs in the lossy mode.

    See integrations/snowflake/docs/en/snowpipe-verification-results.md.
    """
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

    # Fallback: look back by polling interval. Lossy — see the docstring.
    logger.warning(
        "STATE_TABLE not configured: falling back to a %d-minute lookback "
        "window. Objects older than this window will never be notified "
        "(DEFECT-2). Configure STATE_TABLE for at-least-once delivery.",
        POLLING_INTERVAL,
    )
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
    """Publish synthesized S3-event-shaped notifications to SNS for Snowpipe.

    !! UNVERIFIED AND INCOMPLETE (DEFECT-3 / DEFECT-4, reviewed 2026-08-05)

    Whether Snowflake accepts a *synthesized* notification on a pipe's
    notification_channel and triggers COPY has never been tested. That is the
    deciding unknown for this whole pattern.

    Two known gaps in the payload built below:

    * Missing fields that a genuine S3 event notification carries: awsRegion,
      s3.s3SchemaVersion, s3.configurationId, s3.bucket.ownerIdentity,
      s3.bucket.arn, s3.object.eTag, s3.object.sequencer. eTag and sequencer are
      the ones most likely to matter, since a consumer would use them for
      deduplication and ordering.

    * s3.bucket.name is populated straight from S3_ACCESS_POINT_ALIAS. Supplying
      the Access Point ARN therefore emits an ARN where a bucket name belongs,
      which is unlikely to match a stage URL of the form s3://<bucket>/<path>.
      Supply the Access Point *alias*, not the ARN.

    See integrations/snowflake/docs/en/snowpipe-verification-results.md.
    """
    if not new_files:
        return 0

    if S3_AP_ALIAS.startswith("arn:"):
        logger.warning(
            "S3_ACCESS_POINT_ALIAS looks like an ARN (%s). Snowpipe matches "
            "notifications against the pipe's stage location, so an ARN in "
            "s3.bucket.name will probably not match. Supply the Access Point "
            "alias instead (DEFECT-4).",
            S3_AP_ALIAS,
        )

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
            Subject="FSx for ONTAP Snowpipe Notification",
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

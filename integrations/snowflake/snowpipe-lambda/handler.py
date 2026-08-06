"""
Snowpipe Lambda Polling Function

Detects new files on FSx for ONTAP via S3 Access Point and publishes notifications
to SNS for Snowpipe auto-ingest. Required because FSx for ONTAP S3 AP does not
support native S3 Event Notifications.

Architecture:
    EventBridge (every 1-5 min) → This Lambda → List new files → SNS → Snowpipe

Environment Variables:
    S3_ACCESS_POINT_ALIAS: S3 AP alias, bucket-style. Must be the alias, NOT the
        Access Point ARN. The alias is copied verbatim into s3.bucket.name of the
        synthesized notification, and Snowpipe matches that string against the
        bucket in its stage URL. An ARN there causes Snowpipe to accept the
        message and then discard it with no error anywhere. Verified 2026-08-06.
    SNS_TOPIC_ARN: SNS Topic ARN for Snowpipe notifications. The same topic must
        be named in the pipe's AWS_SNS_TOPIC parameter, which is what makes
        Snowflake subscribe its managed SQS queue to it. You cannot create that
        subscription yourself.
    PREFIX: S3 key prefix to monitor (default: "bronze/events/")
    POLLING_INTERVAL_MINUTES: How far back to look for new files (default: 5).
        Only used when STATE_TABLE is unset, and lossy — see
        get_last_processed_time().
    STATE_TABLE: DynamoDB table for tracking last-seen files. Strongly
        recommended; without it objects older than the lookback window are never
        notified.
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

# Fail at init rather than silently dropping every notification.
#
# ListObjectsV2 accepts either the Access Point ARN or its alias as Bucket, so a
# misconfigured ARN here would let the poller appear to work: it lists objects,
# publishes to SNS, and reports success. Snowpipe then receives each message and
# discards it because s3.bucket.name does not match the stage URL — without
# raising an error in SYSTEM$PIPE_STATUS or COPY_HISTORY. An init failure is
# loud; that silent mode is not. Verified 2026-08-06, see
# integrations/snowflake/docs/en/snowpipe-verification-results.md
if S3_AP_ALIAS.startswith("arn:"):
    raise ValueError(
        "S3_ACCESS_POINT_ALIAS must be the S3 Access Point alias, not its ARN. "
        f"Received an ARN: {S3_AP_ALIAS}. The value is written verbatim into "
        "s3.bucket.name of the synthesized notification and must match the bucket "
        "portion of the pipe's stage URL (s3://<alias>/<path>). With an ARN, "
        "Snowpipe silently discards every notification. Use the alias, which "
        "looks like: <name>-<random>-ext-s3alias"
    )
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


def _as_utc(value: datetime) -> datetime:
    """Normalize a datetime to UTC.

    Naive values are assumed to be UTC; aware values are converted. Using
    ``replace(tzinfo=utc)`` on an aware non-UTC value would silently shift the
    instant, which would move the polling cutoff and drop or duplicate files.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def list_new_files(cutoff_time: datetime) -> list[dict]:
    """List files modified after cutoff_time via S3 AP."""
    new_files = []
    continuation_token = None
    cutoff_utc = _as_utc(cutoff_time)

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
            last_modified = _as_utc(obj["LastModified"])
            if last_modified > cutoff_utc:
                new_files.append(
                    {
                        "key": obj["Key"],
                        "size": obj["Size"],
                        "last_modified": last_modified.isoformat(),
                        # ListObjectsV2 returns ETag quoted; strip to match the
                        # unquoted form that real S3 event notifications carry.
                        "etag": obj.get("ETag", "").strip('"'),
                    }
                )

        if response.get("IsTruncated"):
            continuation_token = response["NextContinuationToken"]
        else:
            break

    return new_files


# SNS caps a single publish at 256 KiB. Stay under it with margin rather than
# assuming a fixed record count, because object keys vary in length.
SNS_MAX_MESSAGE_BYTES = 200_000
SNS_MAX_RECORDS_PER_MESSAGE = 100


def _synthesize_sequencer(last_modified_iso: str) -> str:
    """Build a stand-in for the S3 `sequencer` field.

    Real S3 supplies a hex token that increases monotonically for a given key, so
    consumers can order overlapping events. There is no equivalent available when
    the notification is synthesized from a listing, so this derives one from the
    object's LastModified in milliseconds.

    The value orders correctly for repeated writes to the same key at
    millisecond-or-coarser granularity. It is not a substitute for the real thing:
    two writes inside the same millisecond produce the same token.
    """
    ts = _as_utc(datetime.fromisoformat(last_modified_iso))
    return format(int(ts.timestamp() * 1000), "X").zfill(16)


def _build_record(file: dict) -> dict:
    """Build one synthesized S3 ObjectCreated record.

    Field set mirrors a genuine S3 event notification. Which fields Snowpipe
    actually requires was not isolated during verification — only s3.bucket.name
    was varied deliberately — so the full set is sent rather than guessing at a
    minimum.
    """
    return {
        "eventVersion": "2.1",
        "eventSource": "aws:s3",
        "awsRegion": AWS_REGION,
        "eventTime": file["last_modified"],
        "eventName": "ObjectCreated:Put",
        "userIdentity": {"principalId": "AWS:fsx-ontap-s3ap-poller"},
        "requestParameters": {"sourceIPAddress": "0.0.0.0"},
        "responseElements": {
            "x-amz-request-id": "synthesized",
            "x-amz-id-2": "synthesized",
        },
        "s3": {
            "s3SchemaVersion": "1.0",
            "configurationId": "fsx-ontap-s3ap-poller",
            "bucket": {
                # Must be the Access Point alias. Enforced at module init.
                "name": S3_AP_ALIAS,
                "ownerIdentity": {"principalId": "synthesized"},
                "arn": f"arn:aws:s3:::{S3_AP_ALIAS}",
            },
            "object": {
                "key": file["key"],
                "size": file["size"],
                "eTag": file.get("etag", ""),
                "sequencer": _synthesize_sequencer(file["last_modified"]),
            },
        },
    }


def _batch_records(records: list[dict]) -> list[list[dict]]:
    """Split records into publishable batches bounded by count and byte size."""
    batches: list[list[dict]] = []
    current: list[dict] = []
    current_bytes = 0

    for record in records:
        record_bytes = len(json.dumps(record))
        too_many = len(current) >= SNS_MAX_RECORDS_PER_MESSAGE
        too_big = current and (current_bytes + record_bytes) > SNS_MAX_MESSAGE_BYTES
        if too_many or too_big:
            batches.append(current)
            current = []
            current_bytes = 0
        current.append(record)
        current_bytes += record_bytes

    if current:
        batches.append(current)
    return batches


def publish_to_sns(new_files: list[dict]) -> int:
    """Publish synthesized S3-event-shaped notifications to SNS for Snowpipe.

    Verified working 2026-08-06: Snowpipe accepted a synthesized notification of
    this shape and ran COPY, with COPY_HISTORY attributing the load to the pipe.
    Notification-to-loaded-row latency was about half a second.

    Three conditions outside this function must also hold:

    1. The pipe's stage sets AWS_ACCESS_POINT_ARN. Without it every read fails
       even though LIST succeeds.
    2. The pipe sets AWS_SNS_TOPIC to SNS_TOPIC_ARN. That is what makes Snowflake
       subscribe its managed SQS queue to the topic; the subscription cannot be
       created from this side.
    3. The topic policy grants sns:Subscribe to Snowflake's IAM user, the
       STORAGE_AWS_IAM_USER_ARN from DESC STORAGE INTEGRATION.

    See integrations/snowflake/docs/en/snowpipe-verification-results.md.
    """
    if not new_files:
        return 0

    records = [_build_record(file) for file in new_files]
    published = 0

    for batch in _batch_records(records):
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=json.dumps({"Records": batch}),
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
            _as_utc(datetime.fromisoformat(f["last_modified"])) for f in new_files
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

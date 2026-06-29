"""STS credential vending for OpenSharing Volumes."""

import json
import logging
import time
from urllib.parse import urlparse

import boto3

from .config import AppConfig, VolumeConfig

logger = logging.getLogger(__name__)


def _parse_s3_location(storage_location: str) -> tuple[str, str]:
    """Parse s3://bucket-or-alias/prefix/ into (bucket_or_alias, prefix)."""
    parsed = urlparse(storage_location)
    bucket = parsed.netloc
    prefix = parsed.path.lstrip("/")
    return bucket, prefix


def _is_access_point_alias(bucket: str) -> bool:
    """Detect if the bucket name is an S3 Access Point alias (ends with -s3alias)."""
    return bucket.endswith("-s3alias") or bucket.endswith("-ext-s3alias")


def _build_scope_policy(bucket: str, prefix: str, region: str, account_id: str) -> str:
    """Build an IAM policy scoped to the volume's prefix.

    For S3 Access Points, the ARN format is:
      arn:aws:s3:<region>:<account>:accesspoint/<ap-name>/object/<key>
    For regular S3 buckets:
      arn:aws:s3:::<bucket>/<key>

    When using AP aliases (the bucket looks like <name>-<hash>-ext-s3alias),
    we use wildcard AP ARN patterns that match any AP in the account.
    """
    if _is_access_point_alias(bucket):
        # S3 Access Point — use wildcard AP ARN format
        # This matches any access point in any region/account
        # The actual scoping comes from the prefix condition
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowGetObjectPrefix",
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": f"arn:aws:s3:*:*:accesspoint/*/object/{prefix}*",
                },
                {
                    "Sid": "AllowListPrefix",
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket"],
                    "Resource": "arn:aws:s3:*:*:accesspoint/*",
                    "Condition": {"StringLike": {"s3:prefix": [f"{prefix}*"]}},
                },
            ],
        }
    else:
        # Standard S3 bucket
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowListPrefix",
                    "Effect": "Allow",
                    "Action": ["s3:ListBucket"],
                    "Resource": f"arn:aws:s3:::{bucket}",
                    "Condition": {"StringLike": {"s3:prefix": [f"{prefix}*"]}},
                },
                {
                    "Sid": "AllowGetObjectPrefix",
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:GetObjectVersion"],
                    "Resource": f"arn:aws:s3:::{bucket}/{prefix}*",
                },
            ],
        }
    return json.dumps(policy)


def generate_temporary_credentials(
    config: AppConfig,
    volume: VolumeConfig,
    recipient_name: str,
) -> dict:
    """Generate scoped STS credentials for a volume.

    Strategy:
    - If sts_role_arn is configured: Use AssumeRole with inline session policy (works in Lambda)
    - Otherwise: Use GetFederationToken with inline policy (requires IAM user credentials)

    Both approaches scope the resulting credentials to the volume's prefix only.
    """
    bucket, prefix = _parse_s3_location(volume.storage_location)
    region = config.server.aws_region

    sts_client = boto3.client("sts", region_name=region)
    account_id = sts_client.get_caller_identity()["Account"]

    scope_policy = _build_scope_policy(bucket, prefix, region, account_id)
    duration = config.server.credential_duration_seconds

    # Use a descriptive session name for CloudTrail audit
    session_name = f"os-{recipient_name}-{volume.name}"[:64]

    logger.info(
        "Vending credentials",
        extra={
            "recipient": recipient_name,
            "volume": volume.name,
            "bucket": bucket,
            "prefix": prefix,
            "duration_seconds": duration,
            "method": "AssumeRole" if config.server.sts_role_arn else "GetFederationToken",
        },
    )

    if config.server.sts_role_arn:
        # Lambda environment: AssumeRole with session policy
        response = sts_client.assume_role(
            RoleArn=config.server.sts_role_arn,
            RoleSessionName=session_name,
            Policy=scope_policy,
            DurationSeconds=duration,
        )
    else:
        # IAM user environment: GetFederationToken
        response = sts_client.get_federation_token(
            Name=session_name[:32],
            Policy=scope_policy,
            DurationSeconds=duration,
        )

    credentials = response["Credentials"]
    expiration_epoch_ms = int(credentials["Expiration"].timestamp() * 1000)

    return {
        "awsTempCredentials": {
            "accessKeyId": credentials["AccessKeyId"],
            "secretAccessKey": credentials["SecretAccessKey"],
            "sessionToken": credentials["SessionToken"],
        },
        "expirationTime": expiration_epoch_ms,
    }

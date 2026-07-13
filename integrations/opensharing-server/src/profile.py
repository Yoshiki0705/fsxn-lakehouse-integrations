"""Generate OpenSharing credential profiles for Databricks CREATE PROVIDER.

The profile file (config.share / profile.json) is the standard mechanism for
a non-Databricks recipient to connect to an OpenSharing server. Databricks
uses this file with CREATE PROVIDER to establish a sharing connection.

Profile format (Delta Sharing / OpenSharing specification):
{
  "shareCredentialsVersion": 1,
  "endpoint": "https://<server-url>/api/v1",
  "bearerToken": "<token>",
  "expirationTime": "<ISO 8601 timestamp or empty>"
}
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from .config import AppConfig

logger = logging.getLogger(__name__)

# Profile version — matches Delta Sharing / OpenSharing spec
SHARE_CREDENTIALS_VERSION = 1


def generate_profile(
    config: AppConfig,
    endpoint: str,
    recipient_name: str,
    expiration_time: str | None = None,
) -> dict:
    """Generate an OpenSharing credential profile for a specific recipient.

    Args:
        config: The server's AppConfig (contains auth tokens).
        endpoint: The full base URL of the OpenSharing server
                  (e.g., https://abc123.lambda-url.ap-northeast-1.on.aws/api/v1).
        recipient_name: The recipient name to generate the profile for.
        expiration_time: Optional ISO 8601 expiration timestamp.
                         If None, the token does not expire (not recommended for production).

    Returns:
        A dict matching the OpenSharing credential profile schema.

    Raises:
        ValueError: If the recipient is not found in the config.
    """
    # Find the token for this recipient
    token_config = next(
        (t for t in config.auth.tokens if t.recipient == recipient_name),
        None,
    )
    if not token_config:
        raise ValueError(f"Recipient '{recipient_name}' not found in server configuration")

    # Ensure endpoint doesn't have trailing slash
    endpoint = endpoint.rstrip("/")

    # Build the profile
    profile = {
        "shareCredentialsVersion": SHARE_CREDENTIALS_VERSION,
        "endpoint": endpoint,
        "bearerToken": token_config.token,
    }

    if expiration_time:
        profile["expirationTime"] = expiration_time

    logger.info(
        f"Generated profile for recipient={recipient_name}, endpoint={endpoint}"
    )
    return profile


def save_profile(
    profile: dict,
    output_path: str | Path,
) -> Path:
    """Save the credential profile to a file.

    Args:
        profile: The profile dict from generate_profile().
        output_path: Path to write the profile file (e.g., ./factory.share).

    Returns:
        The resolved Path where the file was written.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(profile, f, indent=2)

    logger.info(f"Profile saved to {path}")
    return path


def generate_all_profiles(
    config: AppConfig,
    endpoint: str,
    output_dir: str | Path = "./profiles",
    expiration_time: str | None = None,
) -> list[Path]:
    """Generate credential profiles for all configured recipients.

    Args:
        config: The server's AppConfig.
        endpoint: The full base URL of the OpenSharing server.
        output_dir: Directory to write profile files.
        expiration_time: Optional expiration for all profiles.

    Returns:
        List of paths to generated profile files.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for token_config in config.auth.tokens:
        profile = generate_profile(
            config=config,
            endpoint=endpoint,
            recipient_name=token_config.recipient,
            expiration_time=expiration_time,
        )

        # Name the file: <recipient>.share
        file_path = output_dir / f"{token_config.recipient}.share"
        save_profile(profile, file_path)
        paths.append(file_path)

    logger.info(f"Generated {len(paths)} profiles in {output_dir}")
    return paths

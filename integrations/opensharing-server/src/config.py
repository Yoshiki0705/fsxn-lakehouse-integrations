"""Configuration loader for OpenSharing Volumes server."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class VolumeConfig:
    name: str
    storage_location: str
    comment: str = ""
    id: str = ""


@dataclass
class SchemaConfig:
    name: str
    volumes: list[VolumeConfig] = field(default_factory=list)
    comment: str = ""


@dataclass
class ShareConfig:
    name: str
    schemas: list[SchemaConfig] = field(default_factory=list)
    comment: str = ""


@dataclass
class TokenConfig:
    token: str
    recipient: str
    shares: list[str] = field(default_factory=list)


@dataclass
class AuthConfig:
    tokens: list[TokenConfig] = field(default_factory=list)


@dataclass
class ServerConfig:
    credential_duration_seconds: int = 900
    aws_region: str = "ap-northeast-1"
    sts_role_arn: str | None = None


@dataclass
class AppConfig:
    server: ServerConfig
    auth: AuthConfig
    shares: list[ShareConfig]

    def find_share(self, share_name: str) -> ShareConfig | None:
        return next((s for s in self.shares if s.name.lower() == share_name.lower()), None)

    def find_schema(self, share_name: str, schema_name: str) -> SchemaConfig | None:
        share = self.find_share(share_name)
        if not share:
            return None
        return next((sc for sc in share.schemas if sc.name.lower() == schema_name.lower()), None)

    def find_volume(self, share_name: str, schema_name: str, volume_name: str) -> VolumeConfig | None:
        schema = self.find_schema(share_name, schema_name)
        if not schema:
            return None
        return next((v for v in schema.volumes if v.name.lower() == volume_name.lower()), None)

    def get_recipient_for_token(self, token: str) -> TokenConfig | None:
        return next((t for t in self.auth.tokens if t.token == token), None)


def load_config(config_path: str | Path) -> AppConfig:
    """Load configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    server = ServerConfig(
        credential_duration_seconds=raw.get("server", {}).get("credential_duration_seconds", 900),
        aws_region=raw.get("server", {}).get("aws_region", "ap-northeast-1"),
        sts_role_arn=raw.get("server", {}).get("sts_role_arn"),
    )

    tokens = [
        TokenConfig(token=t["token"], recipient=t["recipient"], shares=t.get("shares", []))
        for t in raw.get("auth", {}).get("tokens", [])
    ]
    auth = AuthConfig(tokens=tokens)

    shares = []
    for share_raw in raw.get("shares", []):
        schemas = []
        for schema_raw in share_raw.get("schemas", []):
            volumes = [
                VolumeConfig(
                    name=v["name"],
                    storage_location=v["storage_location"],
                    comment=v.get("comment", ""),
                    id=v.get("id", ""),
                )
                for v in schema_raw.get("volumes", [])
            ]
            schemas.append(SchemaConfig(name=schema_raw["name"], volumes=volumes, comment=schema_raw.get("comment", "")))
        shares.append(ShareConfig(name=share_raw["name"], schemas=schemas, comment=share_raw.get("comment", "")))

    return AppConfig(server=server, auth=auth, shares=shares)

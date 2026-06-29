"""OpenSharing Volumes API — FastAPI server implementation.

Implements the Volumes endpoints from the OpenSharing protocol specification:
https://github.com/OpenSharing-IO/OpenSharing/blob/main/spec/protocols/VOLUMES.md
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import JSONResponse
from opentelemetry import trace, metrics
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.sdk.resources import Resource

from .config import AppConfig, load_config
from .credentials import generate_temporary_credentials

logger = logging.getLogger(__name__)

# --- Configuration ---
CONFIG_PATH = os.environ.get(
    "OPENSHARING_CONFIG", str(Path(__file__).parent.parent / "config" / "volumes.yaml")
)

_config: AppConfig | None = None

# --- OpenTelemetry Setup ---
_OTEL_SERVICE_NAME = "opensharing-volumes-server"

resource = Resource.create({"service.name": _OTEL_SERVICE_NAME, "service.version": "0.1.0"})

# Traces
_tracer_provider = TracerProvider(resource=resource)
if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
    # If OTLP endpoint configured, use OTLP exporter (added via opentelemetry-exporter-otlp)
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        _tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
    except ImportError:
        _tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
else:
    # Default: console exporter for development
    _tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

trace.set_tracer_provider(_tracer_provider)
tracer = trace.get_tracer(__name__)

# Metrics — disable periodic export in test mode to avoid I/O errors on teardown
if os.environ.get("TESTING") == "1":
    _meter_provider = MeterProvider(resource=resource)
else:
    _metric_reader = PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=60000)
    _meter_provider = MeterProvider(resource=resource, metric_readers=[_metric_reader])
metrics.set_meter_provider(_meter_provider)
meter = metrics.get_meter(__name__)

# Custom metrics
credential_vend_counter = meter.create_counter(
    "opensharing.credentials.issued",
    description="Number of temporary credentials issued",
    unit="1",
)
credential_vend_duration = meter.create_histogram(
    "opensharing.credentials.duration_ms",
    description="Time to issue temporary credentials",
    unit="ms",
)
auth_failure_counter = meter.create_counter(
    "opensharing.auth.failures",
    description="Number of authentication/authorization failures",
    unit="1",
)


def get_config() -> AppConfig:
    global _config
    if _config is None:
        _config = load_config(CONFIG_PATH)
        logger.info(f"Loaded config: {len(_config.shares)} shares")
    return _config


# --- Auth ---
def _authenticate(authorization: str | None) -> str:
    """Validate bearer token and return recipient name."""
    if not authorization or not authorization.startswith("Bearer "):
        auth_failure_counter.add(1, {"reason": "missing_token"})
        raise HTTPException(status_code=401, detail={"errorCode": "UNAUTHENTICATED", "message": "Missing or invalid Authorization header"})

    token = authorization.removeprefix("Bearer ").strip()
    config = get_config()
    recipient = config.get_recipient_for_token(token)
    if not recipient:
        auth_failure_counter.add(1, {"reason": "invalid_token"})
        raise HTTPException(status_code=401, detail={"errorCode": "UNAUTHENTICATED", "message": "Invalid bearer token"})

    return recipient.recipient


def _authorize_share(recipient_name: str, share_name: str) -> None:
    """Check if recipient has access to the share."""
    config = get_config()
    recipient = next((t for t in config.auth.tokens if t.recipient == recipient_name), None)
    if not recipient or share_name.lower() not in [s.lower() for s in recipient.shares]:
        auth_failure_counter.add(1, {"reason": "forbidden_share", "recipient": recipient_name, "share": share_name})
        raise HTTPException(status_code=403, detail={"errorCode": "FORBIDDEN", "message": f"Recipient '{recipient_name}' does not have access to share '{share_name}'"})


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load config on startup."""
    get_config()
    logger.info("OpenSharing Volumes server started")
    yield
    logger.info("OpenSharing Volumes server stopped")


# --- App ---
app = FastAPI(
    title="OpenSharing Volumes Reference Server",
    description="Reference implementation of the OpenSharing Volumes API for S3-compatible backends",
    version="0.1.0",
    lifespan=lifespan,
)

# Instrument FastAPI with OpenTelemetry (automatic span creation for all endpoints)
FastAPIInstrumentor.instrument_app(app)


# --- Health ---
@app.get("/health")
async def health():
    return {"status": "healthy", "version": "0.1.0", "protocol": "OpenSharing Volumes"}


# --- Shares ---
@app.get("/api/v1/shares")
async def list_shares(
    authorization: str | None = Header(default=None),
    maxResults: int | None = Query(default=None),
    pageToken: str | None = Query(default=None),
):
    recipient = _authenticate(authorization)
    config = get_config()

    # Filter shares by recipient access
    recipient_config = config.get_recipient_for_token(
        next(t.token for t in config.auth.tokens if t.recipient == recipient)
    )
    allowed = [s.lower() for s in (recipient_config.shares if recipient_config else [])]
    items = [{"name": s.name, "comment": s.comment} for s in config.shares if s.name.lower() in allowed]

    return {"items": items}


# --- Volumes ---
@app.get("/api/v1/shares/{share}/all-volumes")
async def list_all_volumes(
    share: str,
    authorization: str | None = Header(default=None),
    maxResults: int | None = Query(default=None),
    pageToken: str | None = Query(default=None),
):
    recipient = _authenticate(authorization)
    _authorize_share(recipient, share)
    config = get_config()

    share_config = config.find_share(share)
    if not share_config:
        raise HTTPException(status_code=404, detail={"errorCode": "NOT_FOUND", "message": f"Share '{share}' not found"})

    items = []
    for schema in share_config.schemas:
        for volume in schema.volumes:
            items.append({
                "name": volume.name,
                "schema": schema.name,
                "share": share_config.name,
                "id": volume.id or f"{share_config.name}.{schema.name}.{volume.name}",
                "storageLocation": volume.storage_location,
            })

    return {"items": items}


@app.get("/api/v1/shares/{share}/schemas/{schema}/volumes")
async def list_schema_volumes(
    share: str,
    schema: str,
    authorization: str | None = Header(default=None),
    maxResults: int | None = Query(default=None),
    pageToken: str | None = Query(default=None),
):
    recipient = _authenticate(authorization)
    _authorize_share(recipient, share)
    config = get_config()

    schema_config = config.find_schema(share, schema)
    if not schema_config:
        raise HTTPException(status_code=404, detail={"errorCode": "NOT_FOUND", "message": f"Schema '{schema}' not found in share '{share}'"})

    items = [
        {
            "name": v.name,
            "schema": schema_config.name,
            "share": share,
            "id": v.id or f"{share}.{schema_config.name}.{v.name}",
            "storageLocation": v.storage_location,
        }
        for v in schema_config.volumes
    ]

    return {"items": items}


@app.get("/api/v1/shares/{share}/schemas/{schema}/volumes/{volume}")
async def get_volume(
    share: str,
    schema: str,
    volume: str,
    authorization: str | None = Header(default=None),
):
    recipient = _authenticate(authorization)
    _authorize_share(recipient, share)
    config = get_config()

    volume_config = config.find_volume(share, schema, volume)
    if not volume_config:
        raise HTTPException(status_code=404, detail={"errorCode": "NOT_FOUND", "message": f"Volume '{volume}' not found"})

    return {
        "name": volume_config.name,
        "schema": schema,
        "share": share,
        "id": volume_config.id or f"{share}.{schema}.{volume_config.name}",
        "storageLocation": volume_config.storage_location,
    }


@app.post("/api/v1/shares/{share}/schemas/{schema}/volumes/{volume}/temporary-volume-credentials")
async def generate_volume_credentials(
    share: str,
    schema: str,
    volume: str,
    authorization: str | None = Header(default=None),
):
    recipient = _authenticate(authorization)
    _authorize_share(recipient, share)
    config = get_config()

    volume_config = config.find_volume(share, schema, volume)
    if not volume_config:
        raise HTTPException(status_code=404, detail={"errorCode": "NOT_FOUND", "message": f"Volume '{volume}' not found"})

    with tracer.start_as_current_span(
        "credential_vending",
        attributes={
            "opensharing.recipient": recipient,
            "opensharing.share": share,
            "opensharing.schema": schema,
            "opensharing.volume": volume,
            "opensharing.storage_location": volume_config.storage_location,
        },
    ) as span:
        start = time.time()
        try:
            creds = generate_temporary_credentials(config, volume_config, recipient)
            elapsed_ms = (time.time() - start) * 1000

            # Record metrics
            credential_vend_counter.add(1, {"recipient": recipient, "volume": volume})
            credential_vend_duration.record(elapsed_ms, {"recipient": recipient, "volume": volume})

            span.set_attribute("opensharing.credential_vend_ms", elapsed_ms)
            span.set_attribute("opensharing.expiration_time", creds["expirationTime"])

            logger.info(
                f"Credentials issued: recipient={recipient}, volume={volume}, elapsed={elapsed_ms:.0f}ms"
            )
            return creds
        except HTTPException:
            raise
        except Exception as e:
            elapsed_ms = (time.time() - start) * 1000
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(e))
            logger.error(f"Credential vending failed: {e}")
            raise HTTPException(status_code=500, detail={"errorCode": "INTERNAL_ERROR", "message": str(e)})

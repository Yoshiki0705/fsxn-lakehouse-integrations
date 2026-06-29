"""Tests for OpenSharing Volumes server — API contract + auth."""

import os
import pytest
from httpx import ASGITransport, AsyncClient

# Set config path before importing app
os.environ["OPENSHARING_CONFIG"] = str(
    os.path.join(os.path.dirname(__file__), "..", "config", "volumes.yaml")
)
os.environ["TESTING"] = "1"

from src.server import app  # noqa: E402


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["protocol"] == "OpenSharing Volumes"


@pytest.mark.asyncio
async def test_unauthenticated_request(client):
    resp = await client.get("/api/v1/shares")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token(client):
    resp = await client.get(
        "/api/v1/shares",
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_shares(client):
    resp = await client.get(
        "/api/v1/shares",
        headers={"Authorization": "Bearer test-quality-team-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "factory"


@pytest.mark.asyncio
async def test_list_all_volumes(client):
    resp = await client.get(
        "/api/v1/shares/factory/all-volumes",
        headers={"Authorization": "Bearer test-quality-team-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 3  # inspection-images, sensor-data, delta-lake


@pytest.mark.asyncio
async def test_list_schema_volumes(client):
    resp = await client.get(
        "/api/v1/shares/factory/schemas/quality/volumes",
        headers={"Authorization": "Bearer test-quality-team-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    names = [v["name"] for v in data["items"]]
    assert "inspection-images" in names
    assert "sensor-data" in names


@pytest.mark.asyncio
async def test_get_volume(client):
    resp = await client.get(
        "/api/v1/shares/factory/schemas/quality/volumes/sensor-data",
        headers={"Authorization": "Bearer test-quality-team-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "sensor-data"
    assert data["share"] == "factory"
    assert data["schema"] == "quality"
    assert "sensor-data/" in data["storageLocation"]


@pytest.mark.asyncio
async def test_volume_not_found(client):
    resp = await client.get(
        "/api/v1/shares/factory/schemas/quality/volumes/nonexistent",
        headers={"Authorization": "Bearer test-quality-team-token"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_unauthorized_share_access(client):
    """Token with no share access should get 403."""
    resp = await client.get(
        "/api/v1/shares/factory/all-volumes",
        headers={"Authorization": "Bearer test-unauthorized-token"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_case_insensitive_lookup(client):
    """Share/schema/volume lookups should be case-insensitive."""
    resp = await client.get(
        "/api/v1/shares/FACTORY/schemas/QUALITY/volumes/SENSOR-DATA",
        headers={"Authorization": "Bearer test-quality-team-token"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "sensor-data"

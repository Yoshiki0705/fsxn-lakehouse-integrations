"""E2E integration test — credential vending against real FSx for ONTAP S3 AP.

Run manually: pytest tests/test_e2e_aws.py -v
Requires: AWS credentials with sts:GetFederationToken permission
"""

import os
import pytest
import boto3
from httpx import ASGITransport, AsyncClient

os.environ["OPENSHARING_CONFIG"] = str(
    os.path.join(os.path.dirname(__file__), "..", "config", "volumes.yaml")
)
os.environ["TESTING"] = "1"

from src.server import app  # noqa: E402


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_e2e_credential_vending_and_data_access(client):
    """Full flow: get credentials → use them to access FSx for ONTAP S3 AP."""

    # Step 1: Request temporary credentials for sensor-data volume
    resp = await client.post(
        "/api/v1/shares/factory/schemas/quality/volumes/sensor-data/temporary-volume-credentials",
        headers={"Authorization": "Bearer test-quality-team-token"},
    )
    assert resp.status_code == 200, f"Credential vending failed: {resp.text}"
    data = resp.json()

    # Verify response structure matches OpenSharing spec
    assert "awsTempCredentials" in data
    assert "expirationTime" in data
    creds = data["awsTempCredentials"]
    assert "accessKeyId" in creds
    assert "secretAccessKey" in creds
    assert "sessionToken" in creds
    assert data["expirationTime"] > 0

    # Step 2: Use vended credentials to access FSx for ONTAP S3 AP
    s3 = boto3.client(
        "s3",
        region_name="ap-northeast-1",
        aws_access_key_id=creds["accessKeyId"],
        aws_secret_access_key=creds["secretAccessKey"],
        aws_session_token=creds["sessionToken"],
    )

    ap_alias = "verification-tes-fpg5t76dgh3xchkrudk6yc4jhgzz1apn1b-ext-s3alias"

    # ListObjects on allowed prefix
    list_resp = s3.list_objects_v2(Bucket=ap_alias, Prefix="sensor-data/", MaxKeys=5)
    assert "Contents" in list_resp, "ListObjects returned no contents"
    assert len(list_resp["Contents"]) > 0
    print(f"\n  ✅ ListObjects: {len(list_resp['Contents'])} objects in sensor-data/")

    # GetObject on allowed prefix
    first_key = list_resp["Contents"][0]["Key"]
    get_resp = s3.get_object(Bucket=ap_alias, Key=first_key, Range="bytes=0-100")
    assert get_resp["ResponseMetadata"]["HTTPStatusCode"] == 206
    print(f"  ✅ GetObject: {first_key} (HTTP 206 Partial Content)")

    # Step 3: Verify prefix isolation — access DENIED on other prefix
    with pytest.raises(Exception) as exc_info:
        s3.list_objects_v2(Bucket=ap_alias, Prefix="delta-lake/", MaxKeys=1)
    assert "AccessDenied" in str(exc_info.value)
    print("  ✅ Prefix isolation: delta-lake/ AccessDenied (expected)")


@pytest.mark.asyncio
async def test_e2e_credential_vending_inspection_images(client):
    """Verify credential vending for the inspection-images volume (media/ prefix)."""

    resp = await client.post(
        "/api/v1/shares/factory/schemas/quality/volumes/inspection-images/temporary-volume-credentials",
        headers={"Authorization": "Bearer test-quality-team-token"},
    )
    assert resp.status_code == 200
    data = resp.json()
    creds = data["awsTempCredentials"]

    s3 = boto3.client(
        "s3",
        region_name="ap-northeast-1",
        aws_access_key_id=creds["accessKeyId"],
        aws_secret_access_key=creds["secretAccessKey"],
        aws_session_token=creds["sessionToken"],
    )

    ap_alias = "verification-tes-fpg5t76dgh3xchkrudk6yc4jhgzz1apn1b-ext-s3alias"

    # List media files
    list_resp = s3.list_objects_v2(Bucket=ap_alias, Prefix="media/", MaxKeys=5)
    assert "Contents" in list_resp
    print(f"\n  ✅ ListObjects: {len(list_resp['Contents'])} objects in media/")

    # Verify cannot access sensor-data with media credentials
    with pytest.raises(Exception) as exc_info:
        s3.list_objects_v2(Bucket=ap_alias, Prefix="sensor-data/", MaxKeys=1)
    assert "AccessDenied" in str(exc_info.value)
    print("  ✅ Prefix isolation: sensor-data/ AccessDenied with media credentials")

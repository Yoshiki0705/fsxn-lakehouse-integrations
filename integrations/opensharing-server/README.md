# OpenSharing Volumes Reference Server

> A lightweight, OSS reference implementation of the [OpenSharing](https://github.com/OpenSharing-IO/OpenSharing) Volumes API for S3-compatible storage backends — including Amazon FSx for ONTAP S3 Access Points.

## Why This Exists

The OpenSharing specification (Linux Foundation, June 2026) defines a Volumes API for sharing unstructured file collections via temporary cloud credentials. As of June 2026, **no open-source server implements this API**. The only available implementation is built into the Databricks platform.

This reference server fills the gap: a standalone, vendor-neutral server that any storage operator can run to share data via the OpenSharing protocol.

## What It Does

```
┌─────────────────────────────────────────────────────────────────┐
│  OpenSharing Volumes Server (this project)                      │
│                                                                 │
│  1. Recipient authenticates (bearer token)                      │
│  2. Lists available shares / schemas / volumes                  │
│  3. Requests temporary credentials for a volume                 │
│  4. Server calls STS (scoped to volume's prefix)                │
│  5. Recipient uses credentials to access S3 AP directly         │
└─────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  FSx for ONTAP S3 AP          Standard S3 Bucket
  (primary target)             (also supported)
```

## Quick Start (30 minutes)

### Prerequisites

- Python 3.12+
- AWS CLI configured with admin-level access
- An S3 Access Point with data (or FSx for ONTAP S3 AP)
- pip3 available

### 1. Deploy to AWS Lambda

```bash
cd integrations/opensharing-server
chmod +x deploy-lambda.sh

# Deploy (creates CloudFormation stack + Lambda + Function URL)
./deploy-lambda.sh --ap-alias <your-ap-alias-ext-s3alias>

# Example with FSx for ONTAP S3 AP:
./deploy-lambda.sh --ap-alias verification-tes-abc123-ext-s3alias
```

This single command:
1. Deploys a CloudFormation stack (`template.yaml`) with IAM roles and Lambda
2. Generates `config/volumes.yaml` with your AP alias and the vending role ARN
3. Packages and uploads the Lambda code
4. Creates a Function URL endpoint
5. Runs a health check to verify deployment

### 2. Verify

```bash
# Quick smoke test
curl https://<your-function-url>/health

# Full E2E verification (auth, credential vending, data access, prefix isolation)
python3 scripts/verify-deployment.py --url https://<your-function-url>/
```

### 3. Test Credential Vending

```bash
# Get temporary credentials for a volume
curl -X POST -H "Authorization: Bearer test-quality-team-token" \
  https://<your-function-url>/api/v1/shares/factory/schemas/quality/volumes/sensor-data/temporary-volume-credentials
```

### 4. Use Vended Credentials

```python
import boto3

# Use the credentials from step 3 to access FSx for ONTAP S3 AP directly
s3 = boto3.client('s3',
    aws_access_key_id=creds['accessKeyId'],
    aws_secret_access_key=creds['secretAccessKey'],
    aws_session_token=creds['sessionToken'])

response = s3.list_objects_v2(Bucket='<ap-alias>', Prefix='sensor-data/')
```

### 5. Destroy

```bash
./deploy-lambda.sh --destroy
```

## Demo Scenario: Factory Quality Inspection

> **Manufacturing lens**: A factory stores quality inspection images on FSx for ONTAP. The corporate quality team needs secure, scoped access without copying 500 GB to S3.

1. **Provider** (factory IT) runs this server, maps `/vol1/quality/lineA/images/` as a Volume
2. **Recipient** (quality team) receives a bearer token
3. **Access**: Recipient calls `temporary-volume-credentials` → receives 15-min STS credentials
4. **Query**: Recipient uses Spark/DuckDB/Python with S3A connector to read images directly
5. **Governance**: Each credential is prefix-scoped — Line A team cannot see Line B data

## Architecture

```
                    ┌──────────────────────────────┐
                    │  CloudFormation Stack        │
                    │  (template.yaml)             │
                    │                              │
                    │  • LambdaExecutionRole       │
                    │  • VendingRole               │
                    │  • Lambda Function           │
                    │  • Function URL              │
                    │  • Log Group                 │
                    └──────────────┬───────────────┘
                                   │
                    ┌──────────────▼───────────────┐
                    │  Lambda (arm64, Python 3.12) │
                    │  FastAPI + Mangum adapter    │
                    │                              │
  Recipient ──────► │  Bearer Token Auth           │
  (any client)      │  Volume Registry (YAML)      │
                    │  OpenTelemetry Traces        │
                    └──────────────┬───────────────┘
                                   │ sts:AssumeRole (VendingRole)
                                   │ + inline session policy (prefix-scoped)
                                   ▼
                    ┌──────────────────────────────┐
                    │  AWS STS                     │
                    └──────────────┬───────────────┘
                                   │ Scoped temporary credentials
                                   ▼
                    ┌──────────────────────────────┐
  Recipient ──────► │  FSx for ONTAP S3 AP         │ (direct data access)
  (same creds)      │  or Standard S3 Bucket       │
                    └──────────────────────────────┘
```

### IAM Policy Pattern for S3 Access Points

The vending role uses Access Point ARN format — **not** standard bucket ARN:

```json
{
  "Action": "s3:GetObject",
  "Resource": "arn:aws:s3:*:*:accesspoint/*/object/<prefix>*"
}
```

This is required because S3 AP aliases are resolved to AP ARNs during IAM evaluation.
Standard bucket ARN patterns (`arn:aws:s3:::<bucket>/<key>`) do **not** work with S3 Access Points.
See [AWS docs: S3 AP aliases](https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-points-alias.html).

## API Endpoints (OpenSharing Volumes spec)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/shares` | List shares |
| GET | `/api/v1/shares/{share}/all-volumes` | List all volumes in a share |
| GET | `/api/v1/shares/{share}/schemas/{schema}/volumes` | List volumes in a schema |
| GET | `/api/v1/shares/{share}/schemas/{schema}/volumes/{volume}` | Get volume details |
| POST | `/api/v1/shares/{share}/schemas/{schema}/volumes/{volume}/temporary-volume-credentials` | Generate scoped STS credentials |
| GET | `/health` | Health check |

## Configuration

Volumes are defined in `config/volumes.yaml`:

```yaml
server:
  credential_duration_seconds: 900  # 15 minutes
  aws_region: ap-northeast-1

auth:
  tokens:
    - token: "recipient-quality-team-token-xxx"
      recipient: "quality-team"
      shares: ["factory"]
    - token: "recipient-partner-token-yyy"
      recipient: "partner-corp"
      shares: ["factory"]

shares:
  - name: factory
    schemas:
      - name: quality
        volumes:
          - name: inspection-images
            storage_location: "s3://verification-tes-xxxxx-ext-s3alias/quality/lineA/images/"
          - name: sensor-data
            storage_location: "s3://verification-tes-xxxxx-ext-s3alias/sensor-data/"
      - name: engineering
        volumes:
          - name: cad-drawings
            storage_location: "s3://verification-tes-xxxxx-ext-s3alias/engineering/cad/"
```

## Observability

OpenTelemetry is built in from day one:

- **Traces**: Every API call generates a span with volume name, recipient, latency
- **Metrics**: Credential issuance count, latency p50/p99, error rate
- **Logs**: Structured JSON with request_id, recipient, volume, action

Export to any OTLP-compatible backend (Jaeger, Grafana Tempo, AWS X-Ray).

## Security Considerations

| Control | Implementation |
|---------|---------------|
| Authentication | Bearer token per recipient |
| Authorization | Token → allowed shares mapping |
| Credential scope | STS policy limits to volume's prefix only |
| TTL | Configurable (default 15 min) |
| Network | Deploy in VPC; optional VPC endpoint for STS |
| Audit | CloudTrail (STS calls) + server access log |

## Limitations (PoC Scope)

- **Volumes API only** — Tables, Agent Skills, ML Models are not implemented
- **Read-only** — Credentials grant `s3:GetObject` + `s3:ListBucket` only
- **Single-region** — One AWS region per server instance
- **No dynamic registration** — Volumes defined in YAML config
- **No persistence** — Stateless; no database required

## Relation to Other Documents

| Document | Role |
|----------|------|
| [OpenSharing Integration Analysis](../../docs/en/opensharing-integration-analysis.md) | Protocol-level analysis and independent verification |
| [Part 8 Blog (OpenSharing)](../../blog/en/part8-opensharing.md) | Public article on credential vending validation |
| [Verification Pack](../../verification-pack/opensharing-sts-vending/) | Raw evidence from STS vending tests |
| [README Pattern E](../../README.md) | High-level architecture pattern reference |

## Contributing

This is a reference implementation for validation. It documents S3 Access Point-specific IAM patterns and may serve as a starting point for other implementors.

## License

Apache 2.0 (same as the OpenSharing specification)

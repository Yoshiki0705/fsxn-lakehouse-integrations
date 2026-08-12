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

> **Cross-platform build note (verified 2026-07)**: dependencies with native
> extensions (`pydantic_core`, `opentelemetry`) must be installed as Linux/arm64
> wheels to run on Lambda — building on macOS produces `Runtime.ImportModuleError`.
> Install with:
> ```bash
> pip3 install --target .lambda-pkg \
>   --platform manylinux2014_aarch64 --only-binary=:all: \
>   --implementation cp --python-version 3.12 \
>   fastapi mangum pyyaml \
>   opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi
> ```
> Ensure the OpenTelemetry packages are included in the deployment package;
> a missing `opentelemetry` module surfaces as a 502 at the Function URL.

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

## Known Deployment Notes (verified 2026-07)

| Symptom | Cause | Workaround |
|---------|-------|------------|
| `Circular dependency between resources: [FunctionUrlPermission, VendingRole, FunctionUrl, ...]` | `VendingRole` trust policy and `LambdaExecutionRole` referenced each other's `.Arn` | Break the cycle: have the vending role trust the account root with an `aws:PrincipalArn`-style condition instead of referencing the Lambda role ARN directly; or create the IAM roles + Lambda + Function URL via CLI in dependency order. |
| `AWS::EarlyValidation::PropertyValidation` change set failure (`'Code' is a required property`) | `AWS::Lambda::Function` had no `Code` property. `aws cloudformation validate-template` is lenient and passed, but CloudFormation's change-set early validation (and cfn-lint rule E3003) enforce it. | **Fixed** in `template.yaml`: the function now includes an inline placeholder `Code.ZipFile`. `deploy-lambda.sh` overwrites it via `aws lambda update-function-code` with the real package. Template now validates clean with cfn-lint (0 errors/warnings). |
| `Runtime.ImportModuleError: No module named 'pydantic_core._pydantic_core'` / `'opentelemetry'` | macOS-built wheels or missing OTel deps in the package | Use the Linux/arm64 wheel install command in [Prerequisites](#prerequisites). |
| `AccessDenied ... not authorized to perform: sts:AssumeRole` | vending role ARN in `config/volumes.yaml` did not match the deployed role | Align `server.sts_role_arn` in `volumes.yaml` with the actual deployed vending-role ARN (the stack's `VendingRoleArn` output). |

> The template is validated with cfn-lint (0 errors/warnings). The two-phase deploy
> (CloudFormation creates the function shell with a placeholder, then
> `update-function-code` uploads the real package) keeps the template self-contained
> with no pre-upload S3 dependency. The CLI-direct path remains a portable fallback for
> accounts with stricter change-set hooks.

## Demo Scenario: Factory Quality Inspection

> **Manufacturing use case**: A factory stores quality inspection images on FSx for ONTAP. The corporate quality team needs secure, scoped access without copying 500 GB to S3.

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
| GET | `/api/v1/profile/{recipient}` | Generate credential profile for Databricks `CREATE PROVIDER` |
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
| Function URL | Verification deployments use `auth-type NONE` for convenience. For production, use `AWS_IAM` auth (SigV4) or place the function behind API Gateway / a private VPC endpoint — do **not** expose an unauthenticated Function URL that vends credentials. |
| Audit | CloudTrail (STS calls) + server access log |

## Cost Considerations

> **Sample run vs production estimate**: the figures below separate what was *observed* in one validation environment from an *illustrative production estimate*. Estimates use reference unit prices — confirm current rates for your region with the [AWS Pricing Calculator](https://calculator.aws/).

**Key architectural point**: this server only *vends credentials*. The actual data transfer — the recipient reading objects from the FSx for ONTAP S3 AP — happens **directly between the recipient and S3**, not through this Lambda. So server cost scales with the *number of credential requests*, not with data volume.

**What you pay for**

| Component | Charge basis | Notes |
|-----------|-------------|-------|
| Lambda (requests + duration) | per request + GB-seconds | The only compute cost; arm64 is cheaper per GB-second |
| STS `AssumeRole` | no additional charge | STS API calls are not billed |
| Function URL | no additional charge | Billed as normal Lambda invocations |
| CloudWatch Logs | ingestion + storage | Set a retention policy; structured logs are small |
| Data transfer | not via this server | Recipient ↔ S3 AP GETs are billed as S3 / FSx for ONTAP access |

**Observed (one validation environment — ap-northeast-1, 256 MB, arm64)**

- Cold init ~0.35–0.85 s; warm invoke ~0.38–0.83 s; max memory used ~64–80 MB of 256 MB; deployment package ~3.4 MB.
- Cold/warm split and concurrency were not systematically benchmarked (single-caller validation). Treat as directional, not a benchmark.

**Illustrative production estimate (reference figures, not a quote)**

Assumptions: 10,000 credential-vend requests/month, 256 MB, ~0.4 s average duration, arm64.

- Lambda requests: 10,000 → ~$0.002 (reference $0.20 / 1M requests)
- Lambda compute: 10,000 × 0.4 s × 0.25 GB = 1,000 GB-seconds → ~$0.013 (reference arm64 GB-second rate)
- STS + Function URL: $0
- CloudWatch Logs: small; depends on log volume and retention

At this volume the server's marginal cost is a fraction of a US dollar per month; it becomes meaningful only at very high request rates or with verbose logging. Validate with the AWS Pricing Calculator and your region's current rates before quoting.

## Unity Catalog Consumption (CREATE PROVIDER)

The ultimate goal is for Unity Catalog to consume this server's shares as governed
Foreign Volumes — with lineage, tags, ABAC, and audit. This section documents how to
attempt that path.

### Generate a Credential Profile

The OpenSharing credential profile (`.share` file) is the standard mechanism for
Databricks to connect to an external provider:

```bash
# Generate a profile for a specific recipient
python3 scripts/generate-profile.py \
  --endpoint https://<your-function-url>/api/v1 \
  --recipient quality-team \
  --output ./profiles/quality-team.share

# Or via the server API (requires OPENSHARING_ENDPOINT_URL env var set on server)
curl -H "Authorization: Bearer <token>" \
  https://<your-function-url>/api/v1/profile/quality-team \
  -o quality-team.share
```

The profile file contains:
```json
{
  "shareCredentialsVersion": 1,
  "endpoint": "https://<function-url>/api/v1",
  "bearerToken": "<recipient-token>"
}
```

### Attempt CREATE PROVIDER in Databricks

```sql
-- 1. Create a provider (upload the .share file via Catalog Explorer)
CREATE PROVIDER fsxontap_provider;

-- 2. List available shares
SHOW SHARES IN PROVIDER fsxontap_provider;

-- 3. Create a catalog from the share (if accepted)
CREATE CATALOG fsxontap_data USING SHARE fsxontap_provider.factory;

-- 4. Access the data with full UC governance
USE CATALOG fsxontap_data;
SHOW VOLUMES IN quality;
```

### Expected outcome (as of July 2026)

> **This path has not been validated yet.** MinIO's GA in the Storage Ecosystem proves
> the UC recipient-side code exists, but whether it is open to any protocol-compliant
> server or restricted to certified partners is unknown.

Run the verification script to test:

```bash
python3 scripts/verify-uc-provider.py \
  --server-url https://<your-function-url> \
  --token <bearer-token> \
  --provider-name fsxontap_test
```

**If it succeeds**: UC native consumption with governance is available.
**If it fails**: the specific error message becomes evidence for a Databricks feature
request ("UC recipient for non-Databricks Volume providers").

### Current status of UC recipient support

| Provider type | Tables | Volumes | Status |
|--------------|:------:|:-------:|--------|
| Databricks-to-Databricks | ✅ | ✅ | GA |
| Databricks-to-Open (Databricks as provider) | ✅ | ❌ | Tables GA, Volumes not available for open recipients |
| Storage Ecosystem (MinIO) | ✅ | ❓ | GA, Volume support unclear |
| Storage Ecosystem (NetApp) | — | — | Committed end of 2026 |
| Any OpenSharing-compliant server (this repo) | ❓ | ❓ | **To be validated** |

For detailed analysis, see [OpenSharing and Unity Catalog: Concepts](../../docs/en/opensharing-and-unity-catalog-explained.md#uc-recipient-current-availability-and-responsibility-map).

## Partner / SA Q&A

**Q: "Can Databricks use OpenSharing to read our FSx for ONTAP data today?"**

A first-line answer that separates what is verified from what is not:

- **Protocol layer — verified.** This OSS reference server vends scoped STS credentials, and recipients read the FSx for ONTAP S3 AP directly via standard `GetObject` (re-confirmed 2026-07). This does **not** depend on the Unity Catalog External Location session policy that blocks S3 AP ARNs.
- **Native UC OpenSharing recipient — pending.** Recognition of an OpenSharing share as a UC Foreign Volume/Table is awaiting Databricks' native implementation (expected via the year-end Storage Ecosystem partner delivery). This has not been validated here.
- **What works today for a PoC.** A notebook-mediated pattern: call this server from a notebook (`requests`) → receive scoped credentials → read the S3 AP (`boto3`/Spark) → optionally write to a UC managed table. On a trial (Serverless-only) workspace, notebook-compute activation can stall — that is *environment-specific*, not a general Databricks Serverless limitation.
- **If governed ingestion is needed in production today** (not via OpenSharing), use the established DataSync → S3 → UC managed table path.

**Q: "Is this a certified or production integration?"**

No. This is a vendor-neutral reference implementation for validating the protocol against S3-compatible storage. See [Limitations](#limitations-poc-scope) and [Security Considerations](#security-considerations).

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
| Part 8 (article draft, not in this repository) | Credential vending validation. The measured result is in [opensharing-integration-analysis](../../docs/en/opensharing-integration-analysis.md) |
| [Verification Pack](../../verification-pack/opensharing-sts-vending/) | Raw evidence from STS vending tests |
| [README Pattern E](../../README.md) | High-level architecture pattern reference |

## Contributing

This is a reference implementation for validation. It documents S3 Access Point-specific IAM patterns and may serve as a starting point for other implementors.

## License

Apache 2.0 (same as the OpenSharing specification)

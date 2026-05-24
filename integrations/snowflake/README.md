# Snowflake Integration

🌐 **English** | [日本語](docs/ja/setup-guide.md)

> **Validation Status: ✅ Verified (with `AWS_ACCESS_POINT_ARN`)**
>
> Snowflake can query FSx for ONTAP S3 Access Point data using the `AWS_ACCESS_POINT_ARN` stage parameter.
> SELECT, External Table creation, and LIST all work when this parameter is configured.
> Without it, SELECT fails with "access denied" while LIST works.

## Observed Results

| Operation | Without `AWS_ACCESS_POINT_ARN` | With `AWS_ACCESS_POINT_ARN` |
|---|:---:|:---:|
| Storage Integration | ✅ | ✅ |
| Stage creation | ✅ | ✅ |
| LIST @stage | ✅ | ✅ |
| SELECT @stage (Parquet) | ❌ Access Denied | ✅ |
| SELECT @stage (CSV) | ❌ | ✅ |
| External Table | ❌ | ✅ |
| COPY INTO (load) | ❌ | ✅ |
| Governance Tags | N/A | ✅ |
| Snowpipe (auto-ingest) | ❌ | ❌ (S3 Event Notifications not supported) |
| Iceberg Table write | ❌ | ❌ (conditional writes not supported) |
| GET_PRESIGNED_URL | ✅ (observed) | ✅ |

## Overview

Integrate Amazon FSx for NetApp ONTAP (FSx for ONTAP) S3 Access Points with Snowflake
External Stages, using them as the storage layer for External Tables and Iceberg Tables.

## Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                              AWS Account                               │
│                                                                       │
│  ┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐  │
│  │ FSx for ONTAP   │     │ FSx for ONTAP    │     │ IAM Role      │  │
│  │ (NFS Volume)    │◀───▶│ S3 Access Point  │◀────│ (Snowflake    │  │
│  │                 │     │ (Internet origin) │     │  AssumeRole)  │  │
│  └─────────────────┘     └────────┬─────────┘     └───────┬───────┘  │
│                                    │                        │         │
└────────────────────────────────────┼────────────────────────┼─────────┘
                                     │ S3 API                 │ STS
                                     ▼                        ▼
                          ┌────────────────────────────────────────────┐
                          │  Snowflake (SaaS — ap-northeast-1)         │
                          │                                            │
                          │  Storage Integration → External Stage      │
                          │       → External Table / Iceberg Table     │
                          │       → Snowpipe (via FPolicy + SNS)       │
                          └────────────────────────────────────────────┘
```

**Key Architecture Points:**
- FSx for ONTAP S3 Access Point is created via `aws fsx create-and-attach-s3-access-point` (not CloudFormation `AWS::S3::AccessPoint`)
- Network Origin is **Internet** (Snowflake is SaaS, so VPC-scoped is not usable)
- IAM Role trust policy requires two-phase setup (Snowflake AWS Account ID + External ID)

## FSx for ONTAP S3 Access Point — Supported S3 Operations

| Operation | Supported | Notes |
|-----------|-----------|-------|
| ListObjectsV2 | ✅ | High latency (tens of seconds to minutes) |
| GetObject | ✅ | |
| PutObject | ✅ | Max 5GB |
| DeleteObject | ✅ | |
| HeadObject | ✅ | |
| **Pre-signed URL** | ✅ | AWS docs say unsupported, but works in practice |
| S3 Event Notifications | ❌ | Use FPolicy as alternative |
| Object Versioning | ❌ | |

> ℹ️ **Note**: AWS documentation states Pre-signed URLs are "Not supported," but testing confirms `GET_PRESIGNED_URL()` works correctly with FSx for ONTAP S3 AP.

## Data Format Support

| Format | Read | Write | Table Type |
|--------|------|-------|------------|
| Parquet | ✅ | ✅ | External Table / Iceberg |
| CSV | ✅ | ✅ | External Table |
| JSON | ✅ | ✅ | External Table |
| ORC | ✅ | ❌ | External Table |
| Avro | ✅ | ❌ | External Table |
| Iceberg | ✅ | ✅ | Iceberg Table |

## ONTAP Value for Snowflake

| ONTAP Feature | Snowflake Benefit |
|---------------|-------------------|
| FlexClone | Instant staging environment with production data |
| Snapshot | Recover data beyond Snowflake Time Travel retention |
| FabricPool | Auto-tier historical partitions (transparent to Snowflake) |
| Deduplication | Reduce storage for similar file versions |
| SnapMirror | Cross-region data availability for Snowflake replication |
| FPolicy | Event-driven Snowpipe ingestion (<30s latency) |
| Multi-protocol | NFS (ingest) + S3 AP (Snowflake) — same data, no copy |

## Quick Start

```bash
# 1. Create FSx for ONTAP S3 Access Point (prerequisite)
aws fsx create-and-attach-s3-access-point \
  --name snowflake-ap --type ONTAP \
  --ontap-configuration 'VolumeId=fsvol-xxx,FileSystemIdentity={Type=UNIX,UnixUser={Name=root}}'

# 2. Deploy IAM Role via CloudFormation
cp params.example.json params.json  # Edit: set S3AccessPointArn
./deploy.sh

# 3. Run SQL scripts in Snowflake (01 → 09)
```

## Files

| File | Description |
|------|-------------|
| `template.yaml` | CloudFormation: IAM Role for Snowflake Storage Integration |
| `deploy.sh` | Deployment script (Phase 1 + Phase 2) |
| `params.example.json` | Parameter template |
| `scripts/update_trust_policy.sh` | Phase 2: Update trust with Snowflake info |
| `scripts/configure_fpolicy.py` | ONTAP FPolicy configuration |
| `sql/01-10` | Snowflake SQL setup scripts |
| `docs/ja/` | Japanese documentation |
| `docs/en/` | English documentation |
| `tests/` | Integration tests |

## Known Limitations

1. **FSx for ONTAP S3 AP latency**: ListObjects can take tens of seconds to minutes
2. **Pre-signed URL**: AWS docs say "Not supported" but works in practice with `GET_PRESIGNED_URL()`
3. **S3 Event Notifications not supported**: Direct Snowpipe trigger not possible (use FPolicy as alternative)
4. **Max upload size**: 5GB (Multipart Upload supported)

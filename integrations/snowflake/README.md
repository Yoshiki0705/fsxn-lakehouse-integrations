# Snowflake Integration / Snowflake 統合

🌐 [日本語ドキュメント](docs/ja/setup-guide.md) | [English Documentation](docs/en/setup-guide.md)

## Overview

Amazon FSx for NetApp ONTAP（FSx for ONTAP）の S3 Access Point を Snowflake の
External Stage として統合し、External Table / Iceberg Table のストレージレイヤーとして使用するパターンです。

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
- FSx for ONTAP S3 Access Point は `aws fsx create-and-attach-s3-access-point` で作成（CloudFormation `AWS::S3::AccessPoint` ではない）
- Network Origin は **Internet**（Snowflake は SaaS のため VPC-scoped は使用不可）
- IAM Role の信頼ポリシーは二段階セットアップ（Snowflake の AWS Account ID + External ID）

## FSx for ONTAP S3 Access Point — Supported S3 Operations

| Operation | Supported | Notes |
|-----------|-----------|-------|
| ListObjectsV2 | ✅ | 高レイテンシ（数十秒〜数分） |
| GetObject | ✅ | |
| PutObject | ✅ | 最大 5GB |
| DeleteObject | ✅ | |
| HeadObject | ✅ | |
| **Pre-signed URL** | ✅ | AWS docs say unsupported, but works in practice |
| S3 Event Notifications | ❌ | FPolicy で代替 |
| Object Versioning | ❌ | |

> ℹ️ **注記**: AWS ドキュメントでは Pre-signed URL は「非サポート」と記載されていますが、テストにより `GET_PRESIGNED_URL()` は FSx for ONTAP S3 AP で正常に動作することを確認しています。

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

1. **FSx for ONTAP S3 AP レイテンシ**: ListObjects は数十秒〜数分かかる場合がある
2. **Pre-signed URL**: AWS docs say "Not supported" but works in practice with `GET_PRESIGNED_URL()`
3. **S3 Event Notifications 非サポート**: Snowpipe の直接トリガー不可（FPolicy で代替）
4. **最大アップロードサイズ**: 5GB（Multipart Upload 対応）

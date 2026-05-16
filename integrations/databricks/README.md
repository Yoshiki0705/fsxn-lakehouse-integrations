# Databricks Integration / Databricks 統合

🌐 [日本語ドキュメント](docs/ja/setup-guide.md) | [English Documentation](docs/en/setup-guide.md)

## Overview

Amazon FSx for NetApp ONTAP（FSx for ONTAP）を Databricks Unity Catalog の External Location として統合し、
Delta Lake / Iceberg テーブルのストレージレイヤーとして使用するパターンです。

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AWS Account                                  │
│                                                                           │
│  ┌────────────────────┐                                                  │
│  │  Databricks        │                                                  │
│  │  Unity Catalog     │                                                  │
│  │  ┌──────────────┐  │     ┌──────────────┐     ┌─────────────────┐   │
│  │  │ External     │  │     │ S3 Access    │     │ FSx for ONTAP   │   │
│  │  │ Location     │──┼────▶│ Point        │────▶│ Volume          │   │
│  │  │              │  │     │ (VPC-scoped) │     │ (S3 protocol)   │   │
│  │  └──────────────┘  │     └──────────────┘     └─────────────────┘   │
│  │  ┌──────────────┐  │            │                      │             │
│  │  │ Storage      │  │     ┌──────▼──────┐       ┌──────▼──────┐      │
│  │  │ Credential   │──┼────▶│ IAM Role    │       │ Dedup/Snap/ │      │
│  │  │ (IAM Role)   │  │     │ (AssumeRole)│       │ FlexClone   │      │
│  │  └──────────────┘  │     └─────────────┘       └─────────────┘      │
│  └────────────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

## S3 Access Point Paths

```
s3://<s3ap-alias>/bronze/    # Raw ingested data
s3://<s3ap-alias>/silver/    # Cleaned & transformed
s3://<s3ap-alias>/gold/      # Business-ready aggregates
```

## Data Format Support

| Format | Read | Write | Table Type |
|--------|------|-------|------------|
| Parquet | ✅ | ✅ | External Table |
| Delta Lake | ✅ | ✅ | Managed / External |
| Iceberg | ✅ | ✅ | External (Unity Catalog) |
| CSV | ✅ | ✅ | External Table |
| JSON | ✅ | ✅ | External Table |
| ORC | ✅ | ❌ | External Table (read-only) |

## ONTAP Value for Databricks

| ONTAP Feature | Databricks Benefit |
|---------------|-------------------|
| FlexClone | Instant dev/test dataset provisioning without full copy |
| Snapshot | Table-level point-in-time recovery (complements Delta Time Travel) |
| FabricPool | Auto-tier cold partitions to S3 (transparent to Databricks) |
| Deduplication | Reduce storage for Delta version files and similar datasets |
| SnapMirror | Cross-region DR for lakehouse data |

## Quick Start

1. Deploy CloudFormation template: `template.yaml`
2. Configure Databricks Storage Credential (Terraform or UI)
3. Create External Location pointing to S3 AP
4. Run notebooks in order (01 → 06)

## Files

| File | Description |
|------|-------------|
| `template.yaml` | CloudFormation: S3 AP + IAM Role for Databricks |
| `terraform/` | Databricks Unity Catalog resources |
| `notebooks/01-06` | Step-by-step Databricks notebooks |
| `docs/ja/` | Japanese documentation |
| `docs/en/` | English documentation |
| `tests/` | Integration tests |

# Snowflake Integration / Snowflake 統合

🌐 [日本語ドキュメント](docs/ja/setup-guide.md) | [English Documentation](docs/en/setup-guide.md)

## Overview

Amazon FSx for NetApp ONTAP（FSx for ONTAP）を Snowflake の External Stage として統合し、
External Table / Iceberg Table のストレージレイヤーとして使用するパターンです。

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AWS Account                                  │
│                                                                           │
│  ┌────────────────────┐                                                  │
│  │  Snowflake         │                                                  │
│  │  ┌──────────────┐  │     ┌──────────────┐     ┌─────────────────┐   │
│  │  │ External     │  │     │ S3 Access    │     │ FSx for ONTAP   │   │
│  │  │ Stage        │──┼────▶│ Point        │────▶│ Volume          │   │
│  │  │              │  │     │ (VPC-scoped) │     │ (S3 protocol)   │   │
│  │  └──────────────┘  │     └──────────────┘     └─────────────────┘   │
│  │  ┌──────────────┐  │            │                      │             │
│  │  │ Storage      │  │     ┌──────▼──────┐       ┌──────▼──────┐      │
│  │  │ Integration  │──┼────▶│ IAM Role    │       │ Dedup/Snap/ │      │
│  │  │ (IAM Role)   │  │     │ (AssumeRole)│       │ FlexClone   │      │
│  │  └──────────────┘  │     └─────────────┘       └─────────────┘      │
│  │  ┌──────────────┐  │                                                 │
│  │  │ Snowpipe     │◀─┼──── SNS Topic (optional, for auto-ingest)      │
│  │  └──────────────┘  │                                                 │
│  └────────────────────┘                                                  │
└─────────────────────────────────────────────────────────────────────────┘
```

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

## Quick Start

1. Deploy CloudFormation template: `template.yaml`
2. Run SQL scripts in order (01 → 07)
3. Validate with sample queries

## Files

| File | Description |
|------|-------------|
| `template.yaml` | CloudFormation: S3 AP + IAM Role for Snowflake |
| `sql/01-07` | Snowflake SQL setup scripts |
| `docs/ja/` | Japanese documentation |
| `docs/en/` | English documentation |
| `tests/` | Integration tests |

# Databricks Integration / Databricks 統合

🌐 [日本語ドキュメント](docs/ja/setup-guide.md) | [English Documentation](docs/en/setup-guide.md)

> **Validation Status: Experimental**
> - Unity Catalog External Location with FSx for ONTAP S3 Access Point did not succeed in the tested environment due to a session policy boundary.
> - Instance Profile + boto3 succeeded only as a controlled driver-node PoC.
> - Kernel NFS mount from Databricks Dedicated cluster was blocked by a local runtime boundary in the tested environment.
> - This repository does not claim production support for Databricks + FSx S3 Access Points.
>
> For production Delta Lake tables, use [Databricks-supported cloud storage patterns](https://docs.databricks.com/aws/en/connect/storage/amazon-s3) unless platform support for S3 Access Point ARNs is confirmed.

## Overview

This is an experimental validation package exploring integration paths between
Amazon FSx for NetApp ONTAP (FSx for ONTAP) and Databricks via S3 Access Points.

Some README sections describe intended integration patterns, while the
[Verification Status](#verification-status-2026-05-17) section documents the
current validation results and observed platform boundaries.

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

> **Note**: The table below reflects the intended integration design. See [Verification Status](#verification-status-2026-05-17) for actual test results. Unity Catalog External Location did not succeed in the tested environment, so read/write through UC governance is not currently validated.

| Format | Read via FSx S3 AP | Write via FSx S3 AP | Validation Status |
|--------|:------------------:|:-------------------:|-------------------|
| Parquet | Not validated through UC | Not validated | Requires UC External Location (currently blocked) |
| Delta Lake | Not validated | Not Supported | Delta commit requires atomic rename (not available on S3 AP) |
| Iceberg | Not validated | Not Supported | S3FileIO metadata write fails on AP alias |
| CSV | Possible via boto3 PoC | Not recommended | Driver-only PoC, bypasses UC governance |
| JSON | Possible via boto3 PoC | Not recommended | Driver-only PoC, bypasses UC governance |
| ORC | Not validated | Not validated | — |

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
| `template.yaml` | CloudFormation: S3 AP + IAM Role for Databricks (UC 統合) |
| `customer-vpc-network.yaml` | CloudFormation: Customer-managed VPC ネットワーク (NFS 検証用) |
| `vpc-peering.yaml` | CloudFormation: VPC Peering (Managed VPC ↔ FSx VPC, 参考用) |
| `deploy.sh` | S3 AP + UC 統合のデプロイスクリプト |
| `deploy-customer-vpc.sh` | Customer-managed VPC のデプロイ/削除スクリプト |
| `params.example.json` | CloudFormation パラメータ例 |
| `terraform/` | Databricks Unity Catalog リソース (Storage Credential, External Location) |
| `notebooks/01-09` | Databricks ノートブック (セットアップ〜ML) |
| `docs/ja/` | 日本語ドキュメント |
| `docs/en/` | 英語ドキュメント |
| `tests/` | 統合テスト |

## Infrastructure as Code (IaC) 構成

### 1. S3 Access Point 統合 (`template.yaml` + `terraform/`)

```bash
# Phase 1: AWS リソース (S3 AP, IAM Role)
cp params.example.json params.json  # パラメータ編集
./deploy.sh

# Phase 2: Databricks リソース (Storage Credential, External Location)
cd terraform/
cp terraform.tfvars.example terraform.tfvars  # パラメータ編集
terraform init && terraform apply
```

### 2. Customer-managed VPC (`customer-vpc-network.yaml`)

FSx for ONTAP と同一 VPC に Databricks ネットワークを構築:

```bash
# デプロイ (NAT Gateway 作成 → ~$45/month)
./deploy-customer-vpc.sh deploy

# 状態確認
./deploy-customer-vpc.sh status

# 削除 (コスト削減)
./deploy-customer-vpc.sh delete
```

デプロイ後の手動ステップ:
1. Databricks Account Console → Cloud Resources → Networks で登録
2. 新しい Workspace を作成 (Network Configuration 指定)
3. Dedicated (Single user) クラスタを作成

### 3. VPC Peering (`vpc-peering.yaml`, 参考用)

Managed VPC から FSx VPC への接続。NFS mount は seccomp でブロックされるため、
ONTAP REST API アクセスや将来の再検証用に保持。

## Verification Status (2026-05-17)

> **Note**: Instance Profile is classified as a [legacy data access pattern](https://docs.databricks.com/en/admin/sql/data-access-configuration.html) by Databricks. Unity Catalog external locations are the recommended governance model. The Instance Profile path documented below bypasses Unity Catalog governance and should be treated as a controlled PoC only.

| アプローチ | 結果 | 備考 |
|-----------|------|------|
| S3 AP + Unity Catalog | ❌ | Session policy が S3 AP ARN 非対応 |
| S3 AP + boto3 (Managed VPC) | ❌ | IMDS ブロック |
| NFS mount (Managed VPC) | ❌ | Egress 制限 + seccomp |
| NFS mount (Customer VPC) | ❌ | seccomp フィルターが NFS mount をブロック |
| NFS RPC 直接 (Customer VPC) | ✅ | Python RPC で全操作成功 |
| ONTAP REST API (Customer VPC) | ✅ | 認証・設定変更可能 |
| Instance Profile + boto3 | 🔲 | 未検証 (次のステップ) |

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

| アプローチ | 結果 | 備考 |
|-----------|------|------|
| S3 AP + Unity Catalog | ❌ | Session policy が S3 AP ARN 非対応 |
| S3 AP + boto3 (Managed VPC) | ❌ | IMDS ブロック |
| NFS mount (Managed VPC) | ❌ | Egress 制限 + seccomp |
| NFS mount (Customer VPC) | ❌ | seccomp フィルターが NFS mount をブロック |
| NFS RPC 直接 (Customer VPC) | ✅ | Python RPC で全操作成功 |
| ONTAP REST API (Customer VPC) | ✅ | 認証・設定変更可能 |
| Instance Profile + boto3 | 🔲 | 未検証 (次のステップ) |

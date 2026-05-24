# Databricks Integration

🌐 **English** | [日本語](docs/ja/setup-guide.md)

> **Validation Status: Experimental**
> - Unity Catalog External Location with FSx for ONTAP S3 Access Point did not succeed in the tested environment due to a session policy boundary.
> - Instance Profile + boto3 succeeded only as a controlled driver-node PoC.
> - Kernel NFS mount from Databricks Dedicated cluster was blocked by a local runtime boundary in the tested environment.
> - This repository does not claim production support for Databricks + FSx S3 Access Points.
>
> For production Delta Lake tables, use [Databricks-supported cloud storage patterns](https://docs.databricks.com/aws/en/connect/storage/amazon-s3) unless platform support for S3 Access Point ARNs is confirmed.
>
> **Partner / Marketplace scope**: This repository is not a Databricks Marketplace listing, certified integration, or production-ready partner solution. It is an experimental validation package intended to document observed behavior and collect reproducible evidence.

## Overview

This is an experimental validation package exploring integration paths between
Amazon FSx for NetApp ONTAP (FSx for ONTAP) and Databricks via S3 Access Points.

Some README sections describe intended integration patterns, while the
[Verification Status](#verification-status-2026-05-17) section documents the
current validation results and observed platform boundaries.

## Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                              AWS Account                               │
│                                                                       │
│  ┌────────────────────┐                                               │
│  │  Databricks        │                                               │
│  │  Unity Catalog     │                                               │
│  │  ┌──────────────┐  │     ┌──────────────┐     ┌───────────────┐   │
│  │  │ External     │  │     │ S3 Access    │     │ FSx for ONTAP │   │
│  │  │ Location     │──┼────▶│ Point        │────▶│ Volume        │   │
│  │  │              │  │     │ (VPC-scoped) │     │ (S3 protocol) │   │
│  │  └──────────────┘  │     └──────────────┘     └───────────────┘   │
│  │  ┌──────────────┐  │            │                     │            │
│  │  │ Storage      │  │     ┌──────▼──────┐      ┌──────▼──────┐     │
│  │  │ Credential   │──┼────▶│ IAM Role    │      │ Dedup/Snap/ │     │
│  │  │ (IAM Role)   │  │     │ (AssumeRole)│      │ FlexClone   │     │
│  │  └──────────────┘  │     └─────────────┘      └─────────────┘     │
│  └────────────────────┘                                               │
└───────────────────────────────────────────────────────────────────────┘
```

## S3 Access Point Paths

```
s3://<s3ap-alias>/bronze/    # Raw ingested data
s3://<s3ap-alias>/silver/    # Cleaned & transformed
s3://<s3ap-alias>/gold/      # Business-ready aggregates
```

## Data Format Support

> **Important**: The table below represents intended validation targets, not production support status. Unity Catalog External Location did not succeed in the tested environment due to a session policy boundary. The Databricks Unity Catalog + FSx S3 AP path is currently documented as an observed boundary in this validation.

| Format | Validation Status | Notes |
|--------|-------------------|-------|
| Parquet | Not validated as production Databricks path on FSx S3 AP | Requires UC External Location (currently blocked by session policy) |
| Delta Lake | Not validated for write-path semantics on FSx S3 AP | Delta commit requires atomic rename (not available on S3 AP) |
| Iceberg | Not validated for production use on FSx S3 AP | S3FileIO metadata write fails on AP alias |
| CSV | Driver-only boto3 PoC possible | Bypasses UC governance; not a production path |
| JSON | Driver-only boto3 PoC possible | Bypasses UC governance; not a production path |
| ORC | Not validated | — |

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
| `template.yaml` | CloudFormation: S3 AP + IAM Role for Databricks (UC integration) |
| `customer-vpc-network.yaml` | CloudFormation: Customer-managed VPC network (for NFS verification) |
| `vpc-peering.yaml` | CloudFormation: VPC Peering (Managed VPC ↔ FSx VPC, reference) |
| `deploy.sh` | S3 AP + UC integration deployment script |
| `deploy-customer-vpc.sh` | Customer-managed VPC deploy/delete script |
| `params.example.json` | CloudFormation parameter example |
| `terraform/` | Databricks Unity Catalog resources (Storage Credential, External Location) |
| `notebooks/01-09` | Databricks notebooks (setup through ML) |
| `docs/ja/` | Japanese documentation |
| `docs/en/` | English documentation |
| `tests/` | Integration tests |

## Infrastructure as Code (IaC) Structure

### 1. S3 Access Point Integration (`template.yaml` + `terraform/`)

```bash
# Phase 1: AWS Resources (S3 AP, IAM Role)
cp params.example.json params.json  # Edit parameters
./deploy.sh

# Phase 2: Databricks Resources (Storage Credential, External Location)
cd terraform/
cp terraform.tfvars.example terraform.tfvars  # Edit parameters
terraform init && terraform apply
```

### 2. Customer-managed VPC (`customer-vpc-network.yaml`)

Build Databricks networking in the same VPC as FSx for ONTAP:

```bash
# Deploy (creates NAT Gateway → ~$45/month)
./deploy-customer-vpc.sh deploy

# Check status
./deploy-customer-vpc.sh status

# Delete (cost reduction)
./deploy-customer-vpc.sh delete
```

Post-deployment manual steps:
1. Register in Databricks Account Console → Cloud Resources → Networks
2. Create a new Workspace (specify Network Configuration)
3. Create a Dedicated (Single user) cluster

### 3. VPC Peering (`vpc-peering.yaml`, reference)

Connection from Managed VPC to FSx VPC. NFS mount is blocked by seccomp,
so retained for ONTAP REST API access and future re-verification.

## Verification Status (2026-05-17)

> **Note**: Instance Profile is classified as a [legacy data access pattern](https://docs.databricks.com/en/admin/sql/data-access-configuration.html) by Databricks. Unity Catalog external locations are the recommended governance model. The Instance Profile path documented below bypasses Unity Catalog governance and should be treated as a controlled PoC only.

| Approach | Result | Notes |
|----------|--------|-------|
| S3 AP + Unity Catalog | ❌ | Session policy does not support S3 AP ARN |
| S3 AP + boto3 (Managed VPC) | ❌ | IMDS blocked |
| NFS mount (Managed VPC) | ❌ | Egress restriction + seccomp |
| NFS mount (Customer VPC) | ❌ | seccomp filter blocks NFS mount |
| NFS RPC direct (Customer VPC) | ✅ | All operations succeed via Python RPC |
| ONTAP REST API (Customer VPC) | ✅ | Authentication and config changes possible |
| Instance Profile + boto3 (Customer VPC, Dedicated) | ✅ | S3 AP read from driver-node succeeded. Bypasses UC governance — PoC only |

# Databricks Integration

🌐 **English** | [日本語](docs/ja/README.md)

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

## Managed Table vs External Table — Design Guide

Understanding the difference between managed and external tables in Unity Catalog is critical for architecture decisions — especially given the current FSx S3 AP session policy limitation.

### Comparison Matrix

| Aspect | UC External Table (on FSx S3 AP) | UC Managed Table (on S3 bucket) | boto3 PoC (no UC table) |
|---|---|---|---|
| **Data location** | FSx for ONTAP (zero-copy) | Databricks-managed S3 | FSx for ONTAP |
| **UC governance** | ❌ **Blocked** (CREATE TABLE fails) | ✅ Full (tags, masks, lineage) | ❌ None |
| **ONTAP features preserved** | ✅ Snapshot, FlexClone, FPolicy | ❌ Data outside ONTAP | ✅ (read-only) |
| **Multi-protocol access** | ✅ NFS/SMB/S3 AP | ❌ S3 only | ✅ NFS/SMB/S3 AP |
| **Query performance** | N/A (table creation blocked) | ✅ Optimized Delta/Iceberg | ❌ No Spark optimization |
| **Delta Lake features** | ❌ Blocked | ✅ ACID, Time Travel, MERGE | ❌ Not applicable |
| **ML Feature Store** | ❌ Blocked | ✅ Full support | ❌ Not applicable |
| **Data freshness** | Would be real-time (if supported) | Depends on ingestion pipeline | Real-time (boto3 reads current state) |
| **Storage cost** | FSx only | FSx + S3 (duplicate) | FSx only |
| **Production suitability** | ❌ Not viable today | ✅ Recommended | ⚠️ PoC only |

### Current State: What Works and What Doesn't

```
FSx for ONTAP S3 AP
     │
     ├── UC External Location (access_point field set)
     │     ├── Top-level ls: ✅ (287 items)
     │     ├── Explicit file read (spark.read.csv): ✅ (1000 rows)
     │     ├── Subdirectory listing: ❌ (AccessDenied)
     │     ├── CREATE TABLE: ❌ (UC_CLOUD_STORAGE_ACCESS_FAILURE)
     │     └── Write operations: ❌ (PutObject AccessDenied)
     │
     └── Instance Profile + boto3 (Customer VPC, Dedicated cluster)
           ├── GetObject: ✅
           ├── ListObjectsV2: ✅
           └── UC governance: ❌ (bypassed entirely)
```

### Recommended Architecture Pattern (Today)

Since UC External Tables on FSx S3 AP are blocked, the recommended pattern is a **staged ingestion** approach:

```
FSx for ONTAP ──S3 AP──▶ Ingestion Job ──▶ S3 Bucket ──▶ UC Managed Table ──▶ ML/AI
     │                    (Glue/EMR/Lambda)                    │
     │                                                         └── Full UC governance
     └── Same data via NFS/SMB (source of truth)
```

**Or for read-only analytics:**
```
FSx for ONTAP ──S3 AP──▶ Athena (SQL analytics, no copy needed)
                    └──▶ Snowflake External Table (governed, no copy needed)
```

### When to Use Each Pattern

| Requirement | Recommended Pattern | Why |
|---|---|---|
| Governed ML training data | S3 bucket → UC Managed Table | Full UC governance, Feature Store, lineage |
| Read-only SQL analytics on NAS | Athena + FSx S3 AP | No copy, serverless, governed |
| Governed external tables on NAS | Snowflake External Table | Works today with full governance |
| Exploratory data access (PoC) | Instance Profile + boto3 | Quick access, no governance |
| Production Delta Lake tables | S3 bucket (standard pattern) | Required for ACID, MERGE, OPTIMIZE |
| Real-time NAS data + UC governance | Wait for platform support | UC session policy resolution needed |

### Cost & Governance Trade-off

| Pattern | Storage Cost | Governance | Performance | ONTAP Features |
|---|---|---|---|---|
| **Athena + FSx S3 AP** | Lowest (FSx only) | AWS-side (IAM, S3 AP) | Good (serverless) | ✅ Preserved |
| **Snowflake External Table** | Low (FSx only) | ✅ Full (tags, masking) | Moderate | ✅ Preserved |
| **Staged to S3 → UC Table** | Higher (FSx + S3) | ✅ Full UC | Best (Delta optimized) | ❌ Lost on copy |
| **boto3 PoC** | Lowest (FSx only) | ❌ None | Poor (driver-only) | ✅ Preserved |

### References

- [Unity Catalog External Tables](https://docs.databricks.com/aws/en/tables/external)
- [Managed vs External Assets](https://docs.databricks.com/aws/en/data-governance/unity-catalog/managed-versus-external)
- [External Locations](https://docs.databricks.com/aws/en/connect/unity-catalog/storage-credentials)
- [Delta Lake on Databricks](https://docs.databricks.com/aws/en/delta/index)

## Unstructured Data Support

| Format | Support | Access Method | Use Case |
|--------|:---:|--------------|----------|
| Images (JPEG, PNG, TIFF) | ⚠️ | Instance Profile + boto3 (driver only) | Image classification, quality inspection |
| Video (MP4, MOV) | ⚠️ | Instance Profile + boto3 (driver only) | Frame extraction, video analytics |
| Documents (PDF, DOCX) | ⚠️ | Instance Profile + boto3 (driver only) | Text extraction, RAG pipeline |
| Audio (WAV, MP3) | ⚠️ | Instance Profile + boto3 (driver only) | Transcription, speech analytics |
| Binary / Archives | ⚠️ | Instance Profile + boto3 (driver only) | Download, custom processing |

**Current limitations:**
- Unity Catalog External Table creation is blocked → no governed unstructured data catalog
- `spark.read.binaryFile` works for explicit file paths (with `access_point` field set)
- Instance Profile + boto3 bypasses UC governance (PoC only, not production-recommended)
- No equivalent to Snowflake's Directory Table or GET_PRESIGNED_URL
- Executor-scale processing not yet validated

**Recommended alternative for unstructured data on FSx for ONTAP:**
- Use **Snowflake** (Directory Table + GET_PRESIGNED_URL) for file catalog and secure URL generation
- Use **AWS Lambda** for serverless file processing ([AWS tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-process-files-with-lambda.html))
- Use **Amazon Bedrock** for RAG over documents ([AWS tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html))

## ONTAP Value for Databricks

| ONTAP Feature | Databricks Benefit | Reference |
|---|---|---|
| **FlexCache** | Cache training data across regions/sites for low-latency access; write-back mode for feature engineering | [FlexCache docs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html) |
| **SnapLock / Tamperproof Snapshot** | Immutable training data protection — admin cannot delete during retention; compliance for regulated ML | [SnapLock on FSx](https://netapp.com/blog/snaplock-on-amazon-fsx-ontap/) |
| **ARP/AI** | AI-powered ransomware detection; auto-snapshot protects training data and model artifacts | [ARP on FSx](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/ARP.html) |
| **FlexClone** | Instant dev/test dataset provisioning without full copy; zero-copy ML experimentation | [FlexClone docs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| **Snapshot** | Table-level point-in-time recovery (complements Delta Time Travel); feature pipeline versioning | [Snapshot docs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapshots-ontap.html) |
| **FabricPool** | Auto-tier cold partitions to S3 (transparent to Databricks compute) | [FabricPool docs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/fabricpool.html) |
| **Storage Efficiency** | Up to 65% savings via deduplication + compression + compaction on Delta version files | [Storage efficiency](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/storage-efficiency.html) |
| **SnapMirror** | Cross-region DR for lakehouse data and ML pipelines | [SnapMirror docs](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html) |
| **Multi-protocol** | NFS (data scientists) + SMB (Windows users) + S3 AP (Databricks/Spark) — same data, no copy | [Multi-protocol](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html) |
| **FPolicy** | File operation monitoring and blocking; audit trail for data access compliance | [FPolicy docs](https://docs.netapp.com/us-en/ontap/nas-audit/fpolicy-config-types-concept.html) |

## Governance & AI/ML Guides

| Guide | Description |
|---|---|
| [AI/ML Demo Guide](docs/en/ai-demo-guide.md) | Current status, working demos, blocked paths, future capabilities |
| [Governance: Tags & Data Protection (ABAC)](docs/en/ai-demo-guide.md#governance-tags--data-protection-abac) | UC ABAC, governed tags, column masks, row filters — current limitations |
| [Governance: File-Level Access Control](docs/en/ai-demo-guide.md#file-level-access-control-ontap-native-layer) | ONTAP dual-layer auth, FPolicy, per-team S3 AP isolation (compensating control) |
| [Integration: ONTAP × Databricks Tags](docs/en/ai-demo-guide.md#integration-ontap-file-level-control--databricks-tag-governance) | Combined governance matrix, current vs future state, design patterns |

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

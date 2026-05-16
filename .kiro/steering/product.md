---
inclusion: auto
---

# Product Context: FSxN Lakehouse Integrations

## What This Project Is

A reference implementation and pattern library demonstrating how Amazon FSx for NetApp ONTAP
integrates with modern Data Lake and Lakehouse platforms via S3 Access Points.

**Key Insight**: FSxN S3 Access Points (launched Dec 2025) allow AWS services and third-party
platforms to access FSxN file data as if it were in an S3 bucket — no data movement required.

## Target Audience

- Enterprise data platform teams evaluating FSxN for lakehouse storage
- NetApp/AWS partners building customer solutions
- Data engineers implementing multi-platform data architectures

## Core Value Proposition

| ONTAP Feature | Lakehouse Benefit |
|---------------|-------------------|
| Deduplication | 30-60% storage reduction for Delta/Iceberg version files |
| Snapshot | Volume-level point-in-time recovery (complements table time travel) |
| FlexClone | Zero-copy dev/test environments in seconds |
| FabricPool | Automatic cold partition tiering to S3 |
| Multi-protocol | Same data accessible via NFS + SMB + S3 simultaneously |
| SnapMirror | Cross-region DR without platform-specific replication |

## Architecture Patterns

- **Pattern A**: Read-only analytics (External Table / External Stage)
- **Pattern B**: Read-write managed tables (Delta Lake / Iceberg on FSxN)
- **Pattern C**: ETL pipeline (Medallion: Raw → Bronze → Silver → Gold)
- **Pattern D**: Data sharing (per-consumer S3 AP with scoped policies)

## Important Technical Context

- FSxN S3 AP requires **internet network origin** for Athena/Glue (not VPC-only)
- FSxN S3 AP supports GetObject, PutObject, DeleteObject, ListObjectsV2, Multipart Upload
- FSxN S3 AP does NOT support S3 Event Notifications (use Lambda polling for Snowpipe)
- S3 AP alias format: `<name>-<account-id>.s3-accesspoint.<region>.amazonaws.com`
- Databricks requires cross-account IAM Role with External ID
- Snowflake requires Storage Integration → DESCRIBE → update trust policy flow

## Quality Standards

- All user-facing documentation must be bilingual (JA/EN)
- CloudFormation templates must pass cfn-lint
- Terraform configs must pass terraform validate
- Every integration must have E2E verification tasks (see tasks.md)

# FSx for ONTAP S3 Access Point — Production Checklist

## Purpose

Pre-production validation checklist for FSx for ONTAP S3 Access Points used in the metadata catalog architecture.

## Identity and Access

| Item | Description | Status |
|------|-------------|--------|
| S3 AP identity documented | OntapFileSystemIdentity (UNIX UID/GID or Windows user) for each AP | |
| Identity scope minimized | AP identity has read access only to target volume/paths | |
| IAM principals scoped | Only authorized Lambda/ECS roles can use the AP | |
| S3 AP resource policy | Explicit allow list for authorized principals | |
| ONTAP file-system permission mapping | UNIX mode bits or NTFS ACLs aligned with AP identity | |
| SVM / volume / junction path scope | AP attached to correct volume, not broader than needed | |
| AP alias documented | External alias for SDK access | |

## Performance and Capacity

| Item | Description | Status |
|------|-------------|--------|
| Capacity pool read impact | Understand cold file reads during AI enrichment backfill | |
| S3 request concurrency | Lambda/ECS concurrency vs FSx provisioned throughput | |
| Production NFS/SMB latency impact | S3 AP reads do not degrade production workloads | |
| Throttling / retry behavior | Document retry strategy for 503/throttle responses | |
| ListObjectsV2 pagination | Tested at target file count (100K+ files) | |
| Large file handling | Files >100MB have separate processing path (ECS Fargate) | |
| Backfill scheduling | Off-hours for initial scan to minimize production impact | |

## Data Integrity

| Item | Description | Status |
|------|-------------|--------|
| Scan result checksum | Verify scan completeness after each run | |
| scan_run_id tracking | Each scan run has unique ID for reconciliation | |
| Expected vs cataloged file count | Reconciliation report shows delta | |
| Failed file retry list | DLQ or error table for failed reads | |
| Namespace scan reconciliation | Periodic full scan vs incremental delta | |
| File rename/delete detection | Incremental scan detects removed/renamed files | |
| Stale metadata cleanup | Deleted files marked is_deleted in catalog | |

## Monitoring

| Item | Description | Status |
|------|-------------|--------|
| CloudWatch metrics dashboard | FSx throughput, IOPS, latency, capacity pool reads | |
| S3 AP request metrics | Request count, latency, errors per AP | |
| Lambda/ECS error rate | Enrichment pipeline error rate < 5% threshold | |
| DLQ depth alarm | Alert when failed messages exceed threshold | |
| Enrichment backlog metric | Count of files with enrichment_status = 'pending' | |
| Cost allocation tags | Per-AP, per-volume cost tracking | |

## Security

| Item | Description | Status |
|------|-------------|--------|
| VPC endpoint for S3 | S3 traffic stays within VPC (no internet) | |
| VPC endpoint for Bedrock | AI API calls stay within VPC | |
| IAM least privilege | Each role has minimum required permissions | |
| S3 AP policy deny by default | Explicit allow only for authorized operations | |
| Audit trail | CloudTrail logs all S3 AP API calls | |
| No credentials in code | All secrets in Secrets Manager or SSM Parameter Store | |

## Operational Readiness

| Item | Description | Status |
|------|-------------|--------|
| Runbook documented | Scan, enrichment, reconciliation, recovery procedures | |
| Alerting configured | PagerDuty/SNS for critical failures | |
| Backup/recovery tested | S3 Tables snapshot + FSx Snapshot alignment | |
| Capacity planning | Growth estimate for next 6-12 months | |
| Cost model validated | Monthly cost projection vs actual (after 1 month) | |

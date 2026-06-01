# Partner Readiness Checklist

🌐 [日本語](partner-readiness-checklist-ja.md) | English

## Purpose

Pre-engagement checklist for partners deploying the Iceberg Metadata Catalog pattern at customer sites.

## FSx for ONTAP

- [ ] FSx deployment type (Single-AZ / Multi-AZ)
- [ ] SVM name and protocol configuration
- [ ] Volume IDs (target volumes for catalog)
- [ ] Throughput capacity (provisioned)
- [ ] SSD storage capacity and IOPS
- [ ] Capacity pool tiering policy
- [ ] NFS/SMB protocol usage and client count
- [ ] Active Directory integration (if Windows ACLs)
- [ ] Existing FPolicy configuration (if any)

## S3 Access Point

- [ ] Access point per volume (or shared)
- [ ] IAM policy (principals allowed)
- [ ] Associated file-system identity (UNIX UID/GID or Windows domain\\user)
- [ ] VPC restriction (if applicable)
- [ ] Expected request rate (concurrent scans)
- [ ] Prefix scope (which paths are exposed)

## Metadata Catalog

- [ ] File identity method (path hash / inode / content hash)
- [ ] Latest-record view created
- [ ] Path sensitivity policy defined
- [ ] Retention policy defined
- [ ] DR rebinding policy (if SnapMirror)
- [ ] Domain metadata extensions needed (manufacturing, financial, etc.)

## AI Enrichment

- [ ] Bedrock model access enabled (Claude Haiku + Titan Embeddings)
- [ ] File types requiring Vision classification
- [ ] Backfill volume estimate (file count × enrichment ratio)
- [ ] Batch Inference vs real-time decision
- [ ] Human review workflow defined

## Operations

- [ ] CloudWatch dashboard (Lambda + SQS + FSx metrics)
- [ ] FPolicy event design (create/close/rename/delete only)
- [ ] Backfill concurrency limit
- [ ] Iceberg maintenance schedule
- [ ] OpenSearch collection created (if vector search needed)
- [ ] SnapMirror / DR behavior documented

## Governance

- [ ] Lake Formation grants configured
- [ ] Athena Views for column exposure control
- [ ] PII detection language (EN / JA / other)
- [ ] Audit log retention (CloudTrail Trail to S3)
- [ ] Approval evidence template completed

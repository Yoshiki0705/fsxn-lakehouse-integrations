# Governance and Compliance

## Overview

This document defines the governance, security, and compliance framework for FSx for ONTAP Lakehouse integrations. It is designed for regulated industries (healthcare, financial services, public sector) where data classification, access control, audit, and responsibility boundaries must be clearly documented before deployment.

## Data Classification

| Classification | Description | Example Data | Access Control |
|---------------|-------------|--------------|----------------|
| **Public** | Non-sensitive, publishable | Aggregated reports, public datasets | Open read via internet-origin AP |
| **Internal** | Business-sensitive, not regulated | Internal analytics, operational metrics | VPC-origin AP, team-scoped IAM roles |
| **Confidential** | Business-critical, contractual obligations | Financial transactions, customer records | VPC-origin AP, per-user IAM, restricted file system user |
| **Regulated** | Subject to legal/regulatory requirements | PHI (HIPAA), PII (GDPR), PCI DSS data | VPC-origin AP, minimum-privilege IAM, read-only AP user, audit logging mandatory |

## Access Control Architecture

FSx for ONTAP S3 Access Points use a **dual-layer authorization model** ([source](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html)):

```
┌─────────────────────────────────────────────────────────────────┐
│                    Request Flow                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Caller (IAM Principal)                                          │
│       │                                                           │
│       ▼                                                           │
│  ┌─────────────────────────────────────────┐                     │
│  │  Layer 1: AWS IAM Authorization          │                     │
│  │  ─────────────────────────────────────── │                     │
│  │  • IAM identity policy                   │                     │
│  │  • S3 Access Point resource policy       │                     │
│  │  • VPC Endpoint policy (if applicable)   │                     │
│  │  • Service Control Policy (SCP)          │                     │
│  │  • Network origin check (VPC/Internet)   │                     │
│  └─────────────────┬───────────────────────┘                     │
│                    │ ALLOW                                         │
│                    ▼                                               │
│  ┌─────────────────────────────────────────┐                     │
│  │  Layer 2: File System Authorization      │                     │
│  │  ─────────────────────────────────────── │                     │
│  │  • File system user (UNIX or Windows)    │                     │
│  │  • UNIX: mode-bits or NFSv4 ACLs        │                     │
│  │  • NTFS: Windows ACLs                    │                     │
│  │  • Directory/file level permissions      │                     │
│  └─────────────────┬───────────────────────┘                     │
│                    │ ALLOW                                         │
│                    ▼                                               │
│              Access Granted                                        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**Both layers must permit the request.** An explicit Deny in any layer overrides Allow statements in other layers.

### Layer 1: IAM Authorization Details

| Policy Type | Scope | Example Use |
|-------------|-------|-------------|
| IAM Identity Policy | Per-principal (user/role) | Grant analyst role read-only access to AP |
| Access Point Policy | Per-access point | Restrict AP to specific IAM roles or VPC |
| VPC Endpoint Policy | Per-VPC endpoint | Limit which APs are accessible from VPC |
| Service Control Policy | Per-OU/account | Enforce organization-wide restrictions |
| Network Origin | Per-access point (immutable after creation) | VPC-origin: deny all requests not from bound VPC |

### Layer 2: File System Authorization Details

| Security Style | Permission Model | Use Case |
|---------------|-----------------|----------|
| UNIX | mode-bits (rwx) or NFSv4 ACLs | Linux/NFS workloads |
| NTFS | Windows ACLs (full/modify/read) | Windows/SMB workloads |
| Mixed | UNIX effective, NTFS for Windows clients | Hybrid environments |

**Important**: The file system user associated with the access point determines the permission level for ALL requests through that AP. Use the principle of least privilege:
- Read-only analytics → read-only file system user
- ETL write-back → read-write user scoped to specific directories
- Never use root (UID 0) for production access points

## Network Security

### Block Public Access

Amazon S3 enforces Block Public Access by default for all access points attached to FSx for ONTAP volumes. **This setting cannot be modified or disabled.** ([source](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html))

### Network Origin Options

| Origin | Security Level | Use Case | Limitation |
|--------|---------------|----------|------------|
| **VPC** | Highest | Regulated data, internal analytics | Cannot be changed after creation; Athena/managed services cannot access |
| **Internet** | Standard (IAM-controlled) | AWS managed services (Athena, Bedrock, Glue) | Requires strong IAM policies for access control |

**Note**: "Internet origin" does NOT mean public access. All requests still require valid IAM credentials. Block Public Access prevents anonymous access. ([source](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html))

### Recommended Network Architecture for Regulated Data

```
┌─────────────────────────────────────────────────┐
│  VPC (Private Subnets Only)                      │
│                                                   │
│  ┌───────────┐    ┌──────────────────────┐       │
│  │ Analytics │───▶│ S3 Gateway Endpoint  │       │
│  │ Platform  │    │ (in-VPC traffic)     │       │
│  └───────────┘    └──────────┬───────────┘       │
│                              │                    │
│  ┌───────────┐    ┌──────────▼───────────┐       │
│  │On-premises│───▶│ S3 Interface Endpoint│       │
│  │via DX/VPN │    │ (external traffic)   │       │
│  └───────────┘    └──────────┬───────────┘       │
│                              │                    │
│                    ┌─────────▼────────────┐       │
│                    │ S3 Access Point      │       │
│                    │ (VPC origin)         │       │
│                    └─────────┬────────────┘       │
│                              │                    │
│                    ┌─────────▼────────────┐       │
│                    │ FSx for ONTAP Volume │       │
│                    └─────────────────────-┘       │
└─────────────────────────────────────────────────┘
```

## Audit and Logging

| Log Source | What is Captured | Retention | Use |
|-----------|-----------------|-----------|-----|
| **AWS CloudTrail** | FSx API calls (CreateAccessPoint, etc.), S3 data events (GetObject, PutObject via AP) | Configurable (recommend 1+ year for compliance) | Who accessed what, when, from where |
| **FSx for ONTAP audit logs** | NFS/SMB file access events (via ONTAP fpolicy/audit) | Configurable on ONTAP | Direct file system access not through S3 AP |
| **Lakehouse audit logs** | Query history, table modifications (platform-specific) | Platform-dependent | Analytics activity tracking |
| **VPC Flow Logs** | Network traffic to/from FSx ENIs | Configurable | Network-level access verification |
| **S3 Access Point access logs** | S3 data events via CloudTrail | Same as CloudTrail | S3 API-level access audit |

### Enabling S3 Data Events for Access Points

To audit individual object-level operations (GetObject, PutObject) through access points, enable **S3 data events** in CloudTrail:

```json
{
  "EventSelectors": [{
    "ReadWriteType": "All",
    "DataResources": [{
      "Type": "AWS::S3::AccessPoint",
      "Values": ["arn:aws:s3:REGION:ACCOUNT:accesspoint/ACCESS-POINT-NAME"]
    }]
  }]
}
```

## Encryption

| Layer | Mechanism | Key Management | Notes |
|-------|-----------|---------------|-------|
| **At rest** | SSE-FSX (automatic) | AWS KMS managed | All FSx file systems encrypted by default; transparent to applications |
| **In transit (S3 API)** | TLS 1.2+ | AWS managed | HTTPS enforced for S3 API calls |
| **In transit (NFS)** | Kerberos encryption (optional) | Customer managed | For NFS clients accessing same data |
| **In transit (SMB)** | SMB encryption (optional) | Customer managed | For SMB clients accessing same data |

**Note**: SSE-FSX is the only supported server-side encryption mode for S3 Access Points. SSE-S3, SSE-KMS, and SSE-C are not supported. ([source](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html))

## Data Residency

| Aspect | Guarantee |
|--------|-----------|
| Data at rest | Remains in the AWS Region where FSx for ONTAP is deployed |
| S3 Access Point | Must be in same Region as FSx volume ([source](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html)) |
| DR replication | SnapMirror to specified DR Region (customer-controlled) |
| Query results | Written to customer-specified S3 bucket (same or different Region) |
| Backup storage | Same Region as file system, redundant across multiple AZs |

## Responsibility Matrix (RACI)

| Responsibility | AWS | FSx Admin | Lakehouse Admin | Data Owner |
|---------------|-----|-----------|-----------------|------------|
| Physical infrastructure security | **R** | — | — | — |
| FSx file system encryption at rest | **R** | — | — | — |
| FSx file system provisioning | I | **R** | — | — |
| S3 Access Point creation & policy | I | **R** | C | — |
| IAM role/policy for analytics | I | C | **R** | — |
| File system user permissions | I | **R** | C | A |
| Data classification | — | — | C | **R** |
| Lakehouse table access control | — | — | **R** | A |
| Audit log review | — | C | C | **R** |
| Compliance validation | — | C | C | **R** |
| Incident response | C | **R** | **R** | A |

R = Responsible, A = Accountable, C = Consulted, I = Informed

## Industry-Specific Considerations

### Healthcare (HIPAA)

| Requirement | Implementation |
|-------------|---------------|
| PHI access control | VPC-origin AP + minimum-privilege IAM + read-only file system user |
| Audit trail | CloudTrail S3 data events enabled on AP |
| Encryption | SSE-FSX (at rest) + TLS (in transit) — both automatic |
| Data residency | Single-region deployment, no cross-region replication of PHI without BAA |
| De-identification | Glue ETL pipeline for de-identification before analytics access |
| Sample data | Use synthetic data only for development/testing |

### Financial Services (PCI DSS / SOX)

| Requirement | Implementation |
|-------------|---------------|
| Segregation of duties | Separate IAM roles for admin vs. analyst; separate APs per domain |
| Data mesh domain ownership | Per-domain SVMs with per-consumer access points |
| Audit retention | CloudTrail logs retained 7+ years (SOX) |
| Change management | Infrastructure as Code (CloudFormation), PR-based changes |
| DR/BCP | SnapMirror cross-region, documented RTO/RPO |

### Manufacturing (OT/IT Boundary)

| Requirement | Implementation |
|-------------|---------------|
| OT/IT separation | Separate VPCs for OT data collection and IT analytics |
| Edge ingestion | NFS/SMB write from edge → S3 AP read for analytics |
| Long-term retention | FabricPool tiering for cold data |
| Data freshness | Near-real-time (NFS write immediately visible via S3 AP) |

## Secure Reference Deployment: Healthcare Read-Only Analytics

```yaml
# Minimal secure deployment for healthcare analytics
Components:
  FSx for ONTAP:
    deployment_type: MULTI_AZ
    throughput_capacity: 512  # MB/s
    storage_capacity: 1024   # GB
    ontap_version: "9.17.1+"
    
  S3 Access Point:
    network_origin: VPC      # Private access only
    file_system_user: 
      type: UNIX
      username: analytics_reader  # Read-only user
    block_public_access: true     # Enforced (cannot disable)
    
  IAM:
    role: healthcare-analytics-role
    policy:
      - Effect: Allow
        Action: [s3:GetObject, s3:ListBucket]
        Resource: 
          - "arn:aws:s3:REGION:ACCOUNT:accesspoint/healthcare-ap"
          - "arn:aws:s3:REGION:ACCOUNT:accesspoint/healthcare-ap/object/*"
      # No PutObject, DeleteObject — read-only
      
  VPC:
    endpoint_type: Gateway  # For in-VPC analytics
    endpoint_policy: Scoped to healthcare-ap only
    
  Audit:
    cloudtrail: 
      data_events: enabled
      resource: "arn:aws:s3:REGION:ACCOUNT:accesspoint/healthcare-ap"
      retention: 7_years
      
  Data:
    type: Synthetic only (no real PHI in dev/test)
    format: Parquet (de-identified)
```

## Pre-Deployment Checklist

### Healthcare
- [ ] De-identification pipeline validated
- [ ] No PHI in sample/test data
- [ ] VPC-origin access point (if not using Athena/managed services)
- [ ] Read-only file system user
- [ ] CloudTrail S3 data events enabled
- [ ] Audit log retention configured (7+ years)
- [ ] BAA in place with AWS
- [ ] Data residency confirmed (single region)

### Financial Services
- [ ] Segregation of duties validated (admin ≠ analyst roles)
- [ ] Per-domain access points with scoped policies
- [ ] CloudTrail enabled with long-term retention
- [ ] SnapMirror DR configured and tested
- [ ] Change management process documented
- [ ] Encryption verified (at rest + in transit)

### Manufacturing
- [ ] OT/IT network separation confirmed
- [ ] Edge data ingestion path validated
- [ ] Data freshness SLA documented
- [ ] Long-term retention policy configured (FabricPool)

---

## Safety vs. Assurance

Technical safety and organizational assurance are distinct concerns. Regulated industries require both.

| Aspect | Safety (技術的安全性) | Assurance (説明可能な安心) |
|--------|---------------------|--------------------------|
| **What it answers** | "Is the system technically secure?" | "Can we explain WHY it is secure to stakeholders?" |
| **Audience** | Security engineers, auditors | CxO, compliance officers, patients, regulators |
| **Evidence** | Configuration, test results, penetration tests | Documentation, diagrams, responsibility matrices, audit reports |
| **FSx S3 AP controls** | IAM policy, AP policy, VPC endpoint, file system ACL, SSE-FSX, Block Public Access | Architecture diagrams, RACI matrix, audit log samples, incident response procedures |

### Building Assurance from Safety Controls

| Safety Control | Assurance Artifact |
|---------------|-------------------|
| Block Public Access (enforced, cannot disable) | "No anonymous access is possible — this is enforced by AWS at the infrastructure level and cannot be overridden by any administrator" |
| Dual-layer authorization | Architecture diagram showing both IAM and file system checks must pass |
| VPC-origin access point | "Data can only be accessed from within our private network — requests from the internet are rejected before any policy evaluation" |
| CloudTrail S3 data events | Monthly audit report showing who accessed what data, when, from where |
| SSE-FSX encryption | "All data is encrypted at rest using AWS KMS — encryption is automatic and cannot be disabled" |
| Read-only file system user | "The analytics system can only read data — it is physically impossible for it to modify or delete files" |

### Assurance Documentation Checklist

- [ ] Non-technical architecture overview (1-page diagram with plain language)
- [ ] Data flow diagram showing where data resides and who can access it
- [ ] RACI matrix signed by all responsible parties
- [ ] Audit log sample report (redacted) demonstrating monitoring capability
- [ ] Incident response procedure document
- [ ] Annual access review process document
- [ ] Third-party explanation materials (for regulators, patients, partners)

---

## Generative AI / RAG Governance

When using FSx S3 AP as a data source for generative AI (e.g., Amazon Bedrock Knowledge Bases), additional governance considerations apply.

### Data Handling for AI/RAG

| Concern | Governance Control |
|---------|-------------------|
| **PHI/PII in source documents** | De-identification pipeline BEFORE indexing; never index raw PHI/PII |
| **Embedding storage location** | Bedrock Knowledge Bases stores embeddings in a customer-managed vector store (OpenSearch Serverless); ensure same-region, same-account |
| **Vector store encryption** | OpenSearch Serverless encrypts at rest by default (AWS KMS) |
| **Embedding deletion** | When source document is deleted, re-sync Knowledge Base to remove corresponding embeddings |
| **Prompt/response logging** | Enable CloudWatch Logs for Bedrock model invocations; retain per compliance requirements |
| **Human review requirement** | RAG responses in healthcare/financial MUST include human review before action |
| **Hallucination mitigation** | Configure Bedrock guardrails; include source citation in responses; validate against source documents |
| **Synthetic data for testing** | Use synthetic documents for development/testing; never use real PHI/PII in non-production |
| **Model access policy** | Restrict which Bedrock models can be invoked; use IAM policies on `bedrock:InvokeModel` |

### RAG Architecture for Regulated Industries

```
┌─────────────────────────────────────────────────────────────┐
│  Regulated RAG Architecture                                  │
│                                                              │
│  ┌──────────────┐     ┌─────────────────┐                  │
│  │ Source Docs   │     │ De-identification│                  │
│  │ (FSx Volume)  │────▶│ Pipeline (Glue)  │                  │
│  │ NFS/SMB write │     │ Remove PHI/PII   │                  │
│  └──────────────┘     └────────┬────────┘                  │
│                                │                             │
│                       ┌────────▼────────┐                   │
│                       │ Clean Documents  │                   │
│                       │ (FSx Volume)     │                   │
│                       └────────┬────────┘                   │
│                                │                             │
│                       ┌────────▼────────┐                   │
│                       │ S3 Access Point  │                   │
│                       │ (read-only user) │                   │
│                       └────────┬────────┘                   │
│                                │                             │
│                       ┌────────▼────────┐                   │
│                       │ Bedrock KB       │                   │
│                       │ (ingestion)      │                   │
│                       └────────┬────────┘                   │
│                                │                             │
│                       ┌────────▼────────┐                   │
│                       │ Vector Store     │                   │
│                       │ (OpenSearch)     │                   │
│                       └────────┬────────┘                   │
│                                │                             │
│  ┌──────────────┐     ┌───────▼─────────┐                  │
│  │ User Query    │────▶│ Bedrock Agent    │                  │
│  │ (with guardrails)   │ + Guardrails     │                  │
│  └──────────────┘     └───────┬─────────┘                  │
│                                │                             │
│                       ┌────────▼────────┐                   │
│                       │ Human Review     │                   │
│                       │ (required)       │                   │
│                       └─────────────────┘                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Lifecycle Management

### Retention Policy Framework

| Data Type | Retention Period | Storage Tier | Deletion Method |
|-----------|----------------|-------------|-----------------|
| Active analytics data | Indefinite (while in use) | FSx SSD | Manual review + approval |
| Historical analytics data | Per business requirement | FSx Capacity Pool (FabricPool) | Automated tiering, manual deletion |
| Audit logs (CloudTrail) | 7 years (SOX) / 6 years (HIPAA) | S3 (CloudTrail destination) | S3 Lifecycle policy |
| ONTAP Snapshots | Per snapshot policy (e.g., 7 daily, 4 weekly) | FSx SSD (copy-on-write) | Automatic per policy |
| RAG embeddings | Same as source document retention | OpenSearch Serverless | Re-sync Knowledge Base after source deletion |
| Query results (Athena) | 90 days (default) or per policy | S3 (Athena results bucket) | S3 Lifecycle policy |

### Data Deletion Procedure

1. **Identify**: Determine which files/records must be deleted (data owner approval required)
2. **Verify dependencies**: Check if data is referenced by Glue Catalog, Bedrock KB, or other services
3. **Delete from source**: Remove via NFS/SMB or S3 AP (DeleteObject)
4. **Update catalog**: Re-run Glue Crawler or manually drop table/partition
5. **Re-sync AI**: If used by Bedrock KB, trigger re-sync to remove embeddings
6. **Verify deletion**: Confirm via ListObjectsV2 and catalog query
7. **Audit**: CloudTrail records the deletion event automatically

---

## Incident Response

### Incident Response Flow

```
Detection → Triage → Containment → Investigation → Recovery → Post-mortem
    │          │          │              │             │           │
    ▼          ▼          ▼              ▼             ▼           ▼
CloudTrail  Severity   Revoke AP     CloudTrail    Snapshot    Document
Alert       Assessment policy/IAM    log analysis  restore     & improve
```

### Incident Scenarios and Response

| Scenario | Detection | Containment | Recovery |
|----------|-----------|-------------|----------|
| Unauthorized data access | CloudTrail alert on unexpected principal | Update AP policy to deny; revoke IAM credentials | Review access logs; assess data exposure |
| AP policy misconfiguration | CloudTrail `PutAccessPointPolicy` event | Revert to known-good policy (IaC) | Verify access restored for authorized users |
| Data corruption (accidental) | Application error reports; data validation failure | Isolate affected volume (if needed) | Restore from ONTAP Snapshot |
| Ransomware | Unusual write patterns; file extension changes | Disconnect NFS/SMB clients; AP remains read-only if configured | Restore from immutable Snapshot |
| Region failure | AWS Health Dashboard; connectivity loss | Activate DR runbook | SnapMirror failover; create new AP in DR region |

### Snapshot Restore Approval Flow

For regulated environments, snapshot restore should follow an approval process:

1. **Request**: Operator identifies need for restore (with justification)
2. **Approve**: Data owner or compliance officer approves (documented)
3. **Notify**: Inform all stakeholders (analytics teams, application owners)
4. **Execute**: Perform snapshot restore
5. **Reconcile**: Re-run Glue Crawler; verify catalog consistency
6. **Validate**: Confirm data integrity via sample queries
7. **Document**: Record restore event, reason, approver, outcome

### DR Failover Governance Checklist

- [ ] SnapMirror relationship confirmed healthy (lag within RPO)
- [ ] DR region AP creation procedure documented and tested
- [ ] IAM roles/policies replicated to DR region
- [ ] Glue Catalog recreation procedure documented
- [ ] Application configuration update procedure documented
- [ ] Communication plan for stakeholders activated
- [ ] Post-failover validation queries defined
- [ ] Failback procedure documented

---

## References

- [Managing access point access — Dual-layer authorization](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html)
- [Configuring network access for Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
- [Access point compatibility](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)
- [Monitoring FSx for ONTAP API Calls with AWS CloudTrail](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/logging-using-cloudtrail-win.html)
- [Access points naming rules, restrictions, and limitations](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html)
- [Build a RAG application using Amazon Bedrock Knowledge Bases](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)

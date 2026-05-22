# Partner Offering Guide

## Target Customers

| Segment | Profile | Pain Points |
|---------|---------|-------------|
| Enterprise NAS users | On-premises NetApp ONTAP / NAS users with 10TB+ file data | Data copy required for analytics, S3-native services inaccessible from NAS |
| FSx for ONTAP adopters | AWS customers already running FSx for ONTAP for NFS/SMB workloads | Lakehouse/analytics platforms require S3, creating data silos |
| Hybrid cloud | Organizations with on-premises ONTAP + AWS, using SnapMirror for DR/migration | Want to leverage cloud analytics without re-architecting storage |

## Business Challenge

Organizations with file-based data on NAS/ONTAP face a fundamental disconnect:

1. **Data duplication**: Analytics platforms (Databricks, Snowflake, Athena) require data in S3, forcing ETL pipelines to copy data from NAS to S3
2. **Governance fragmentation**: Separate access controls for NAS (UNIX/NTFS permissions) and S3 (IAM policies) create compliance gaps
3. **Operational overhead**: Synchronization pipelines add latency, cost, and failure points
4. **Stranded investment**: Existing ONTAP features (deduplication, snapshots, tiering) are lost when data is copied to S3

## Solution: FSx for ONTAP + S3 Access Points + Lakehouse Integration

Amazon FSx for ONTAP S3 Access Points enable S3 API access to file data stored on FSx for ONTAP volumes without data movement. Applications and AWS services that work with S3 can directly read and write file data through the access point.

**Key technical facts** (per [AWS documentation](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)):
- Supported S3 operations: GetObject, PutObject, DeleteObject, ListObjectsV2, HeadObject, Multipart Upload, CopyObject (same access point only)
- Dual-layer authorization: IAM policy evaluation + file system user permissions (UNIX or Windows)
- Latency: Tens of milliseconds range, consistent with S3 bucket access
- Throughput: Depends on FSx file system provisioned throughput capacity
- Block Public Access enforced by default (cannot be disabled)
- Requires ONTAP version 9.17.1 or later

## Business Outcomes

| Outcome | Metric |
|---------|--------|
| Eliminate data copies | N copies → 1 authoritative source |
| Remove sync pipelines | Eliminate NAS → S3 ETL jobs |
| Accelerate time-to-insight | Days of pipeline setup → hours of direct query |
| Preserve NFS/SMB access | Existing workloads unchanged |
| Unified governance | Single data location, dual-layer access control |
| Enable AI/ML on file data | Bedrock, SageMaker, EMR access via S3 AP |

## Good / Better / Best Configurations

### Good: Single-Account Read-Only Analytics

**Scope**: Single AWS account, single SVM, read-only analytics

| Component | Configuration |
|-----------|--------------|
| FSx for ONTAP | Single-AZ, 1 SVM, 1 volume |
| S3 Access Point | Internet origin, read-only file system user |
| Analytics | Athena + Glue Data Catalog |
| Security | IAM role per analyst team, read-only UNIX user |
| Monitoring | CloudTrail for API calls |

**Use case**: Ad-hoc SQL queries on file data (CSV, Parquet, JSON) without data movement.

**Validated AWS integration**: [Query files with SQL using Amazon Athena](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

---

### Better: VPC-Restricted Access with Catalog Integration

**Scope**: VPC-restricted access, Glue Catalog / Unity Catalog integration, read-write for ETL

| Component | Configuration |
|-----------|--------------|
| FSx for ONTAP | Single-AZ or Multi-AZ, multiple volumes |
| S3 Access Point | VPC origin (bound to specific VPC), read-write file system user |
| Analytics | Databricks Unity Catalog / Snowflake External Stage / Glue ETL |
| Security | VPC endpoint policy + access point policy + file system permissions |
| Networking | Gateway endpoint (in-VPC) + Interface endpoint (on-premises via Direct Connect) |
| Monitoring | CloudTrail + CloudWatch metrics |

**Use case**: ETL pipelines reading source data from FSx for ONTAP, transforming with Glue/EMR, writing curated results back.

**Validated AWS integrations**:
- [Build ETL pipelines using AWS Glue](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)
- [Run Spark jobs using Amazon EMR Serverless](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-run-spark-with-emr-serverless.html)

---

### Best: Multi-Account Governance with DR and AI

**Scope**: Multi-account, Lake Formation / IAM / S3 AP policy, SnapMirror DR, audit logging, AI/RAG

| Component | Configuration |
|-----------|--------------|
| FSx for ONTAP | Multi-AZ, multiple SVMs, SnapMirror to DR region |
| S3 Access Points | Per-consumer access points with scoped IAM policies |
| Analytics | Databricks + Snowflake + Athena (multi-platform) |
| AI/ML | Amazon Bedrock Knowledge Bases for RAG |
| Security | Lake Formation + S3 AP policy + VPC origin + file system ACLs |
| Governance | CloudTrail, ONTAP audit logs, data classification tags |
| DR | SnapMirror cross-region replication, ONTAP Snapshots |

**Use case**: Enterprise data mesh with domain-specific access points, AI-powered document search, and regulated data governance.

**Validated AWS integrations**:
- [Build a RAG application using Amazon Bedrock Knowledge Bases](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)
- All integrations from Good and Better tiers

---

## Sellable Use Case Names

| Use Case Name | Industry | Pattern | Tier |
|---------------|----------|---------|------|
| Zero-Copy NAS Analytics for Manufacturing | Manufacturing | Read-Only Analytics | Good |
| Regulated Data Lakehouse for Healthcare Research | Healthcare | Managed Tables (Read) | Better |
| Financial Data Mesh with FSxN and S3 Access Points | Financial Services | Data Sharing | Best |
| AI-Powered Document Intelligence on Enterprise Files | Cross-industry | RAG with Bedrock | Best |
| Hybrid Cloud Analytics Bridge | Cross-industry | ETL Pipeline | Better |
| Media Asset Analytics without Data Migration | Media & Entertainment | Read-Only Analytics | Good |

## Implementation Steps per Use Case

### Zero-Copy NAS Analytics for Manufacturing

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Deploy FSx for ONTAP with S3 Access Point | Day 1-2 |
| 2 | Configure Glue Crawler on access point | Day 2 |
| 3 | Validate Athena queries on sample data | Day 3 |
| 4 | Connect BI tools (QuickSight) | Day 4-5 |
| **Success criteria** | Query latency < 10s for 1GB dataset, zero data copies | |

### Regulated Data Lakehouse for Healthcare Research

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Deploy Multi-AZ FSx for ONTAP with VPC-origin S3 AP | Week 1 |
| 2 | Configure Lake Formation permissions | Week 1 |
| 3 | Set up Glue ETL for de-identification pipeline | Week 2 |
| 4 | Register external tables in analytics platform | Week 2 |
| 5 | Validate audit trail and access controls | Week 3 |
| **Success criteria** | PHI never leaves VPC, audit trail complete, query < 30s | |

### Financial Data Mesh with FSxN and S3 Access Points

| Step | Action | Timeline |
|------|--------|----------|
| 1 | Multi-account setup with per-domain SVMs | Week 1-2 |
| 2 | Per-consumer S3 Access Points with scoped policies | Week 2-3 |
| 3 | Cross-account IAM roles and VPC endpoints | Week 3 |
| 4 | SnapMirror DR configuration | Week 4 |
| 5 | Databricks Unity Catalog + Snowflake External Stage | Week 4-5 |
| **Success criteria** | Domain isolation verified, DR RTO < 1h, multi-platform query | |

---

## Partner Motion

### Who Sells This Offering

| Partner Type | Role | Value Proposition | Typical Deal |
|-------------|------|-------------------|--------------|
| **SIer / Consulting** | Design + implement + migrate | NAS modernization / data platform renewal projects | Existing ONTAP customers upgrading to cloud analytics |
| **MSP (Managed Service Provider)** | Operate + monitor + optimize | FSxN + S3 AP + audit as managed service | Ongoing operations for regulated industries |
| **Data / AI Partner** | Build analytics + AI solutions | Bedrock RAG / Athena / Glue / Databricks integration | AI-powered document intelligence, data mesh |
| **NetApp Channel Partner** | Extend ONTAP investment to cloud analytics | Existing ONTAP customer base expansion to AWS analytics | Hybrid cloud analytics bridge |
| **ISV** | Embed FSxN S3 AP in product | S3-compatible product integration without data copy | SaaS analytics on customer file data |

### Partner Engagement Model

```
Discovery → Assessment → PoC → Production → Managed Operations
    │            │          │         │              │
    ▼            ▼          ▼         ▼              ▼
  SIer/       SIer/      SIer/     SIer/          MSP
  NetApp      NetApp     Data/AI   Data/AI
  Partner     Partner    Partner   Partner
```

### Partner Enablement Checklist

- [ ] Complete FSx for ONTAP S3 Access Points technical training
- [ ] Review compatibility matrix (understand what works and what does NOT)
- [ ] Build internal PoC with Good tier configuration
- [ ] Develop customer-facing demo environment
- [ ] Create industry-specific pitch deck using 1-page template below
- [ ] Identify 2-3 target accounts with existing NAS/ONTAP footprint

---

## 1-Page Partner Pitch Template

```
┌─────────────────────────────────────────────────────────────┐
│  FSxN Lakehouse Integration: Zero-Copy Analytics on NAS     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. CUSTOMER PAIN                                            │
│     "We copy TB of file data to S3 just to run analytics.   │
│      It costs $X/month, takes Y days to set up, and         │
│      creates governance gaps."                               │
│                                                              │
│  2. WHY NOW                                                  │
│     • FSx for ONTAP S3 Access Points (GA, ONTAP 9.17.1+)   │
│     • AWS validated integrations: Athena, Glue, EMR,        │
│       Bedrock, Lambda, CloudFront, Transfer Family           │
│     • AI/RAG requires access to enterprise file data        │
│                                                              │
│  3. PROPOSED SOLUTION                                        │
│     FSx for ONTAP + S3 Access Point → Direct S3 API access  │
│     to existing file data. No copy. No sync pipeline.        │
│                                                              │
│  4. GOOD / BETTER / BEST                                     │
│     Good:   Athena read-only analytics ($)                   │
│     Better: Glue ETL + VPC-restricted access ($$)            │
│     Best:   Multi-platform + AI/RAG + DR ($$$)               │
│                                                              │
│  5. EXPECTED BUSINESS OUTCOME                                │
│     • Eliminate N data copies → save $X/month storage        │
│     • Remove sync pipelines → save Y hours/week ops         │
│     • Analytics in hours, not days                           │
│     • AI/RAG on existing documents without migration         │
│                                                              │
│  6. PoC PACKAGE                                              │
│     • 2-week PoC with sample data                            │
│     • Deliverable: Working Athena/Glue query on FSxN data    │
│     • Success criteria: Query < 30s, zero data copies        │
│     • Cost: < $500 AWS charges                               │
│                                                              │
│  7. PARTNER ROLE                                             │
│     • [Partner name] designs, implements, and operates       │
│     • AWS provides technical validation and co-sell support  │
│     • NetApp provides ONTAP expertise and licensing          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Anti-Patterns: What NOT to Sell

| Anti-Pattern | Why It Fails | What to Propose Instead |
|-------------|-------------|------------------------|
| Delta Lake write / MERGE / compaction on FSx S3 AP | Delta commit protocol requires atomic rename, which is not supported by FSx S3 AP ([API support](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)) | Read-only analytics on Delta tables, or use native S3 for Delta write path |
| Internet-origin AP as default for regulated industries | Regulated data requires network-level isolation; VPC-origin provides built-in explicit Deny for non-VPC traffic | VPC-origin AP for Confidential/Regulated data (note: Athena requires internet-origin) |
| Claiming "S3 fully compatible" | FSx S3 AP supports a subset of S3 operations. No Object Versioning, no conditional writes, no presigned URLs, 5GB upload limit | Use precise language: "S3 API access for supported operations" with link to compatibility matrix |
| Selling unverified Iceberg write path as production-ready | Iceberg write with external catalog is Experimental, not Verified | Position as "read-only verified, write path under validation" |
| Ignoring FSx throughput provisioning | Customers expect S3-like unlimited throughput; FSx S3 AP throughput is bounded by provisioned capacity | Size FSx throughput to workload requirements; include in PoC validation |
| Proposing FSx S3 AP for high-concurrency, small-file workloads | Tens of milliseconds latency + provisioned throughput limits make this suboptimal vs native S3 | Use for large sequential scans, batch analytics, document retrieval; not for high-frequency API calls |

### Red Lines for Partner Proposals

1. **Never** claim FSx S3 AP is a drop-in replacement for S3 buckets
2. **Never** propose Delta/Hudi write operations without explicit customer acknowledgment of limitations
3. **Never** use real PHI/PII in PoC environments
4. **Never** propose internet-origin AP for healthcare/financial without documenting the security trade-off
5. **Always** include compatibility matrix reference in technical proposals

---

## Competitive Positioning

### When to Use FSx S3 AP vs. Alternatives

| Approach | Data Copy? | NAS Impact | Time to Analytics | Governance | AI/RAG | Best For |
|----------|-----------|-----------|-------------------|-----------|--------|----------|
| **FSx S3 AP (this solution)** | No | None | Hours | Unified (dual-layer) | Yes (Bedrock) | Existing NAS data, read-heavy analytics, AI on documents |
| **Native S3 + DataSync** | Yes (full copy) | None | Days (initial sync) | Separate (S3 vs NAS) | Yes | Write-heavy Lakehouse, Delta/Iceberg managed tables |
| **Native S3 + ETL pipeline** | Yes (transformed) | None | Days-weeks | Separate | Yes | Complex transformations, medallion architecture on S3 |
| **Snowflake External Stage on S3** | Yes (to S3 first) | None | Days | Snowflake-managed | Limited | Snowflake-centric organizations |
| **Databricks on native S3** | Yes (to S3 first) | None | Days | Unity Catalog on S3 | Yes | Databricks-centric, Delta write-heavy |
| **NetApp BlueXP tiering** | Partial (cold tier) | Minimal | N/A (not analytics) | ONTAP-managed | No | Cost optimization, not analytics |
| **On-premises analytics** | No | None | Weeks (setup) | On-prem tools | Limited | Air-gapped environments |

### Decision Framework

```
Q1: Does the customer need to WRITE Lakehouse tables (Delta/Iceberg)?
  → Yes: Use native S3 for write path; FSx S3 AP for read-only source data
  → No: FSx S3 AP is ideal

Q2: Does the customer need sub-millisecond latency or unlimited concurrency?
  → Yes: Use native S3
  → No: FSx S3 AP (tens of ms latency, provisioned throughput)

Q3: Does the customer have existing NAS/ONTAP data they want to analyze?
  → Yes: FSx S3 AP eliminates the copy
  → No: Native S3 is simpler

Q4: Does the customer need NFS/SMB access alongside S3 analytics?
  → Yes: FSx S3 AP (multi-protocol on same data)
  → No: Native S3 may be sufficient

Q5: Does the customer need AI/RAG on existing documents?
  → Yes: FSx S3 AP + Bedrock Knowledge Bases
  → No: Evaluate based on Q1-Q4
```

---

## References

- [Accessing your data via Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)
- [Access point compatibility](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)
- [Using access points with AWS services](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html)
- [Configuring network access for Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
- [Amazon FSx for NetApp ONTAP performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)

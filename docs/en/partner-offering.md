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
| Financial Data Mesh with FSx for ONTAP and S3 Access Points | Financial Services | Data Sharing | Best |
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

### Financial Data Mesh with FSx for ONTAP and S3 Access Points

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
| **MSP (Managed Service Provider)** | Operate + monitor + optimize | FSx for ONTAP + S3 AP + audit as managed service | Ongoing operations for regulated industries |
| **Data / AI Partner** | Build analytics + AI solutions | Bedrock RAG / Athena / Glue / Databricks integration | AI-powered document intelligence, data mesh |
| **NetApp Channel Partner** | Extend ONTAP investment to cloud analytics | Existing ONTAP customer base expansion to AWS analytics | Hybrid cloud analytics bridge |
| **ISV** | Embed FSx for ONTAP S3 AP in product | S3-compatible product integration without data copy | SaaS analytics on customer file data |

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
│  FSx for ONTAP Lakehouse Integration: Zero-Copy Analytics on NAS     │
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
│     • Deliverable: Working Athena/Glue query on FSx for ONTAP data    │
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
| Iceberg write (CREATE TABLE / INSERT) on FSx S3 AP | Iceberg S3FileIO cannot handle S3 AP alias for metadata write/verify. NullPointerException during commit (verified 2026-05-24). | Read-only analytics on pre-existing Iceberg tables, or use native S3 for Iceberg warehouse |
| **Any transactional table format write on FSx S3 AP** | **All Lakehouse formats (Delta, Iceberg, Hudi) require metadata operations that fail on S3 AP** — atomic rename (Delta/Hudi) or metadata file write/verify (Iceberg). | **Use FSx S3 AP for read-only analytics and flat file writes (Parquet append). Use native S3 for transactional table writes.** |
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
| **Snowflake External Stage on FSx S3 AP** | No (zero-copy read) | None | Hours | Snowflake-managed (Tags, Row Policy, Masking) | Yes (Cortex AI, Cortex Search) | Snowflake customers needing governed AI on NAS data. COPY INTO → Managed Iceberg for open format sharing. |
| **Databricks on native S3** | Yes (to S3 first) | None | Days | Unity Catalog on S3 | Yes | Databricks-centric, Delta write-heavy |
| **NetApp Console tiering** | Partial (cold tier) | Minimal | N/A (not analytics) | ONTAP-managed | No | Cost optimization, not analytics |
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

## Co-sell Ready Package

Materials and processes for AWS + Partner joint selling.

### Target Account Criteria

| Criterion | Indicator |
|-----------|-----------|
| Existing NAS/ONTAP footprint | ≥ 10 TB file data on NetApp ONTAP (on-prem or FSx for ONTAP) |
| Analytics initiative | Active or planned data lake / lakehouse / BI project |
| Cloud adoption stage | AWS account active; VPC deployed |
| Pain signal | Complaints about data copy cost, sync pipeline failures, or analytics access delays |
| Regulatory driver | Compliance requirement driving data governance improvement |
| AI/ML interest | Exploring or piloting generative AI / RAG on enterprise documents |

### Discovery Questions

1. "How much file data do you currently copy to S3 for analytics? What does that cost monthly?"
2. "How long does it take from data creation to analytics availability?"
3. "Do you have separate access controls for NAS and S3? How do you audit cross-system access?"
4. "Are there documents on your file shares that you'd like to make searchable with AI?"
5. "What analytics platforms are you using or evaluating (Databricks, Snowflake, Athena)?"
6. "What compliance requirements affect your data architecture decisions?"

### Qualification Checklist

- [ ] Customer has ≥ 10 TB on NAS/ONTAP
- [ ] Customer has active AWS account with VPC
- [ ] Customer has identified analytics use case
- [ ] Customer budget owner identified
- [ ] Technical decision maker engaged
- [ ] No blocker: customer can run ONTAP 9.17.1+
- [ ] Same-region deployment feasible

### Customer Objection Handling

| Objection | Response |
|-----------|----------|
| "We already copy to S3, it works fine" | "What's the monthly cost of that pipeline? What happens when it fails? FSx S3 AP eliminates that entirely." |
| "Is it really S3 compatible?" | "It supports the core S3 operations for analytics (Get, Put, List, Delete). Here's the exact compatibility matrix. Read-only analytics is fully verified." |
| "What about performance?" | "Latency is tens of milliseconds — same as S3. Throughput depends on your FSx provisioning. We size it to your workload in the PoC." |
| "We need Delta Lake write" | "Delta write requires atomic rename which isn't supported. We recommend FSx S3 AP for source data reads, native S3 for Delta write targets." |
| "Our security team will block this" | "Block Public Access is enforced by default. Dual-layer auth (IAM + file system). VPC-origin option for network isolation. Here's the governance doc." |

### PoC SOW Template Outline

```
1. Objective: Validate FSx S3 AP for [use case]
2. Scope: [Good/Better/Best tier]
3. Duration: 2 weeks
4. Deliverables:
   - Working query on FSx data via [Athena/Glue/Bedrock]
   - Performance benchmark results
   - Security validation report
   - Cost comparison (current vs FSx S3 AP)
5. Success criteria: [from kpi-and-validation.md]
6. Resources: Partner SA (X days), Customer admin (Y hours)
7. AWS charges estimate: < $1,000
8. Go/No-go decision: End of Week 2
```

---

## First Deal Playbook (by Partner Type)

### SIer: NAS Modernization Assessment + Analytics PoC

| Phase | Activity | Duration | Deliverable |
|-------|----------|----------|-------------|
| 1. Assessment | Inventory NAS data, identify analytics candidates | 1 week | Assessment report |
| 2. Design | Architecture for Good/Better tier | 1 week | Architecture document |
| 3. PoC | Deploy FSx + S3 AP + Athena/Glue | 2 weeks | Working demo + benchmark |
| 4. Proposal | Production deployment proposal | 1 week | SOW + cost estimate |
| **First deal size** | Assessment + PoC: $15K-30K | | |

### MSP: Read-Only Analytics Managed Package

| Phase | Activity | Duration | Deliverable |
|-------|----------|----------|-------------|
| 1. Onboard | Deploy FSx + S3 AP + monitoring | 2 weeks | Production environment |
| 2. Operate | Monthly monitoring, patching, optimization | Ongoing | Monthly report |
| 3. Expand | Add Glue ETL, Bedrock RAG | Per request | Updated architecture |
| **Revenue model** | Setup fee + monthly managed fee | | |
| **First deal size** | Setup: $10K, Monthly: $3K-5K | | |

### Data/AI Partner: Bedrock RAG PoC Package

| Phase | Activity | Duration | Deliverable |
|-------|----------|----------|-------------|
| 1. Data prep | Identify documents, configure S3 AP | 1 week | Data source ready |
| 2. RAG build | Bedrock Knowledge Base + agent | 2 weeks | Working RAG application |
| 3. Evaluate | Accuracy testing, user feedback | 1 week | Evaluation report |
| 4. Production | Hardening, monitoring, guardrails | 2 weeks | Production RAG system |
| **First deal size** | RAG PoC: $20K-40K | | |

### NetApp Channel Partner: ONTAP Customer Analytics Extension

| Phase | Activity | Duration | Deliverable |
|-------|----------|----------|-------------|
| 1. Identify | Existing ONTAP customers with analytics needs | Ongoing | Target list |
| 2. Workshop | Joint workshop: ONTAP + AWS analytics | 1 day | Customer interest |
| 3. PoC | FSx migration + S3 AP + analytics | 3 weeks | Working solution |
| **First deal size** | Workshop + PoC: $10K-20K | | |

### ISV: Governed File Access Integration

| Phase | Activity | Duration | Deliverable |
|-------|----------|----------|-------------|
| 1. Integration | S3 AP integration in ISV product | 4-6 weeks | Feature release |
| 2. Certification | AWS validation, documentation | 2 weeks | Certified integration |
| 3. GTM | Joint marketing, customer pilots | Ongoing | Pipeline |
| **Revenue model** | Product feature (included in license) + services | | |

---

## Partner Monetization Model

| Revenue Stream | Description | Typical Range | Recurring? |
|---------------|-------------|---------------|-----------|
| Assessment / Discovery | NAS inventory, analytics readiness evaluation | $10K-25K | No |
| Architecture Design | Solution design, security review | $15K-40K | No |
| PoC Implementation | 2-4 week proof of concept | $15K-50K | No |
| Production Deployment | Full implementation + testing | $50K-200K | No |
| Managed Operations | Monitoring, patching, optimization, support | $3K-10K/month | Yes |
| Security/Compliance Review | Annual audit, policy review, penetration test | $10K-30K/year | Yes |
| RAG/AI Integration | Bedrock KB setup, prompt engineering, evaluation | $20K-60K | No |
| Optimization Service | Quarterly performance review, cost optimization | $5K-15K/quarter | Yes |
| Training & Enablement | Customer team training on operations | $5K-15K | No |

### Revenue Projection (First Year per Customer)

```
Conservative (Good tier):
  Assessment:     $15K
  PoC:            $20K
  Deployment:     $50K
  Operations:     $36K (12 × $3K)
  Total Year 1:   $121K

Growth (Better tier + RAG):
  Assessment:     $20K
  PoC:            $30K
  Deployment:     $100K
  RAG integration: $40K
  Operations:     $72K (12 × $6K)
  Total Year 1:   $262K
```

---

## Path to Market

```
Phase 1: Internal Validation (Month 1-2)
  └─ Build internal PoC
  └─ Train partner SA/delivery team
  └─ Document offering in partner portal

Phase 2: First Customer (Month 2-4)
  └─ Identify target account (with AWS account team)
  └─ Joint discovery call
  └─ PoC delivery
  └─ Case study (anonymized if needed)

Phase 3: Offering Publication (Month 4-6)
  └─ Reference architecture on partner website
  └─ AWS Partner Solutions Finder listing
  └─ Joint blog post / webinar with AWS
  └─ Conference presentation (AWS Summit, re:Invent)

Phase 4: Scale (Month 6-12)
  └─ Repeatable delivery methodology
  └─ Junior consultant enablement
  └─ AWS Marketplace private offer (if applicable)
  └─ Multi-customer pipeline
  └─ Quarterly business review with AWS partner team
```

---

## Partner Prioritization Matrix

Score each candidate partner (1-5 per criterion) to determine engagement priority.

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Existing FSx / NetApp practice | 5 | Already delivers ONTAP solutions |
| Data & analytics capability | 4 | Has Databricks/Snowflake/Athena expertise |
| Industry footprint (healthcare/finance/manufacturing) | 4 | Active in regulated industries |
| Managed service capability | 3 | Can operate ongoing environments |
| AWS sales alignment | 5 | Active co-sell relationship with AWS account teams |
| Customer base with NAS-heavy workloads | 5 | Existing customers with 10TB+ NAS |
| Executive sponsor availability | 3 | Partner leadership committed to new offering |
| First-deal readiness | 4 | Can execute within 60 days |

### Prioritization Tiers

| Tier | Score Range | Action | Timeline |
|------|-------------|--------|----------|
| **Tier 1** | 30-40 | Immediate co-sell engagement | Start within 2 weeks |
| **Tier 2** | 20-29 | Enablement first, then co-sell | Start within 60 days |
| **Tier 3** | 10-19 | Future candidate; monitor readiness | Revisit quarterly |

---

## First 3 Deals Pipeline Plan

### 30-Day Pipeline Creation Sprint

| Week | Activity | Owner | Output |
|------|----------|-------|--------|
| 1 | Identify 5-10 target accounts (NAS 10TB+, analytics need) | AWS account team + Partner | Target account list |
| 1 | Align with AWS account managers on target accounts | Partner SA + Account Manager | Joint account plan |
| 2 | Partner account mapping (which partner covers which account) | Partner SA | Account-partner mapping |
| 2 | Joint discovery workshops (2-3 accounts) | Partner + AWS SA | Discovery notes |
| 3 | Qualify opportunities (use Qualification Checklist) | Partner sales + AWS | Qualified pipeline |
| 3 | Develop PoC proposals for top 3 | Partner SA + delivery | PoC SOWs |
| 4 | Customer decision meetings | Partner + AWS | 3 signed PoC engagements |

### Opportunity Stage Progression

| Stage | Definition | Expected Next Action | Typical Duration |
|-------|-----------|---------------------|-----------------|
| 0. Identified | Account meets target criteria | Schedule discovery call | — |
| 1. Discovery | Pain confirmed, stakeholders engaged | Present solution overview | 1-2 weeks |
| 2. Qualified | Budget, authority, need, timeline confirmed | Propose PoC | 1 week |
| 3. PoC Proposed | SOW presented, pricing agreed | Customer signs SOW | 1-2 weeks |
| 4. PoC Active | PoC in execution | Deliver results | 2-4 weeks |
| 5. Production Proposed | PoC success, production SOW presented | Customer approves | 2-4 weeks |
| 6. Won | Production deployment contracted | Begin delivery | — |

---

## Partner Enablement Kit

| Audience | Materials | Purpose |
|----------|-----------|---------|
| **Sales / Account Manager** | 1-page pitch, objection handling, pricing guide, target account criteria | Identify and qualify opportunities |
| **Pre-sales / SA** | Technical deep dive deck, demo script, architecture diagrams, compatibility matrix | Technical validation and customer workshops |
| **Delivery / Consultant** | PoC SOW template, deployment checklist, runbooks, benchmark methodology | Execute PoC and production deployments |
| **Managed Services** | Operations runbook, monitoring setup guide, monthly report template, escalation matrix | Ongoing operations |
| **Executive / Practice Lead** | Revenue model, Path to Market, case study template, QBR template | Business planning and partner management |

### Enablement Session Plan

| Session | Duration | Audience | Content |
|---------|----------|----------|---------|
| 1. Overview & positioning | 1 hour | All | Business value, competitive positioning, anti-patterns |
| 2. Technical deep dive | 2 hours | SA / delivery | Architecture, compatibility matrix, security model |
| 3. Hands-on lab | 4 hours | SA / delivery | Deploy FSx + S3 AP + Athena/Glue end-to-end |
| 4. Sales play workshop | 1 hour | Sales | Discovery questions, objection handling, pricing |
| 5. First deal planning | 1 hour | Sales + SA | Target accounts, pipeline sprint kickoff |

---

## Industry-Specific GTM Messages

| Industry | Headline | Pain Point | Value Proposition | Call to Action |
|----------|----------|-----------|-------------------|---------------|
| **Manufacturing** | "AI-enable your engineering files without migration" | Design files, inspection records, maintenance manuals trapped on NAS | Query and search existing files with Athena/Bedrock — zero data copy | "2-week PoC: AI search on your maintenance manuals" |
| **Healthcare** | "Safely unlock research data for AI — without moving PHI" | Research documents on file shares, inaccessible to analytics/AI | De-identified data accessible via governed S3 AP + Bedrock RAG | "Secure RAG PoC on de-identified research documents" |
| **Financial Services** | "Governed search across compliance documents" | Regulations, audit trails, contracts scattered across file shares | Controlled access via dual-layer auth + full audit trail | "Compliance document search with complete audit trail" |
| **Media & Entertainment** | "Find and analyze your media assets with AI" | Past productions, scripts, metadata buried in file storage | AI-powered asset discovery without migrating TB of media files | "Asset analytics PoC: search your production archive" |
| **Enterprise IT** | "Turn your runbooks into an AI knowledge base" | Incident reports, runbooks, architecture docs on shared drives | RAG-powered knowledge search for faster incident resolution | "IT knowledge base PoC: reduce MTTR with AI search" |

---

## Joint Discovery Workshop

### Purpose

Validate partner fit, identify target accounts, and define the first joint offer — in a single 120-minute session with a Tier 1 partner candidate.

### Tier 1 Partner Minimum Criteria

A partner must meet ALL of the following to qualify for a Joint Discovery Workshop:

- [ ] Has existing FSx / NetApp / NAS customer base
- [ ] Has Data/AI or managed service capability (at least one)
- [ ] Business or technical leader can attend the workshop
- [ ] Can identify at least 1 customer candidate within 30 days

### Workshop Agenda (120 minutes)

| Time | Topic | Owner | Output |
|------|-------|-------|--------|
| 0-10 min | Introductions, objectives | AWS Partner SA | Alignment on goals |
| 10-30 min | FSx for ONTAP S3 AP overview + demo | AWS SA | Partner understands the technology |
| 30-50 min | Partner capability review | Partner | Understand partner strengths |
| 50-70 min | Target account brainstorm | Joint | 3-5 candidate accounts identified |
| 70-90 min | Deal hypothesis development | Joint | 1-3 deal hypotheses drafted |
| 90-110 min | First offer package design | Joint | Agreed first offer (Assessment/PoC) |
| 110-120 min | Next steps and owners | Joint | Action items with dates |

### Pre-Workshop Preparation

| Participant | Preparation |
|-------------|-------------|
| AWS Partner SA | Partner background research, 1-page pitch ready, demo environment |
| AWS Account Manager | Target account list (NAS 10TB+, analytics need) |
| Partner Business Lead | Customer list with NAS/ONTAP footprint, revenue goals |
| Partner Technical Lead | Review compatibility matrix, anti-patterns |

### Workshop Output Template

```yaml
workshop_date: "YYYY-MM-DD"
partner_name: "<partner>"
participants:
  - name: "<name>"
    role: "<role>"
    org: "AWS | Partner"

partner_fit_score: X/40  # from Prioritization Matrix
tier: "Tier 1 | Tier 2 | Tier 3"

target_accounts:
  - account: "<customer name>"
    industry: "<industry>"
    nas_footprint: "<estimated TB>"
    analytics_need: "<description>"
    partner_relationship: "<existing | new>"

deal_hypotheses:
  - hypothesis: "Manufacturing / NAS inspection data analytics / SIer-led"
    first_offer: "Assessment + Analytics PoC"
    estimated_value: "$25K"
    timeline: "60 days"
    validated: true/false
    
  - hypothesis: "Enterprise IT / Runbook RAG / MSP-led"
    first_offer: "Managed RAG package"
    estimated_value: "$15K setup + $5K/month"
    timeline: "45 days"
    validated: true/false

first_offer_package:
  type: "Assessment | PoC | Managed Package"
  scope: "<description>"
  duration: "<weeks>"
  price_range: "$X-Y"

required_enablement:
  - "<session needed>"

next_steps:
  - action: "<action>"
    owner: "<who>"
    due: "YYYY-MM-DD"
```

### Partner Readiness Certification

After enablement, a partner is certified to co-sell when they can:

- [ ] Deliver the 15-minute pitch without AWS support
- [ ] Explain top 3 anti-patterns and why they matter
- [ ] Create a PoC SOW from the template
- [ ] Answer Security FAQ questions (Block Public Access, dual-layer auth, VPC-origin)
- [ ] Conduct a Discovery call using the standard questions
- [ ] Define a joint next step with an AWS account team

### Co-sell RACI

| Activity | Partner | AWS SA | AWS Account Mgr | NetApp | Customer |
|----------|:-------:|:------:|:----------------:|:------:|:--------:|
| Account selection | C | C | **R** | I | — |
| Discovery call | **R** | C | I | — | **A** |
| Technical validation | **R** | **R** | I | C | C |
| PoC delivery | **R** | C | I | C | **A** |
| Security review | C | **R** | I | — | **A** |
| Production deployment | **R** | C | I | C | **A** |
| Managed operations | **R** | I | I | C | **A** |
| Customer success review | C | C | **R** | I | **A** |

R = Responsible, A = Accountable, C = Consulted, I = Informed

### Opportunity Ownership

For each active deal, assign explicit owners:

| Role | Responsibility |
|------|---------------|
| **Opportunity Owner** | Drives deal progression; owns CRM entry; accountable for stage advancement |
| **Technical Owner** | Owns architecture decisions, PoC execution, security validation |
| **Partner Sales Owner** | Owns customer relationship, commercial negotiation, SOW |
| **AWS Account Owner** | Owns AWS relationship, internal alignment, co-sell support |
| **Next Meeting Owner** | Owns scheduling and agenda for the next customer interaction |

---

## First Offer: FSx S3 AP Analytics Readiness Assessment

**Duration**: 2–3 weeks  
**Target**: Customers with existing NAS/ONTAP data who want to explore analytics or AI without data migration

**Deliverables:**
- Dataset discovery (file types, sizes, access patterns)
- Engine fit assessment (Athena, Databricks, EMR, DuckDB Lambda, Snowflake)
- Governance impact summary (IAM, file system permissions, audit requirements)
- Read-only validation (working query on customer data)
- Negative test evidence (unauthorized access denied)
- Architecture recommendation (Good / Better / Best tier)

**Pricing**: $15K–25K (assessment + PoC)

---

## Marketplace Offer Boundary

This validation package ([fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations)) can inform a partner-delivered assessment, but it is **not itself a Marketplace offer**.

Potential packaged offers for AWS Marketplace or CPPO:
- FSx for ONTAP S3 AP Analytics Assessment (partner-delivered service)
- Lakehouse Engine Fit Workshop (1-day engagement)
- Governance and Evidence Package (for regulated industries)

To create a Marketplace listing, partners must separately package the service with defined scope, pricing, and delivery methodology.

---

## References

- [Accessing your data via Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)
- [Access point compatibility](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)
- [Using access points with AWS services](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html)
- [Configuring network access for Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
- [Amazon FSx for NetApp ONTAP performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)

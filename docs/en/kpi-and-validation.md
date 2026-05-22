# KPI and PoC Validation Guide

## Overview

This document defines measurable success criteria for FSx for ONTAP Lakehouse integration PoCs. Without clear KPIs, it is impossible to evaluate whether a PoC succeeded or failed. Each metric includes a measurement method and target range.

## Core KPIs

### 1. Query Latency

| Metric | Definition | Measurement Method | Target (Good Tier) | Target (Best Tier) |
|--------|-----------|-------------------|-------------------|-------------------|
| Cold query latency | Time from query submission to first result (no cache) | Athena/Databricks query execution time | < 30s for 1 GB scan | < 10s for 1 GB scan |
| Warm query latency | Time with data in FSx NVMe/memory cache | Repeated query execution time | < 10s for 1 GB scan | < 5s for 1 GB scan |
| Metadata query latency | Time for schema/partition discovery | Glue Catalog API response time | < 5s | < 2s |

**How to measure**:
```sql
-- Athena: Check query execution time in console or via API
SELECT query_execution_id, 
       total_execution_time_in_millis,
       data_scanned_in_bytes
FROM information_schema.__query_log__
WHERE query LIKE '%your_table%'
ORDER BY submission_date_time DESC;
```

### 2. Throughput

| Metric | Definition | Measurement Method | Target |
|--------|-----------|-------------------|--------|
| Read throughput | MB/s sustained during table scan | CloudWatch `DataReadBytes` / query duration | ≥ 80% of FSx provisioned throughput |
| Write throughput | MB/s during ETL write-back | CloudWatch `DataWriteBytes` / write duration | ≥ 50% of FSx provisioned throughput |
| Concurrent query throughput | Aggregate throughput under concurrent load | Multiple simultaneous queries | Linear scaling up to provisioned limit |

**Note**: S3 API throughput via access points depends on FSx file system provisioned throughput capacity. This is NOT equivalent to native S3 throughput. ([source](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html))

### 3. Cost per TB Scanned

| Metric | Definition | Measurement Method | Target |
|--------|-----------|-------------------|--------|
| Athena cost/TB | Athena query cost per TB scanned | $5/TB (Athena pricing) + FSx throughput cost | < $10/TB total |
| Storage cost/TB | Monthly storage cost per TB | FSx SSD + capacity pool pricing | Compare vs. S3 Standard + ETL pipeline cost |
| Total cost of ownership | Storage + compute + data transfer | Monthly bill analysis | < current NAS + S3 copy pipeline cost |

**Cost comparison framework**:
```
Current state cost:
  NAS storage: $X/TB/month
  + S3 copy storage: $Y/TB/month  
  + ETL pipeline compute: $Z/month
  + Data transfer: $W/month
  = Total: $(X+Y+Z+W)/month

FSx S3 AP state cost:
  FSx storage: $A/TB/month
  + Analytics compute: $B/month
  + No S3 copy: $0
  + No ETL pipeline: $0
  = Total: $(A+B)/month

Savings = Current - FSx S3 AP
```

### 4. Data Freshness

| Metric | Definition | Measurement Method | Target |
|--------|-----------|-------------------|--------|
| Write-to-query latency | Time from NFS/SMB write to S3 AP query visibility | Write file via NFS, immediately query via S3 AP | Near-zero (same volume, same data) |
| Catalog refresh latency | Time from file creation to Glue Catalog awareness | Glue Crawler run time or event-driven update | < 5 minutes (crawler) or < 1 minute (event) |

**Key advantage**: Since S3 Access Points read directly from the FSx volume, data written via NFS/SMB is immediately visible via S3 API. No sync delay.

### 5. Data Copies Avoided

| Metric | Definition | Measurement Method | Target |
|--------|-----------|-------------------|--------|
| Copy count reduction | Number of redundant data copies eliminated | Inventory of current data copies vs. new architecture | ≥ 50% reduction |
| Storage savings | TB of duplicate storage eliminated | Sum of eliminated copy sizes | Quantify in $/month |
| Pipeline elimination | Number of sync/copy pipelines removed | Count of ETL jobs no longer needed | ≥ 1 pipeline eliminated |

### 6. Recovery Time Objective (RTO) / Recovery Point Objective (RPO)

| Metric | Definition | Measurement Method | Target |
|--------|-----------|-------------------|--------|
| Snapshot RTO | Time to restore volume from snapshot | Timed snapshot restore test | < 5 minutes |
| Snapshot RPO | Maximum data loss window | Snapshot schedule frequency | ≤ 1 hour (hourly snapshots) |
| SnapMirror RTO | Time to failover to DR region | Timed failover test | < 15 minutes |
| SnapMirror RPO | Replication lag | SnapMirror lag metric | < 15 minutes (async) or 0 (sync) |

### 7. Access Policy Review Time

| Metric | Definition | Measurement Method | Target |
|--------|-----------|-------------------|--------|
| Policy audit time | Time to review and validate all access policies | Manual review of IAM + AP + file system permissions | < 1 hour per access point |
| Permission change time | Time to grant/revoke access | Time from request to effective change | < 30 minutes |
| Compliance report generation | Time to produce access audit report | CloudTrail query + report generation | < 1 hour |

## PoC Success Criteria Template

### Phase 1: Connectivity Validation (Week 1)

| Criterion | Pass Condition | Test Method |
|-----------|---------------|-------------|
| S3 AP creation | Access point in AVAILABLE state | `aws fsx describe-s3-access-points` |
| Basic read | GetObject succeeds via AP alias | `aws s3 cp s3://AP-ALIAS/test.txt .` |
| Basic write | PutObject succeeds via AP alias | `aws s3 cp test.txt s3://AP-ALIAS/` |
| List objects | ListObjectsV2 returns expected files | `aws s3 ls s3://AP-ALIAS/` |
| IAM authorization | Unauthorized role is denied | Test with role lacking AP permissions |
| File system authorization | Read-only user cannot write | Test PutObject with read-only AP user |

### Phase 2: Analytics Integration (Week 2)

| Criterion | Pass Condition | Test Method |
|-----------|---------------|-------------|
| Glue Crawler | Table registered in Glue Catalog | Run crawler, verify table in catalog |
| Athena query | SQL query returns correct results | Run SELECT on registered table |
| Query performance | Meets latency target for dataset size | Measure query execution time |
| Data freshness | New file visible in query within SLA | Write via NFS, query via Athena |

### Phase 3: Production Readiness (Week 3-4)

| Criterion | Pass Condition | Test Method |
|-----------|---------------|-------------|
| Concurrent access | N concurrent queries without degradation | Load test with parallel queries |
| Security validation | Unauthorized access denied at both layers | Penetration test IAM + file system |
| Audit completeness | All access events logged in CloudTrail | Review CloudTrail for test period |
| Recovery test | Snapshot restore within RTO target | Timed restore exercise |
| Cost validation | Total cost within budget | Compare actual vs. projected cost |

## Measurement Tools

| Tool | What it Measures | Setup |
|------|-----------------|-------|
| CloudWatch (FSx metrics) | Throughput, IOPS, latency, storage utilization | Automatic with FSx |
| CloudTrail | API calls, data access events | Enable S3 data events on AP |
| Athena query history | Query latency, data scanned, cost | Built into Athena |
| Databricks query profile | Query execution plan, duration | Built into Databricks |
| AWS Cost Explorer | Monthly cost breakdown | Automatic |

---

## Business KPI Mapping

Technical KPIs must be translated into business/operational metrics that executives and business stakeholders can evaluate.

| Technical KPI | Business KPI | Business Question Answered |
|--------------|-------------|---------------------------|
| Query latency (seconds) | Time from analysis request to decision | "How fast can we act on data?" |
| Data freshness (write-to-query) | Operational data reflection delay | "Are we making decisions on current data?" |
| Data copies avoided (count) | Storage cost reduction ($/month) + operational headcount savings | "How much are we saving by not maintaining copy pipelines?" |
| Throughput (MB/s) | Analyst productivity (queries/day) | "Can our team run all needed analyses without waiting?" |
| Cost per TB scanned | Analytics cost per business insight | "What does each report/dashboard cost us?" |
| RTO / RPO | Business continuity SLA compliance | "Can we meet our regulatory recovery commitments?" |
| Access policy review time | Audit response time (hours) | "How quickly can we respond to a compliance audit?" |
| RAG response accuracy | Knowledge worker time savings | "How much faster can employees find information?" |

### Executive Dashboard Metrics

For CxO reporting, distill to 4-5 headline metrics:

1. **Cost avoidance**: $X/month saved by eliminating data copy pipelines
2. **Time-to-insight**: Reduced from Y days to Z hours
3. **Compliance posture**: 100% of data access auditable via CloudTrail
4. **AI readiness**: N documents accessible for AI/RAG without migration
5. **Operational risk**: DR tested, RTO < 15 min, RPO < 1 hour

---

## PoC Guardrails

Define clear boundaries for what is allowed during PoC to enable safe experimentation.

### What IS Allowed in PoC

| Activity | Condition |
|----------|-----------|
| Read-only analytics (Athena, Glue Crawler) | Any data classification |
| Glue ETL read + write-back (Parquet) | Internal/Public data only |
| Bedrock RAG ingestion | De-identified documents only |
| Performance benchmarking | Synthetic or public datasets |
| Security testing (IAM deny verification) | Controlled test principals |
| Snapshot restore testing | Non-production volume |

### What is NOT Allowed in PoC

| Activity | Reason |
|----------|--------|
| Delta Lake write / MERGE / compaction | Not Supported — will produce inconsistent state |
| Real PHI/PII in non-production environments | Compliance violation risk |
| Internet-origin AP for Confidential/Regulated data | Security posture insufficient for regulated data |
| Modifying production AP policies for testing | Risk of production access disruption |
| Exceeding defined cost ceiling | Budget control |
| Sharing PoC access credentials | Audit trail integrity |

### PoC Cost Ceiling

Define maximum acceptable PoC cost before starting:

| Component | Estimated Cost (2-week PoC) |
|-----------|---------------------------|
| FSx for ONTAP (512 MB/s, 1 TB SSD) | ~$800 |
| Athena queries (10 TB scanned) | ~$50 |
| Glue Crawler + ETL | ~$20 |
| CloudTrail (S3 data events) | ~$10 |
| **Total ceiling** | **< $1,000** |

### PoC Exit Criteria

| Outcome | Action |
|---------|--------|
| All Phase 1-2 criteria pass | Proceed to Phase 3 (production readiness) |
| Performance targets not met | Evaluate FSx throughput sizing; re-test with higher provisioning |
| Security verification fails | Investigate and remediate before proceeding |
| Cost exceeds ceiling | Stop and reassess architecture |
| Fundamental limitation discovered | Document and evaluate alternative approaches |

---

## RAG Use Case Catalog

FSx S3 AP + Amazon Bedrock Knowledge Bases enables RAG on existing enterprise file data without migration.

| Industry | Use Case | Source Documents | Business Value |
|----------|----------|-----------------|----------------|
| **Manufacturing** | Maintenance manual / work standard search | PDF manuals, work instructions, inspection records | Reduce equipment downtime; faster technician onboarding |
| **Healthcare** | Research document / de-identified case search | Research papers, de-identified clinical notes, protocols | Accelerate research; improve evidence-based decisions |
| **Financial Services** | Regulation / audit trail / contract search | Compliance documents, audit reports, contracts | Faster regulatory response; reduce compliance risk |
| **Media** | Past asset / metadata / script search | Production notes, scripts, asset metadata files | Faster content discovery; reduce re-creation of existing assets |
| **Enterprise IT** | Incident report / runbook search | Incident reports, runbooks, architecture documents | Faster incident resolution; knowledge preservation |

### RAG Implementation Pattern

```
Existing NFS/SMB workflow          Analytics / AI workflow
        │                                    │
        ▼                                    ▼
┌──────────────────┐              ┌─────────────────────┐
│ Users write docs │              │ Bedrock Knowledge   │
│ via NFS/SMB      │              │ Base ingests via     │
│ (unchanged)      │              │ S3 Access Point      │
└────────┬─────────┘              └──────────┬──────────┘
         │                                    │
         ▼                                    ▼
┌──────────────────────────────────────────────────────┐
│              FSx for ONTAP Volume                     │
│         (single source of truth)                      │
└──────────────────────────────────────────────────────┘
```

**Key advantage**: Documents written by users via NFS/SMB are immediately available for RAG ingestion via S3 AP. No copy, no sync, no delay.

---

## Future: Agentic AI Integration

As AI evolves from RAG to autonomous agents, FSx S3 AP positions enterprise file data as a governed data access layer for AI agents.

### Potential Integration Points

| AI Capability | FSx S3 AP Role | Status |
|--------------|---------------|--------|
| **Bedrock Knowledge Bases (RAG)** | Document data source for retrieval | ✅ Available ([tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)) |
| **Bedrock Agents (tool use)** | Agent retrieves documents via S3 API tool | Architecturally feasible (agent → S3 GetObject → AP → FSx) |
| **MCP-compatible tools** | S3-based document retrieval tool for any MCP client | Architecturally feasible (MCP tool wraps S3 GetObject) |
| **Athena query tool** | Agent runs SQL on file data via Athena + Glue Catalog | Architecturally feasible (agent → Athena → Glue → AP → FSx) |
| **Multi-modal AI** | Image/video/audio analysis on media files | Architecturally feasible (agent → GetObject → media file → model) |

### Governance for Agentic AI

When AI agents access enterprise data autonomously, governance becomes critical:

- **Read-only access points**: Agents should NEVER have write access to source data
- **Scoped IAM roles**: Per-agent IAM roles with minimum necessary permissions
- **Audit trail**: All agent data access logged via CloudTrail S3 data events
- **Human-in-the-loop**: Agent actions that affect business decisions require human approval
- **Rate limiting**: Prevent runaway agents from overwhelming FSx throughput
- **Data classification awareness**: Agents must respect data classification boundaries

### Strategic Positioning

```
Today (2025):          Near-term (2026):           Future:
RAG on documents  →    Agents query structured  →  Autonomous agents
(Bedrock KB)           + unstructured data          with governed access
                       (Athena + Bedrock)           to enterprise files
```

FSx S3 AP provides a **governed, auditable, read-only data access layer** that is well-suited for AI agent architectures where data security and auditability are non-negotiable.

---

## References

- [Amazon FSx for NetApp ONTAP performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)
- [Accessing your data via Amazon S3 access points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)
- [Monitoring FSx for ONTAP API Calls with AWS CloudTrail](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/logging-using-cloudtrail-win.html)
- [Build a RAG application using Amazon Bedrock Knowledge Bases](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)
- [Using access points with AWS services](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html)

# PoC Plan

🌐 **English** | [日本語](../ja/05_poc_plan.md)

---

> This plan aligns with `.kiro/specs/manufacturing-data-platform-poc/tasks.md` (5-phase task structure).
> Phase 1–3 from tasks.md (Architecture Design Completion) must be completed before PoC execution begins.

## TSK-000: PoC Objectives

Validate the manufacturing data platform architecture with minimum viable components on AWS.

**Success Criteria:**
1. Edge events flow through Kafka to both ClickHouse and Databricks Delta tables
2. Delta tables are governed by Unity Catalog
3. Large payloads are stored on FSx for ONTAP and referenced from Delta tables
4. ClickHouse provides sub-second queries on streaming data
5. Failure/replay scenarios are tested and documented
6. ClickHouse cold tier to ONTAP S3 is validated (stretch goal)

---

## Phase 1: Infrastructure Setup

### TSK-001: AWS Infrastructure Provisioning

Deploy base infrastructure in a single AWS region (ap-northeast-1 or us-east-1).

**Components:**
- VPC with private subnets (4 subnets across 2 AZs)
- Security groups for inter-component communication
- VPC endpoints for S3, STS
- S3 bucket for Delta Lake storage
- S3 bucket for Structured Streaming checkpoints

**Acceptance Criteria:**
- [ ] VPC deployed with correct CIDR ranges
- [ ] Security groups allow required inter-component traffic
- [ ] S3 buckets created with encryption and no public access
- [ ] VPC endpoints verified working

### TSK-002: Amazon MSK Cluster Deployment

Deploy managed Kafka cluster.

**Configuration:**
- MSK Serverless or Provisioned (m5.large × 3 for PoC)
- SASL/SCRAM or IAM authentication
- TLS encryption in transit
- Topics created per DES-003

**Acceptance Criteria:**
- [ ] MSK cluster running and healthy
- [ ] Authentication configured and tested
- [ ] Topics created with correct partition counts
- [ ] Producer/consumer connectivity verified from private subnet

### TSK-003: ClickHouse Deployment

Deploy ClickHouse for real-time analytics.

**Options (choose one):**
- ClickHouse Cloud (fastest setup)
- ClickHouse BYOC (data in customer VPC)
- Self-managed on EC2 (lowest cost)

**Acceptance Criteria:**
- [ ] ClickHouse cluster running
- [ ] Accessible from VPC private subnet
- [ ] Authentication configured
- [ ] Test query executes successfully

### TSK-004: FSx for ONTAP Deployment

Deploy FSx for ONTAP file system.

**Configuration:**
- Single-AZ (PoC cost optimization)
- SSD storage: 1 TB
- Throughput capacity: 128 MB/s (minimum)
- SVM with NFS and ONTAP S3 enabled
- Volumes per DES-007

**Acceptance Criteria:**
- [ ] File system created and accessible
- [ ] NFS exports configured and mountable
- [ ] ONTAP S3 endpoint accessible
- [ ] Snapshot policy configured
- [ ] Test file write/read via NFS succeeds
- [ ] Test object write/read via ONTAP S3 succeeds

### TSK-005: Databricks Workspace Setup

Deploy Databricks workspace with Unity Catalog.

**Configuration:**
- Databricks workspace in same region
- Unity Catalog metastore
- External location pointing to S3 bucket (or use managed storage)
- Catalog: `manufacturing_catalog`
- Schema: `factory_data`

**Acceptance Criteria:**
- [ ] Workspace accessible
- [ ] Unity Catalog metastore attached
- [ ] Catalog and schema created
- [ ] Cluster with Unity Catalog access mode launches
- [ ] VPC connectivity to MSK verified

---

## Phase 2: Data Pipeline Development

### TSK-006: Edge Event Simulator

Build a simulated factory edge event generator.

**Implementation:**
- Python application generating synthetic sensor data and quality events
- Publishes to Kafka topics defined in DES-003
- Simulates multiple devices, lines, and event types
- Generates payload metadata (with references to synthetic files)
- Configurable event rate (10-1000 events/second)

**Acceptance Criteria:**
- [ ] Simulator produces valid Avro/JSON messages
- [ ] Messages appear in Kafka topics
- [ ] Event rate is configurable
- [ ] Multiple device/line simulation works
- [ ] Payload references point to valid synthetic paths

### TSK-007: Payload Generator

Generate synthetic payload files on FSx for ONTAP.

**Implementation:**
- Python script generating synthetic images (PNG with metadata)
- Synthetic documents (PDF/text with quality data)
- Files stored on FSx for ONTAP via NFS mount
- File paths match payload_uri in Kafka messages

**Acceptance Criteria:**
- [ ] Synthetic files created on FSx for ONTAP
- [ ] Files accessible via NFS
- [ ] Files accessible via ONTAP S3 API
- [ ] File URIs match payload_uri in corresponding Kafka messages

### TSK-008: Kafka to ClickHouse Ingestion

Configure ClickHouse to consume from Kafka.

**Implementation:**
- Kafka Engine tables in ClickHouse
- Materialized views for data transformation
- MergeTree destination tables (DES-005)

**Acceptance Criteria:**
- [ ] ClickHouse ingests from Kafka topics in real-time
- [ ] Data appears in MergeTree tables within 5 seconds
- [ ] Schema matches DES-005
- [ ] Queries return results in < 1 second

### TSK-009: Kafka to Databricks Streaming Pipeline

Implement Structured Streaming pipeline.

**Implementation:**
- Databricks notebook or DLT pipeline
- Reads from MSK topics
- Writes to Unity Catalog managed Delta tables (DES-006)
- Checkpointing to S3
- Schema evolution handling

**Acceptance Criteria:**
- [ ] Streaming pipeline starts and processes messages
- [ ] Delta tables populated with correct data
- [ ] Tables visible in Unity Catalog with governance metadata
- [ ] Exactly-once semantics verified (no duplicates after restart)
- [ ] Checkpoint location verified on S3

---

## Phase 3: Validation and Testing

### TSK-010: End-to-End Data Flow Verification

Verify complete data path from simulator to governed analytics.

**Tests:**
1. Generate 10,000 events → verify all appear in ClickHouse AND Delta tables
2. Verify payload_uri in Delta tables points to actual files on FSx for ONTAP
3. Verify Unity Catalog shows correct table metadata and statistics
4. Verify ClickHouse dashboard queries return correct aggregations

**Acceptance Criteria:**
- [ ] Event counts match across all systems (within pipeline latency)
- [ ] Payload URIs are resolvable
- [ ] Unity Catalog metadata is accurate
- [ ] No data loss detected

### TSK-011: Failure Recovery Test

Test pipeline resilience.

**Scenarios:**
1. Stop Databricks streaming job → restart → verify no data loss or duplication
2. Stop ClickHouse consumer → resume → verify catch-up from Kafka
3. Simulate Kafka topic unavailability → verify error handling
4. Reset consumer offset → verify replay capability

**Acceptance Criteria:**
- [ ] Databricks pipeline resumes from checkpoint without data loss
- [ ] ClickHouse catches up after consumer restart
- [ ] No duplicate records after recovery
- [ ] Replay from specific offset produces correct results

### TSK-012: Metadata-to-Payload Lookup Test

Verify payload reference integrity.

**Tests:**
1. Query Delta table for events with payload_uri
2. For each payload_uri, verify file exists on FSx for ONTAP
3. Verify file checksum matches metadata
4. Verify file is accessible via both NFS and ONTAP S3

**Acceptance Criteria:**
- [ ] 100% of payload_uri references resolve to actual files
- [ ] Checksums match between metadata and actual files
- [ ] Files accessible via multiple protocols

### TSK-013: ClickHouse Cold Tier to ONTAP S3 (Stretch Goal)

Validate ClickHouse tiered storage with ONTAP S3 backend.

**Tests:**
1. Configure ClickHouse S3 storage policy pointing to ONTAP S3 endpoint
2. Insert sufficient data to trigger TTL-based tier migration
3. Verify cold data queries still work (with expected latency)
4. Verify data on ONTAP S3 is protected by Snapshot

**Acceptance Criteria:**
- [ ] ClickHouse recognizes ONTAP S3 as valid S3 storage
- [ ] Data migrates to cold tier based on TTL policy
- [ ] Cold tier queries return correct results
- [ ] ONTAP Snapshot covers cold tier data

---

## Phase 4: Documentation and Assessment

### TSK-014: Performance Observations

Document observed performance characteristics.

**Metrics to capture:**
- Kafka → ClickHouse ingestion latency
- Kafka → Delta Lake ingestion latency
- ClickHouse query latency (P50, P95, P99)
- Structured Streaming throughput (records/sec)
- FSx for ONTAP file operation latency (NFS, ONTAP S3)

**Acceptance Criteria:**
- [ ] Latency measurements documented
- [ ] Throughput measurements documented
- [ ] Bottlenecks identified (if any)

### TSK-015: Final Feasibility Assessment

Produce final architecture feasibility judgment.

**Deliverables:**
- Feasibility rating with justification
- Required modifications for production
- Unresolved blockers
- Vendor confirmation requirements
- PoC success criteria evaluation

**Acceptance Criteria:**
- [ ] All PoC success criteria evaluated
- [ ] Feasibility rating assigned
- [ ] Production gap analysis completed
- [ ] Recommendations documented

---

## PoC Timeline (Estimated)

| Phase | Duration | Dependencies |
|-------|----------|-------------|
| Phase 1: Infrastructure | 3-5 days | AWS account, Databricks workspace |
| Phase 2: Pipelines | 5-7 days | Phase 1 complete |
| Phase 3: Validation | 3-5 days | Phase 2 complete |
| Phase 4: Documentation | 2-3 days | Phase 3 complete |
| **Total** | **13-20 days** | |

## PoC Cost Estimate (Rough Order of Magnitude)

| Component | Monthly Estimate (USD) | Notes |
|-----------|----------------------|-------|
| Amazon MSK (Serverless) | $50-150 | Low throughput PoC |
| ClickHouse Cloud | $100-300 | Development tier |
| FSx for ONTAP (Single-AZ, 1TB SSD) | $200-400 | Minimum config |
| Databricks | $200-500 | Streaming jobs + interactive |
| S3 | $10-30 | Delta tables + checkpoints |
| VPC/Network | $50-100 | NAT, endpoints |
| **Total (monthly)** | **$610-1,480** | |

*Note: Costs are estimates for a PoC workload. Production costs would be significantly higher.*

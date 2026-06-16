# Decision Matrix

🌐 **English** | [日本語](../ja/06_decision_matrix.md)

---

> Each decision below is documented as a formal Architecture Decision Record (ADR).
> See [docs/adr/README.md](../adr/README.md) for the full ADR index.

## DEC-001: Delta Lake Storage Target

> 📄 Detailed in [ADR-004](../adr/ADR-004.md) — Avoid direct dependency on S3 Access Points

| Option | Unity Catalog Compatible | Performance | Cost | Operational Complexity | Verdict |
|--------|------------------------|-------------|------|----------------------|---------|
| Native Amazon S3 | ✅ Yes | High | Low | Low | **Selected** |
| FSx for ONTAP (ONTAP S3) | ❌ No | Medium | Medium | Medium | Rejected |
| FSx for ONTAP (S3 Access Points) | ❌ No (not supported by UC) | Medium | Medium | Medium | Rejected |
| MinIO / S3-compatible | ❌ No | Variable | Variable | High | Rejected |

**Decision:** Native Amazon S3 is the only supported storage for Unity Catalog external locations on AWS. This is a confirmed product constraint, not a design choice.

**Source:** REF-020, REF-021, REF-022

---

## DEC-002: Kafka to Databricks Ingestion Method

> 📄 Detailed in [ADR-001](../adr/ADR-001.md) — Use Kafka as the factory event backbone

| Option | Exactly-Once | Managed | Schema Evolution | Unity Catalog | Maturity | Verdict |
|--------|-------------|---------|-----------------|---------------|----------|---------|
| Structured Streaming (direct) | ✅ | Partial (job mgmt) | ✅ | ✅ | High | **Selected (primary)** |
| Confluent Tableflow | ✅ | ✅ | ✅ | ✅ | Medium (GA Oct 2025) | Alternative |
| Confluent Delta Lake Sink Connector | ✅ | ✅ | ✅ | Limited | High | Alternative |
| Delta Live Tables (DLT) | ✅ | ✅ | ✅ | ✅ | High | Alternative |
| Custom batch consumer | ❌ (at-least-once) | ❌ | Manual | ✅ | Low | Rejected |

**Decision:** Databricks Structured Streaming is the primary approach (most control, well-documented, exactly-once). Confluent Tableflow is a viable managed alternative for Confluent Cloud users.

**Source:** REF-001, REF-002, REF-003, REF-004, REF-005

---

## DEC-003: Real-Time Analytics Engine

> 📄 Detailed in [ADR-002](../adr/ADR-002.md) — Use ClickHouse for real-time operational analytics

| Option | Query Latency | Kafka Native | Manufacturing References | AWS Options | Verdict |
|--------|--------------|-------------|------------------------|-------------|---------|
| ClickHouse | Sub-second | ✅ (Kafka Engine) | ✅ Multiple | Cloud, BYOC, Self-managed | **Selected** |
| Amazon OpenSearch | Sub-second | Via connector | Limited | Managed (Serverless) | Alternative |
| Amazon Timestream | Sub-second | Via Lambda/Firehose | Limited | Fully managed | Alternative |
| Databricks SQL (warehouse) | Seconds | Via streaming | N/A (overlaps with lakehouse) | Managed | Not applicable |
| Apache Druid | Sub-second | ✅ | Limited | Self-managed only | Rejected (ops overhead) |

**Decision:** ClickHouse selected for sub-second real-time analytics. Strong manufacturing reference cases (REF-030, REF-032). Native Kafka ingestion. Multiple AWS deployment options.

> **DAIS 2026 update (2026-06-16)**: Databricks announced **Lakehouse//RT** (Beta, Reyden engine) — millisecond real-time analytics directly on UC-governed Delta/Iceberg. Decision is unchanged for the PoC (ClickHouse for Phase A); plan is to trial **both** ClickHouse and Lakehouse//RT in the PoC for comparative knowledge and re-evaluate for Phase B. See [ADR-002 DAIS 2026 Update](../adr/ADR-002.md#dais-2026-update-2026-06-16--dais-2026-アップデート).

**Source:** REF-030, REF-031, REF-032, REF-040, REF-041

---

## DEC-004: ClickHouse Deployment Model (PoC)

| Option | Ops Effort | Cost (PoC) | Data Location | Network | Verdict |
|--------|-----------|------------|---------------|---------|---------|
| ClickHouse Cloud | Zero | Medium | ClickHouse-managed | PrivateLink | **Recommended** |
| ClickHouse BYOC | Low | Medium-High | Customer VPC | Same VPC | Alternative |
| Self-managed (EC2) | High | Low | Customer VPC | Same VPC | Cost-optimized alt |
| Self-managed (EKS) | High | Medium | Customer VPC | Same VPC | Not for PoC |

**Decision:** ClickHouse Cloud recommended for PoC (minimal ops). BYOC or self-managed EC2 if VPC-local data access is required for ONTAP S3 tiering tests.

**Source:** REF-040, REF-041, REF-044, REF-045

---

## DEC-005: FSx for ONTAP vs Native S3 for Payloads

> 📄 Detailed in [ADR-003](../adr/ADR-003.md) — Use FSx for ONTAP as payload storage for large unstructured data
> 📄 Also see [ADR-005](../adr/ADR-005.md) — Use metadata/payload separation for large files

| Criterion | FSx for ONTAP | Native Amazon S3 |
|-----------|--------------|------------------|
| Protocol flexibility | ✅ NFS + SMB + S3 | ❌ S3 only |
| Edge device compatibility | ✅ NFS/SMB for PLC/SCADA | ⚠️ Requires S3 SDK |
| Data protection | ✅ Snapshot, SnapMirror | ⚠️ Versioning only |
| Space-efficient clones | ✅ FlexClone | ❌ Full copy required |
| Multiprotocol concurrent | ✅ Same data via multiple protocols | ❌ S3 only |
| Cost | ⚠️ Higher (provisioned) | ✅ Lower (pay-per-use) |
| Operational complexity | ⚠️ Higher (SVM, volumes) | ✅ Lower (buckets) |
| ClickHouse cold tier | ✅ ONTAP S3 endpoint | ✅ Native S3 |
| Unity Catalog compatibility | ❌ Not for Delta tables | ✅ Full support |

**Decision:** FSx for ONTAP selected for payload storage where multiprotocol access and enterprise data protection provide clear value. Native S3 used for Delta Lake tables (required by Unity Catalog). This is a complementary design, not either/or.

**Source:** REF-050, REF-051, REF-052, REF-053

---

## DEC-006: Kafka Service

| Option | Managed | Cost (PoC) | IAM Auth | Serverless | Verdict |
|--------|---------|-----------|----------|-----------|---------|
| Amazon MSK Provisioned | ✅ | Medium | ✅ | ❌ | **Selected** |
| Amazon MSK Serverless | ✅ | Low | ✅ | ✅ | Alternative |
| Confluent Cloud | ✅ | Medium-High | Different | ✅ | If Tableflow needed |
| Self-managed (EC2) | ❌ | Low | Manual | ❌ | Not for PoC |

**Decision:** Amazon MSK (Provisioned or Serverless) for PoC. Native AWS integration, IAM authentication, VPC deployment. Confluent Cloud if Tableflow is desired.

---

## DEC-007: ClickHouse to Databricks Integration Pattern

| Pattern | Performance | Complexity | Coupling | Verdict |
|---------|-------------|-----------|----------|---------|
| Kafka (shared) → both systems | High | Low | Loose | **Primary (already designed)** |
| Spark connector (batch reads) | Medium | Medium | Medium | Secondary (on-demand) |
| S3 export → Databricks | Medium | Low | Loose | Fallback |
| JDBC direct queries | Low | Low | Tight | Ad-hoc only |

**Decision:** Primary integration is indirect (both consume from Kafka). Direct ClickHouse→Databricks reads via Spark connector are secondary/optional for batch aggregation pulls.

---

## Final Architecture Feasibility Assessment

### Verdict: Feasible with Modifications

| Criterion | Assessment |
|-----------|-----------|
| Technical feasibility | ✅ All components have proven integration paths |
| Unity Catalog compatibility | ✅ Correctly uses native S3 for Delta tables |
| Kafka→Databricks | ✅ Production-proven pattern with exactly-once |
| ClickHouse real-time analytics | ✅ Manufacturing references exist |
| FSx for ONTAP payload storage | ✅ Clear value for multiprotocol edge access |
| S3 Access Points avoidance | ✅ Architecture does not depend on S3 Access Points |
| ClickHouse→ONTAP S3 tiering | ⚠️ Needs PoC validation |
| ClickHouse→Databricks connector | ⚠️ Needs PoC validation |
| Split governance model | ⚠️ Accepted trade-off, needs clear documentation |

### Required Modifications from Original Hypothesis

1. **Delta tables must be on native S3** (not ONTAP S3) — confirmed constraint
2. **ClickHouse→Databricks is secondary path** — primary ingestion remains Kafka→Structured Streaming
3. **FSx for ONTAP role is payload storage** — not a lakehouse storage target
4. **Governance is split** — UC for structured data, ONTAP for unstructured payloads

### Required Vendor Confirmations

1. ClickHouse: S3-compatible tiering to ONTAP S3 endpoint (performance, stability)
2. Databricks: Spark connector version compatibility with current Databricks Runtime
3. AWS: MSK↔Databricks PrivateLink/VPC peering connectivity validation

### Minimum PoC Success Criteria

1. ✅ Events flow from simulator → Kafka → ClickHouse (sub-second queries work)
2. ✅ Events flow from simulator → Kafka → Databricks Delta tables (exactly-once)
3. ✅ Delta tables are governed by Unity Catalog
4. ✅ Payload files exist on FSx for ONTAP and are referenced from Delta tables
5. ✅ Pipeline recovery works after simulated failure
6. ⚠️ ClickHouse cold tier to ONTAP S3 works (stretch goal)

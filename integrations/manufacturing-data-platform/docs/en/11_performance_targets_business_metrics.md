# Performance Targets and Business Metrics

🌐 **English** | [日本語](../ja/11_performance_targets_business_metrics.md)

---

> Addresses P1 items from [design concern checklist](08_design_concern_checklist.md):
> - Storage: P99 latency targets and throughput budget
> - Business outcome and product decision: Business success metrics and Go/No-Go criteria

---

## PERF-001: P99 Latency Targets

### End-to-End Latency Budget

```
Edge Device → Kafka → ClickHouse → Dashboard Query Result

Target: < 5 seconds (end-to-end for real-time path)
```

| Segment | P50 Target | P99 Target | Measurement Point |
|---------|-----------|-----------|-------------------|
| Edge → Kafka (produce + ack) | < 100 ms | < 500 ms | Producer callback timestamp − event timestamp |
| Kafka → ClickHouse (consume + insert) | < 500 ms | < 2 s | ClickHouse row timestamp − Kafka message timestamp |
| ClickHouse query (hot data) | < 100 ms | < 500 ms | query_duration_ms in system.query_log |
| ClickHouse query (with FINAL dedup) | < 300 ms | < 2 s | query_duration_ms with FINAL |
| **Total: event → queryable** | **< 1 s** | **< 5 s** | End-to-end verification test |

### Payload Access Latency

| Segment | P50 Target | P99 Target | Condition |
|---------|-----------|-----------|-----------|
| NFS read (same VPC, hot data) | < 10 ms | < 50 ms | File in SSD tier, NFS v4.1 |
| NFS read (capacity pool tier) | < 100 ms | < 500 ms | File in capacity pool, first access |
| ONTAP S3 GET (same VPC) | < 50 ms | < 200 ms | Object on SSD tier |
| FlexCache hit (Phase B, AWS side) | < 20 ms | < 100 ms | Cached in FlexCache volume |
| FlexCache miss (Phase B, WAN) | < 500 ms | < 3 s | First access, fetch from on-prem origin over VPN/DX |

### Kafka → Databricks Latency (Governed Path)

| Segment | P50 Target | P99 Target | Notes |
|---------|-----------|-----------|-------|
| Kafka → Delta table (Structured Streaming) | < 30 s | < 5 min | Trigger interval: 10 seconds |
| Delta table available for query | < 1 min | < 10 min | Including file compaction |

> Note: The governed path (Databricks) is intentionally slower than the real-time path (ClickHouse). This is by design — freshness vs governance trade-off.

---

## PERF-002: FSx for ONTAP Shared Throughput Budget

### Throughput Capacity: 128 MB/s (PoC)

The 128 MB/s throughput is **shared across all protocols and volumes**. Contention analysis:

| Workload | Protocol | Peak Demand | Duty Cycle | Effective Demand |
|----------|----------|-------------|-----------|-----------------|
| Edge payload upload (images) | NFS | 50 MB/s (5 × 10 MB images/sec) | 30% of time | ~15 MB/s avg |
| Edge payload upload (video) | NFS | 30 MB/s (continuous stream) | 80% of time | ~24 MB/s avg |
| ClickHouse cold tier read | ONTAP S3 | 20 MB/s (cold query burst) | 5% of time | ~1 MB/s avg |
| FlexCache fill (Phase B) | Intercluster | 50 MB/s (batch fill burst) | 10% of time | ~5 MB/s avg |
| Databricks payload access (ML) | NFS/S3 | 80 MB/s (training batch) | Periodic | Burst |
| **Total peak (worst case)** | | **~230 MB/s** | | **~45 MB/s avg** |

### Contention Assessment

| Scenario | Risk | Mitigation |
|----------|------|-----------|
| Normal operations | ✅ Low | Average demand (~45 MB/s) well within 128 MB/s |
| Peak upload + ML training | ⚠️ Medium | Concurrent 50 MB/s upload + 80 MB/s ML read = 130 MB/s > 128 MB/s |
| Peak + FlexCache fill | ⚠️ Medium | Burst scenarios can exceed provisioned throughput |

### Recommendations

1. **PoC**: 128 MB/s is sufficient for typical development/validation workload
2. **If contention observed**: Upgrade to 256 MB/s ($174/month vs $87/month)
3. **Production**: Plan for 512 MB/s minimum with QoS policies per volume
4. **Schedule ML training** outside peak upload hours (if possible in PoC)
5. **Monitor**: CloudWatch `ThroughputUtilization` alarm at 80%

---

## PERF-003: ONTAP S3 Authorization Chain

### ClickHouse → ONTAP S3 Access Path

```
ClickHouse Process
    │
    ↓ (S3 API call: GET/PUT)
ONTAP S3 Endpoint (SVM management LIF, port 443)
    │
    ↓ (S3v4 signature verification)
ONTAP S3 User Authentication
    │ (Access Key + Secret Key → mapped to SVM S3 user)
    ↓
ONTAP S3 Bucket Policy
    │ (Allow/Deny based on user, action, resource)
    ↓
ONTAP Volume Permission
    │ (Volume junction path → file system permission check)
    ↓
Data Access (Read/Write)
```

### Configuration Checklist

| Step | Component | Configuration | Verification |
|------|-----------|-------------|-------------|
| 1 | SVM S3 service | `vserver object-store-server create` | `vserver object-store-server show` |
| 2 | S3 user | `vserver object-store-server user create` with access/secret keys | `vserver object-store-server user show` |
| 3 | S3 bucket | `vserver object-store-server bucket create -vserver svm1 -bucket factory-clickhouse-cold` | `bucket show` |
| 4 | Bucket policy | Allow GetObject, PutObject, DeleteObject, ListBucket for ClickHouse user | `bucket policy show` |
| 5 | Network | Security group allows ClickHouse CIDR → FSx SVM LIF port 443 | SG rule verification |
| 6 | ClickHouse config | S3 disk config with endpoint, access_key, secret_key | ClickHouse system.disks |

### Security Boundaries

| Boundary | Enforcement | Verified By |
|----------|-------------|-------------|
| Network (VPC) | Security group: only ClickHouse IPs can reach ONTAP S3 port | SG audit |
| Authentication | S3v4 signature with access/secret key pair | Connection test |
| Authorization | Bucket policy: only ClickHouse user can R/W cold-tier bucket | Policy review |
| Encryption | TLS in transit (HTTPS endpoint) | Certificate validation |
| Encryption at rest | FSx for ONTAP volume-level encryption (KMS) | FSx configuration |

---

## BIZ-001: Business Success Metrics

### Business Outcome Mapping

| Business Outcome | Metric | PoC Target | Current Baseline (estimated) | Measurement |
|-----------------|--------|-----------|------------------------------|-------------|
| Faster defect detection | Time from quality event to dashboard visibility | < 5 seconds | Hours (batch processing) | SLO-02 measurement |
| Real-time operational awareness | OEE dashboard refresh rate | Real-time (< 5s) | Daily batch reports | Dashboard query interval |
| Accelerated AI/ML development | Payload retrieval time for ML pipeline | < 10 seconds (FlexCache hit) | Manual file transfer (hours) | FlexCache access latency |
| Data consolidation across factories | Cross-factory query capability | Single SQL query across all factories | Separate silos per factory | Unity Catalog cross_factory schema |
| Reduced data duplication cost | Storage footprint ratio (cloud copies / origin) | < 0.1x (FlexCache cache only) | 1x or more (full copies) | FSx cache size / on-prem origin size |

### PoC Technical → Business Metric Mapping

| Technical SLO | Business Metric It Supports | Stakeholder |
|-------------|---------------------------|-------------|
| SLO-02 (Kafka→CH < 5s) | Faster defect detection | Quality Manager |
| SLO-03 (Kafka→Delta < 5 min) | Governed data availability for analysis | Data Scientist |
| SLO-06 (Payload availability > 99.9%) | AI model training data access | ML Engineer |
| SLO-07 (Data loss = 0) | Regulatory audit readiness | Compliance Officer |
| SLO-10 (FlexCache hit > 80%) | Reduced cloud storage cost | FinOps / CFO |

---

## BIZ-002: Go/No-Go Decision Framework

### Phase A → Phase B Transition Criteria

| Category | GO Criteria | NO-GO Criteria | PIVOT Criteria |
|----------|------------|---------------|----------------|
| **Technical** | All 6 PoC success criteria met (TSK-000) | Data loss detected in any test | — |
| **Latency** | End-to-end < 5s (real-time path) confirmed | Latency consistently > 30s | Reduce scope to fewer topics |
| **Cost** | Monthly cost < $1,500 | Monthly cost > $3,000 | Remove ClickHouse Cloud; use BYOC |
| **Integration** | Kafka→ClickHouse + Kafka→Databricks both working | Kafka→ClickHouse Kafka Engine fails with MSK IAM | Use Kafka Connect Sink instead |
| **Storage** | FlexCache concept validated (or deferred to Phase B) | FSx for ONTAP fundamentally incompatible | Use native S3 for payloads (lose multiprotocol) |
| **Vendor** | Instaclustr SE confirms on-prem ClickHouse availability | Instaclustr cannot deploy ClickHouse on-prem | Self-managed ClickHouse for Phase B |
| **Timeline** | Phase A complete within 20 days | Phase A exceeds 60 days | Re-scope to minimum viable validation |

### Decision Authority

| Decision | Authority | Input From |
|----------|-----------|-----------|
| Go/No-Go for Phase B | Architecture Lead | All PoC results, cost data |
| Budget approval for on-prem hardware | Business Sponsor (TBD) | Cost estimate, business metrics |
| Vendor selection confirmation | Architecture Lead | Instaclustr SE engagement results |
| Architecture pivot | Architecture Lead + Stakeholders | Technical blockers, alternatives analysis |

---

## BIZ-003: Before/After Narrative

### Current State (Before)

- Factory data exists in isolated systems (PLC historians, quality databases, file shares)
- No real-time visibility across factories
- Quality defects detected hours or days after occurrence
- AI/ML teams manually transfer files for training (days of lead time)
- Data duplicated multiple times across systems (historian → batch ETL → data warehouse → ML platform)
- No unified governance or lineage tracking

### Future State (After)

- Unified event stream from all factory devices (Kafka backbone)
- Real-time OEE and quality dashboards (ClickHouse, < 5 second freshness)
- Governed data lake for AI/ML (Databricks + Unity Catalog)
- Zero-copy payload access from cloud (FlexCache — no data duplication)
- Single source of truth for manufacturing data (on-premises ONTAP)
- Full audit trail: who accessed what data, when, for what purpose

### What this buys you (30-second version)

> This platform eliminates data silos between factory floor and cloud analytics.
> Quality events are visible in real-time (seconds, not hours).
> AI/ML teams access factory data without copying it to the cloud.
> One architecture serves both operational dashboards and governed analytics.
> Data stays in one place (on-premises); the cloud accesses it on demand.

---

## Design Review Notes

> Notes recorded while checking this decision against the design concerns listed in [design concern checklist](08_design_concern_checklist.md). Self-review, not external review.

- **Storage**: P99 latency targets defined per segment. Throughput contention model documented. ONTAP S3 auth chain complete.
- **Business outcome**: Business metrics mapped to technical SLOs. Before/after narrative provides stakeholder context.
- **Cost**: Throughput budget quantified. Upgrade path clear (128→256→512 MB/s).
- **Product decision**: Go/No-Go framework with measurable criteria. Decision authority defined.
- **Confidentiality check**: All metrics, targets, and narratives are generic. No customer-specific baselines.

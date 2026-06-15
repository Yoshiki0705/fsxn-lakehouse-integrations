# Instaclustr Team Request — Manufacturing Data Platform PoC

> **Purpose**: Internal request template for engaging the Instaclustr team.
> **Note**: This file is for internal preparation only. Remove or move to private location before public push if it contains any internal context.

---

## Request Summary

Requesting demo/PoC environment access and technical guidance for a manufacturing data platform architecture validation that combines:
- **Instaclustr Managed Kafka** (on-premises)
- **Instaclustr Managed ClickHouse** (cloud + on-premises)
- **Amazon FSx for NetApp ONTAP** (storage layer)
- **Databricks + Unity Catalog** (governed analytics)

---

## Phase A Request (Immediate — Cloud)

### What We Need

1. **Instaclustr for ClickHouse — Cloud trial/demo account**
   - Purpose: Validate Kafka Engine integration with Amazon MSK
   - Deployment: AWS ap-northeast-1 (or us-east-1 as alternative)
   - Duration: 1-2 months
   - Scale: Development tier (minimal — PoC workload)
   - Key requirement: Kafka Engine support with SASL_SSL authentication

2. **Technical guidance**: Can ClickHouse Kafka Engine on Instaclustr connect to Amazon MSK Serverless with IAM auth or SASL/SCRAM?

### What We Can Provide

- Architecture design (13 ADRs documented)
- Synthetic workload generator (ready to run)
- Expected data volume: ~100-1000 events/sec during testing
- No production data — all synthetic

---

## Phase B Request (Planning — On-Premises)

### What We Need

1. **On-premises Kafka cluster sizing and requirements**
   - Workload: Manufacturing sensor data + quality events
   - Throughput: 1000-5000 events/sec peak
   - Retention: 7-90 days depending on topic
   - Topics: 5 (with 3-12 partitions each)
   - Replication to AWS MSK (MirrorMaker 2)
   - Authentication: SASL/SCRAM + TLS

2. **On-premises ClickHouse sizing and requirements**
   - Workload: Real-time operational analytics
   - Data volume: ~100 GB/month growing
   - Query pattern: Sub-second aggregations on time-series data
   - Kafka Engine ingestion from local Kafka cluster
   - S3 tiered storage to on-prem ONTAP S3 endpoint

3. **Hardware minimum requirements**
   - CPU, RAM, storage specs per node
   - Minimum node count for HA
   - Network requirements (bandwidth, latency)
   - OS requirements

4. **ClickHouse on-prem GA status**
   - Last published: Private Preview (July 2024)
   - Question: Is it now GA or available for PoC engagement?

5. **Licensing model for demo/PoC**
   - Is there a demo license for internal validation?
   - Duration needed: 3-6 months
   - Scale: Minimal (3 Kafka nodes, 2 ClickHouse nodes)

### Timeline

| Milestone | Target |
|-----------|--------|
| Phase A (AWS cloud) validation start | This week |
| Instaclustr engagement call | This week / next week |
| Phase B hardware requirements received | Within 2 weeks |
| Hardware procurement decision | Within 1 month |
| Phase B on-prem deployment | 2-3 months |

---

## Architecture Context

```
Phase B Target Architecture:

On-Premises (Factory):
  Edge (Raspberry Pi) → Instaclustr Kafka (on-prem)
                              ↓
                    Instaclustr ClickHouse (on-prem)
                    [real-time dashboards]
                              ↓
                    MirrorMaker 2 → AWS MSK
                              
  On-prem ONTAP (payload origin) → FlexCache → FSx for ONTAP (AWS cache)

AWS:
  MSK (replicated topics) → Databricks Structured Streaming → Delta Lake
  Unity Catalog governs Delta tables on native S3
  FlexCache provides on-demand payload access (no data duplication)
```

### Key Design Decisions Relevant to Instaclustr

| ADR | Decision | Instaclustr Impact |
|-----|----------|-------------------|
| ADR-006 | ClickHouse Cloud for Phase A | Need Instaclustr Cloud trial |
| ADR-007 | Phased deployment (AWS → hybrid) | Need on-prem sizing for Phase B |
| ADR-009 | Kafka Engine as primary connector | Need confirmation of Kafka Engine support |

### Published References (from Instaclustr blog)

We're building on patterns documented in:
- "How FSx for ONTAP and Managed ClickHouse enhance lakehouse analytics" (Instaclustr blog)
- "Amazon Q + ClickHouse + Kafka + ONTAP integration" (Instaclustr resource)
- "Understanding NetApp Instaclustr architectures, part 3: Running workloads on-premises"

---

## Questions for Instaclustr Team

1. Is Instaclustr for ClickHouse available for PoC/demo engagement (cloud)?
2. What is the current GA status for on-premises ClickHouse?
3. Can Kafka Engine on Instaclustr ClickHouse connect to external Kafka (MSK) with SASL_SSL?
4. What are the minimum hardware specs for an on-prem 3-node Kafka + 2-node ClickHouse PoC?
5. Is there a Terraform provider for on-prem deployments, or is it API/console only?
6. What network bandwidth is recommended between on-prem Kafka and on-prem ClickHouse?
7. Is there a demo/internal license available for this type of architecture validation?


---

## Additional Questions (Updated 2026-06-08)

### AWS-side Kafka Deployment

We encountered connectivity issues between AWS MSK and ClickHouse Cloud (Multi-VPC PrivateLink requirement). This raises the question of whether Instaclustr Kafka on AWS would be a better fit:

8. **Does Instaclustr offer managed Kafka on AWS** (not just on-premises)?
   - BYOC (customer VPC) or Instaclustr-hosted on AWS?
   - Can it be deployed in the same VPC as our workloads (eliminating PrivateLink needs)?

9. **If Instaclustr Kafka is available on AWS**, can Instaclustr manage the replication between:
   - On-premises Instaclustr Kafka cluster → AWS Instaclustr Kafka cluster?
   - What replication mechanism is used (MirrorMaker 2, proprietary)?

10. **VPC connectivity**: If Instaclustr Kafka runs in our AWS VPC (BYOC), can ClickHouse Cloud connect to it via VPC peering (instead of the complex Multi-VPC PrivateLink setup required by MSK)?

11. **Cost comparison**: What is the approximate monthly cost for an Instaclustr Kafka cluster on AWS (3 nodes, development tier) compared to MSK Provisioned (kafka.m5.large × 2)?

### Context for These Questions

We discovered that:
- MSK Serverless cannot be accessed from ClickHouse Cloud at all
- MSK Provisioned requires kafka.m5.large ($300+/month) for Multi-VPC connectivity
- Having both on-prem and cloud Kafka managed by Instaclustr would simplify operations significantly
- The NetApp ecosystem story (Instaclustr + ONTAP + ClickHouse) is stronger with unified Kafka management


---

## Critical Architecture Question (Updated 2026-06-08)

### Kafka on NFS (ONTAP) + FlexCache for Cross-Site Data Sharing

NetApp has published TR-4947 validating Apache Kafka running with log directories on NFS (ONTAP). Performance benchmarks exist for both on-premises AFF and FSx for ONTAP.

**Architecture hypothesis we want to validate:**

```
On-prem ONTAP ──(FlexCache + write-back)──→ FSx for ONTAP (AWS)
    ↑ NFS mount                                    ↑ NFS mount
On-prem Kafka brokers                        AWS Kafka brokers
    (Instaclustr managed)                    (Instaclustr managed)
```

**Questions:**

12. Is it technically feasible to run Kafka with log directories on ONTAP NFS volumes, and use FlexCache (with write-back mode) to share the data layer between on-premises and AWS Kafka brokers?

13. What are the constraints from Kafka's KRaft (or ZooKeeper) metadata consensus protocol when brokers are geographically distributed? Is the storage layer (FlexCache) the bottleneck, or is it the Kafka cluster membership protocol?

14. Has Instaclustr validated or considered a Kafka deployment where the storage layer is NFS-backed (ONTAP)? Is this a supported configuration in Instaclustr's managed environment?

15. If a single cross-site Kafka cluster is not feasible due to KRaft latency constraints, can Instaclustr manage two separate clusters (on-prem + AWS) with built-in replication between them?

**Reference:** NetApp TR-4947 — Apache Kafka workload with NetApp NFS storage
**Reference:** https://docs.netapp.com/us-en/netapp-solutions-ai/data-analytics/kafka-nfs-perf-aws-fsxn.html

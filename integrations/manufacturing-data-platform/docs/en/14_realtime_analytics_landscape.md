# Real-Time Analytics in a Hybrid Manufacturing Architecture: Positioning Guide

🌐 English | [日本語](../ja/14_realtime_analytics_landscape.md)

> Last updated: 2026-06-16
> Context: Databricks Data + AI Summit 2026 — Lakehouse//RT announcement

---

## Background

At the Databricks Data + AI Summit (June 2026), Databricks announced **Lakehouse//RT**, a new real-time analytics capability powered by the "Reyden" engine. Lakehouse//RT enables millisecond-level queries directly on governed Delta Lake and Apache Iceberg tables, with the stated goal of eliminating the need for separate real-time serving systems.

This document evaluates how Lakehouse//RT affects the architecture of a hybrid manufacturing data platform that includes both on-premises real-time analytics (ClickHouse) and cloud-based governed analytics (Databricks).

---

## Architecture Context: Three-Layer Hybrid Platform

```
Layer 1: Edge/Factory (on-premises)
  Kafka → ClickHouse → Local dashboards, anomaly detection

Layer 2: Real-time cloud analytics
  Kafka (replicated) → ClickHouse Cloud or Lakehouse//RT → Operational dashboards

Layer 3: Governed AI and analytics
  Databricks → Unity Catalog → Delta/Iceberg → AI, BI, compliance
```

The question Lakehouse//RT raises: **Does Layer 2 still need a dedicated real-time database, or can Databricks now serve both Layer 2 and Layer 3?**

---

## Comparison: Dedicated Real-Time DB vs Lakehouse//RT

| Dimension | Dedicated RT DB (e.g., ClickHouse) | Lakehouse//RT (Databricks) |
|-----------|-----------------------------------|---------------------------|
| Deployment options | On-premises, cloud, hybrid | Cloud only (current) |
| Query latency | 1-50ms (tuned MergeTree) | 10-100ms (Reyden engine, preview) |
| Data format | Proprietary columnar | Open formats (Delta, Iceberg) |
| Governance integration | External (no built-in catalog) | Native (Unity Catalog, lineage, tags) |
| Ingestion latency | Sub-second (Kafka Engine) | Seconds to minutes (Structured Streaming) |
| Network resilience | Operates locally during outages | Requires cloud connectivity |
| Concurrency | Hundreds to thousands of concurrent queries | High (improved with Reyden) |
| Cost model | Infrastructure-based (no per-query markup) | DBU-based (compute time billing) |
| AI/ML integration | Separate pipeline needed | Native (MLflow, Feature Store, AI/BI) |
| Multi-engine access | SQL only | SQL + Python + Spark + REST |

---

## When Lakehouse//RT Can Replace a Dedicated RT Engine

1. **All data is already in Databricks** — No separate ingestion path needed
2. **Cloud-only architecture** — No on-premises or edge requirements
3. **Governance is the primary concern** — Unity Catalog lineage and access control are non-negotiable
4. **10-100ms latency is acceptable** — Dashboard and BI use cases (not sub-10ms alerting)
5. **Unified platform preference** — Organization wants to minimize systems to manage

## When a Dedicated RT Engine Remains Necessary

1. **On-premises / edge deployment** — Factory floor, manufacturing line, disconnected environments
2. **Sub-10ms latency requirement** — Real-time alerting, anomaly detection, control system feedback
3. **Ultra-high-frequency ingestion** — Millions of events/second with sub-second visibility
4. **Network-resilient operation** — Must continue during cloud connectivity loss
5. **Cost-sensitive high-volume queries** — No per-query compute billing; fixed infrastructure cost
6. **Lightweight deployment** — No need for full Databricks platform for a single analytics use case

---

## Hybrid Architecture: Both Can Coexist

For manufacturing and industrial IoT use cases, the optimal architecture often uses **both**:

```
On-premises                              Cloud (AWS)
┌──────────────────────┐          ┌──────────────────────────┐
│ Sensors/PLCs/Cameras │          │                          │
│        │             │          │   Kafka (replicated)     │
│        ▼             │          │        │                 │
│ Kafka (local)        │─────────▶│        ▼                 │
│        │             │          │ Databricks Lakehouse//RT │
│        ▼             │          │ (governed, AI-ready,     │
│ ClickHouse (local)   │          │  millisecond queries)    │
│ - Anomaly detection  │          │                          │
│ - Quality dashboard  │          │ Unity Catalog governance │
│ - Sub-5ms alerting   │          │ AI/ML model training     │
│                      │          │ Cross-plant comparison   │
│ Payload Storage      │          │                          │
│ (ONTAP on-prem)      │─ ─ ─ ─ ─ │ FSx for ONTAP (cache)    │
└──────────────────────┘          └──────────────────────────┘
```

**Division of responsibility:**
- **Local ClickHouse**: Immediate operational analytics (line-stop decisions, quality alerts, OEE)
- **Lakehouse//RT / Databricks**: Cross-plant analysis, AI model serving, governed BI, compliance reporting

---

## Impact on This PoC

| PoC Component | Lakehouse//RT Impact | Action |
|---------------|---------------------|--------|
| On-premises ClickHouse (Phase B) | **No impact** — Lakehouse//RT is cloud-only | Continue as designed |
| ClickHouse Cloud (Phase A) | **Potential replacement** — if Databricks is already in the platform | Evaluate after Lakehouse//RT GA |
| Kafka → ClickHouse pipeline | **Complementary** — ClickHouse for local RT, Databricks for governed analytics | Keep both paths |
| Databricks Structured Streaming | **Enhanced** — Lakehouse//RT may reduce latency for streaming tables | Monitor GA performance |

### Recommendation

For this PoC:
- **Phase A (AWS)**: Continue with ClickHouse Cloud for real-time validation. Re-evaluate when Lakehouse//RT reaches GA and pricing is clear.
- **Phase B (On-premises)**: ClickHouse on-prem via Instaclustr is unaffected. Lakehouse//RT has no on-premises option.
- **Long-term**: The "both" architecture (local ClickHouse + cloud Databricks) is validated by Lakehouse//RT's cloud-only scope.

---

## Key Takeaways

1. Lakehouse//RT is a significant advancement for cloud-based real-time analytics within Databricks
2. It directly targets the "separate serving layer" pattern (ClickHouse, Druid, Pinot in cloud)
3. It does NOT address on-premises, edge, or network-disconnected real-time analytics
4. For hybrid manufacturing architectures, both layers remain necessary
5. The storage layer (ONTAP / FSx for ONTAP) is unaffected — it serves both patterns as the payload source

---

## References

- [Databricks: Introducing Lakehouse//RT](https://www.databricks.com/blog/introducing-lakehousert-real-time-performance-unified-lakehouse) (2026-06-16)
- [Databricks: Press Release](https://www.databricks.com/company/newsroom/press-releases/databricks-launches-lakehousert-bring-real-time-analytics-directly) (2026-06-16)
- [ClickHouse vs Databricks: Join Performance](https://clickhouse.com/blog/join-me-if-you-can-clickhouse-vs-databricks-snowflake-join-performance) (2025)
- [ClickHouse: Real-Time Analytics Platforms Comparison](https://clickhouse.com/resources/engineering/real-time-analytics-platforms-a-practical-comparison) (2025)

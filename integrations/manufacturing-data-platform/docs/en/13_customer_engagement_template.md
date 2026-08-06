# Customer Engagement Template

🌐 **English** | [日本語](../ja/13_customer_engagement_template.md)

---

> Addresses P1-#7 from [design concern checklist](08_design_concern_checklist.md) (partner reusability).
> Provides a reusable template for positioning this architecture in customer conversations.

---

## Template: Manufacturing Data Platform — Customer Discovery

### 1. Customer Question Identification

| # | Typical Customer Question | Maps To |
|---|--------------------------|---------|
| Q1 | "How can we get real-time visibility into factory quality events?" | Real-time analytics (ClickHouse + Kafka) |
| Q2 | "We have data in file shares (NFS/SMB) that AI teams can't access easily" | FlexCache + metadata/payload separation |
| Q3 | "We want to use Databricks but our data lives on-premises" | Hybrid architecture (Instaclustr on-prem + AWS Databricks) |
| Q4 | "We're copying data everywhere — historian → ETL → warehouse → ML" | Zero-copy with FlexCache, single source of truth |
| Q5 | "How do we govern manufacturing data across factories?" | Unity Catalog + schema-per-factory |
| Q6 | "Edge devices generate huge files (images, video) — how to handle?" | Metadata/payload separation (ADR-005) |

### 2. Industry Pattern Mapping

| Industry | Pattern | Key Components |
|----------|---------|---------------|
| Manufacturing (discrete) | Quality inspection + real-time OEE | Kafka + ClickHouse + ONTAP (images) |
| Manufacturing (process) | Sensor monitoring + anomaly detection | Kafka + ClickHouse + Databricks (ML) |
| Automotive | Vision inspection + traceability | ONTAP (video) + Kafka + Unity Catalog |
| Semiconductor | Metrology data + yield analysis | ClickHouse (high-cardinality) + Delta Lake |
| Food & Beverage | Temperature monitoring + compliance | Kafka + ClickHouse + audit trail |

### 3. Stakeholder Map

| Role | Interest | Key Metric |
|------|----------|-----------|
| VP Manufacturing / Plant Manager | Production uptime, quality yield | OEE, defect rate, response time |
| Quality Director | Defect detection speed, traceability | Time-to-detect, audit completeness |
| IT Director / CIO | Data consolidation, cost, governance | TCO, data duplication ratio, compliance |
| Data Science Lead | Access to factory data for ML models | Data access time, model training throughput |
| Operations Manager | Dashboard freshness, alerting | Dashboard latency, false alarm rate |

### 4. Discovery Questions (for customer meeting)

```
□ What data sources exist on the factory floor today?
  (Historians, PLCs, SCADA, MES, quality systems, cameras)

□ What protocols are in use? (OPC-UA, Modbus, MQTT, NFS, SMB, S3)

□ What is the current latency from event to visibility?
  (Real-time? Minutes? Hours? Next day?)

□ Where does large file data (images, video, documents) live today?
  (Local file servers? NAS? Object storage?)

□ Are there multiple factories? How is data shared between them?

□ What analytics platform is in use or planned?
  (Databricks? Snowflake? Custom? None?)

□ What are the compliance/governance requirements?
  (Audit trail? Data classification? Retention?)

□ Is there existing on-premises infrastructure (NetApp ONTAP, Kafka)?

□ What is the budget/timeline for a PoC?

□ Who is the business sponsor for this initiative?
```

### 5. PoC Success Criteria Template

| # | Criterion | Measurement | Target | Owner |
|---|-----------|-------------|--------|-------|
| 1 | Real-time event visibility | Event-to-dashboard latency | < 5 seconds | Quality Director |
| 2 | Governed data lake populated | Delta tables in Unity Catalog | Tables queryable | Data Science Lead |
| 3 | Payload accessibility | Image retrieval time from cloud | < 10 seconds | ML Engineer |
| 4 | No data loss | Event reconciliation | 0 lost events | IT Director |
| 5 | Cost within budget | Monthly AWS spend | < $X/month | IT Director |
| 6 | Failure recovery | Pipeline restart after simulated failure | Resume without data loss | Operations |

### 6. Go/No-Go Checklist

```
□ All PoC success criteria met?
□ Cost within agreed budget?
□ No blocking technical issues identified?
□ Business sponsor confirmed value?
□ Next phase (production/expansion) scope defined?
□ Operational ownership assigned for next phase?
□ Vendor commitments confirmed (Instaclustr, Databricks)?
```

### 7. Partner Delivery Checklist

| Phase | Deliverable | Template Available |
|-------|-------------|-------------------|
| Discovery | Customer requirements document | This template (Section 4) |
| Architecture | Solution design (ADR-based) | ADR-001 through ADR-013 |
| PoC | Infrastructure deployment | poc/infrastructure/ (CloudFormation) |
| PoC | Data pipeline code | poc/synthetic-data-generator/ |
| PoC | Validation results | Success criteria table (Section 5) |
| Decision | Go/No-Go recommendation | Section 6 checklist |
| Handoff | Operational runbooks | docs/en/10_slo_operational_readiness.md |
| Handoff | Security configuration | docs/en/12_security_hardening.md |

### 8. Reusable Assets from This Project

| Asset | Path | Purpose |
|-------|------|---------|
| Architecture Decision Records | docs/adr/ | Reusable decision templates |
| Synthetic data generator | poc/synthetic-data-generator/ | PoC validation tool |
| MSK CloudFormation template | poc/infrastructure/ | Quick infrastructure deployment |
| SLO framework | docs/en/10_slo_operational_readiness.md | Operational readiness template |
| Security hardening guide | docs/en/12_security_hardening.md | Security configuration reference |
| Bilingual glossary | docs/glossary_ja_en.md | Technical term alignment |
| Performance targets | docs/en/11_performance_targets_business_metrics.md | Sizing and budget reference |

---

## Design Review Notes

> Notes recorded while checking this decision against the design concerns listed in [design concern checklist](08_design_concern_checklist.md). Self-review, not external review.

- **Partner reusability**: This template directly addresses all P1 findings. Partners can use discovery questions in customer meetings. PoC success criteria template is reusable. Delivery checklist maps to project assets.
- **Business outcome**: Business outcome mapped to stakeholders. Success criteria include measurable targets with owners.
- **Product decision**: Go/No-Go checklist with clear decision points. Next-phase scope required for GO decision.
- **Confidentiality check**: Template is generic. No customer-specific information. Industry examples are public knowledge.

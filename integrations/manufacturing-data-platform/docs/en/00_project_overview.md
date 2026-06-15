# OVR-000: Project Overview

🌐 **English** | [日本語](../ja/00_project_overview.md)

---

## Manufacturing Data Platform PoC — Architecture Validation

### Purpose

This project validates an AWS-based manufacturing data platform architecture that integrates edge/factory data pipelines with Databricks Unity Catalog **without relying on S3 Access Points**.

The goal is to determine whether the proposed architecture is feasible for a PoC and whether it can serve as a credible architecture pattern for:

- Manufacturing data consolidation
- Real-time analytics
- Downstream AI/analytics activation

### Architecture Hypothesis

Instead of directly integrating object storage with Databricks Unity Catalog through S3 Access Points, this architecture uses:

| Component | Role |
|-----------|------|
| Apache Kafka (Amazon MSK) | Factory data event backbone — carries structured events and lightweight metadata |
| ClickHouse | Real-time analytics engine — sub-second queries on high-frequency sensor/quality data |
| FSx for ONTAP | Storage layer for large unstructured payloads (documents, images, video) |
| Databricks + Unity Catalog | Downstream governed analytics and AI platform — curated Delta tables |
| Native Amazon S3 | Physical storage for Delta Lake tables governed by Unity Catalog |

### Data Flow Summary

```
Edge/Factory → MQTT/Kafka Producers → Kafka Topics
                                          ↓
                              ┌───────────┼───────────┐
                              ↓           ↓           ↓
                        ClickHouse   Databricks    FSx for ONTAP
                        (real-time   (Structured   (payload store:
                         analytics)   Streaming     images, video,
                                      → Delta)      documents)
                              ↓           ↓
                         Dashboards  Unity Catalog
                                     governed tables
                                     on native S3
```

### Key Design Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| DEC-001 | Delta Lake tables stored on native Amazon S3 | Unity Catalog only supports native S3/ADLS/GCS/R2 for external locations. S3-compatible endpoints (including ONTAP S3) are not supported. |
| DEC-002 | Kafka as primary ingestion path to Databricks | Structured Streaming provides exactly-once guarantees when writing to Delta tables. Well-supported, production-proven pattern. |
| DEC-003 | ClickHouse for real-time operational analytics | Sub-second query latency on high-cardinality manufacturing data. Not a replacement for Databricks but a complement for operational dashboards. |
| DEC-004 | FSx for ONTAP for unstructured payload storage | Multiprotocol access (NFS/SMB/S3), Snapshot, SnapMirror, enterprise data protection. Delta tables reference payloads via path/URI. |
| DEC-005 | No direct S3 Access Points dependency | Architecture works without S3 Access Points. Payloads stored on FSx for ONTAP; metadata and curated analytics on native S3 via Kafka. |

### Project Scope

- Technical research and validation (not production deployment)
- Public GitHub repository (no confidential content)
- Bilingual documentation (Japanese primary, English parallel)
- Evidence-based assessment with cited sources
- PoC design with minimum viable components

### Out of Scope

- Production deployment
- Real customer data
- Vendor commercial negotiations
- Regulatory compliance certification
- Performance benchmarking at scale

### Document Structure

| Document | Content |
|----------|---------|
| 00_project_overview | This document |
| 01_requirements | Functional and non-functional requirements |
| 02_research_findings | Technical research results with sources |
| 03_architecture_design | Detailed architecture design |
| 04_risks_and_considerations | Risk register and mitigation |
| 05_poc_plan | PoC implementation plan |
| 06_decision_matrix | Architecture decision matrix |
| glossary_ja_en | Bilingual glossary |
| references | All research sources |
| confidentiality_review | Public repository safety check |

### Stable ID Conventions

| Prefix | Domain |
|--------|--------|
| OVR- | Overview |
| REQ- | Requirements |
| RES- | Research findings |
| DES- | Architecture design |
| RSK- | Risks |
| TSK- | PoC tasks |
| DEC- | Decisions |
| REF- | References |

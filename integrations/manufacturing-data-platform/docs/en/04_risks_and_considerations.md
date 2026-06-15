# Risks and Considerations

🌐 **English** | [日本語](../ja/04_risks_and_considerations.md)

---

## Persona Review-Identified Risks

The following risks were specifically identified during the 5-persona architecture review (see [07_persona_review_initial.md](07_persona_review_initial.md)):

### RSK-014: Edge Buffering Not Designed (Persona 2)

- **Description:** No store-and-forward or local buffering mechanism is designed for edge devices when Kafka is unreachable. Factory networks can be intermittent.
- **Impact:** High — Data loss during network partitions between edge and cloud
- **Likelihood:** High (factory networks are inherently less reliable than cloud)
- **Severity:** High
- **Mitigation:** Design edge buffering (local MQTT persistence, filesystem queue, or embedded Kafka). Addressed in TSK-002.
- **Status:** Not yet designed — Must Fix before PoC execution

### RSK-015: ClickHouse/Databricks Data Divergence (Persona 1)

- **Description:** Both ClickHouse and Databricks consume from the same Kafka topics but process independently. Data counts and states may diverge due to different processing semantics (at-least-once vs exactly-once), timing, or failures.
- **Impact:** Medium — Inconsistent analytics results across real-time and governed views
- **Likelihood:** Medium
- **Severity:** Medium
- **Mitigation:** (1) Define data reconciliation strategy. (2) Accept divergence for real-time (ClickHouse) vs governed (Databricks) as intentional. (3) Periodic reconciliation check in PoC validation.
- **Status:** Accepted trade-off; needs monitoring strategy

### RSK-016: Payload Integrity Verification Gap (Persona 2)

- **Description:** No automated mechanism to verify that payload files on FSx for ONTAP are complete, uncorrupted, and match the checksums recorded in Kafka metadata events.
- **Impact:** Medium — Corrupted or incomplete payloads referenced from Delta tables
- **Likelihood:** Medium (file transfers can fail silently)
- **Severity:** Medium
- **Mitigation:** (1) Checksum verification after upload. (2) Kafka metadata event published only after payload upload confirmed. (3) Periodic integrity scan job. (4) PoC validates with TSK-012.
- **Status:** Requires design and PoC validation

### RSK-017: FSx for ONTAP Over-Positioning Risk (Persona 4)

- **Description:** FSx for ONTAP may be positioned for roles where native S3 would be simpler and cheaper. Risk of over-engineering the payload storage layer for a PoC.
- **Impact:** Low for PoC (manageable cost); Medium for production credibility
- **Likelihood:** Medium
- **Severity:** Low
- **Mitigation:** (1) Clearly define where FSx for ONTAP adds value vs where native S3 suffices. (2) Document honest trade-off analysis (DEC-005). (3) PoC should include a comparison of same operation on S3 vs FSx for ONTAP.
- **Status:** Acknowledged; addressed in ADR-003 and DEC-005

---

## Technical Risks

### RSK-001: Unity Catalog Does Not Support S3-Compatible External Locations

- **Description:** Unity Catalog external locations only support native Amazon S3, Azure ADLS, GCS, and Cloudflare R2. S3-compatible endpoints (ONTAP S3, MinIO) are not supported.
- **Impact:** High — Delta Lake tables cannot be stored on FSx for ONTAP via ONTAP S3
- **Likelihood:** Confirmed (not a risk but a constraint)
- **Severity:** Critical for architecture design; already mitigated by design decision DEC-001
- **Mitigation:** Delta tables are stored exclusively on native Amazon S3. FSx for ONTAP serves as payload storage only.
- **Status:** Mitigated by design

### RSK-002: ClickHouse Spark Connector Maturity

- **Description:** The ClickHouse Spark connector is community-maintained and may have version compatibility issues with specific Databricks Runtime versions.
- **Impact:** Medium — ClickHouse→Databricks batch reads could fail or perform poorly
- **Likelihood:** Medium
- **Severity:** Low (ClickHouse→Databricks is a secondary path; primary ingestion is via Kafka)
- **Mitigation:** (1) Test connector compatibility during PoC. (2) Use S3 export as fallback pattern. (3) Keep ClickHouse→Databricks path optional.
- **Status:** Needs PoC validation

### RSK-003: ClickHouse to ONTAP S3 Tiered Storage Performance

- **Description:** ClickHouse S3 tiered storage with ONTAP S3 as backend has not been publicly validated. Performance characteristics may differ from native S3.
- **Impact:** Medium — Cold tier queries could be slower than expected
- **Likelihood:** Medium
- **Severity:** Medium
- **Mitigation:** (1) Validate during PoC with representative query patterns. (2) Benchmark cold tier latency vs native S3. (3) Prepare fallback to native S3 for cold tier.
- **Status:** Needs PoC validation

### RSK-004: Streaming Pipeline Failure Recovery Complexity

- **Description:** Kafka→ClickHouse and Kafka→Databricks streaming pipelines require coordinated checkpoint management and failure recovery procedures.
- **Impact:** Medium — Data loss or duplication during failures
- **Likelihood:** Low (well-documented patterns)
- **Severity:** Medium
- **Mitigation:** (1) Structured Streaming provides exactly-once to Delta Lake. (2) ClickHouse Kafka engine provides at-least-once with deduplication via ReplacingMergeTree. (3) Document recovery runbooks.
- **Status:** Mitigated by design; validate in PoC

### RSK-005: Network Connectivity Complexity

- **Description:** Multiple components (MSK, ClickHouse, Databricks, FSx for ONTAP) need private network connectivity within or across VPCs.
- **Impact:** High — Components cannot communicate if networking is misconfigured
- **Likelihood:** Medium
- **Severity:** High
- **Mitigation:** (1) Deploy all components in same VPC or use VPC peering. (2) Document security group rules. (3) Use VPC endpoints for S3/AWS services. (4) Validate connectivity first in PoC.
- **Status:** Requires careful PoC setup

---

## Operational Risks

### RSK-006: Multi-Component Operational Complexity

- **Description:** Operating MSK + ClickHouse + Databricks + FSx for ONTAP requires diverse expertise across multiple managed services.
- **Impact:** High — Difficult to troubleshoot cross-component issues
- **Likelihood:** High
- **Severity:** Medium for PoC, High for production
- **Mitigation:** (1) Use managed services wherever possible (MSK Serverless, ClickHouse Cloud, Databricks managed). (2) Centralize observability. (3) Document operational runbooks.
- **Status:** Accepted for PoC; major consideration for production

### RSK-007: Cost Estimation Uncertainty

- **Description:** Combined cost of MSK + ClickHouse + Databricks + FSx for ONTAP is difficult to estimate accurately without load testing.
- **Impact:** Medium — PoC budget may be exceeded
- **Likelihood:** Medium
- **Severity:** Medium
- **Mitigation:** (1) Start with minimum sizing. (2) Set cost alerts. (3) Use serverless/on-demand where available. (4) Estimate cost model before starting PoC.
- **Status:** Requires pre-PoC cost model

### RSK-008: Edge Device Payload Upload Reliability

- **Description:** Large file uploads (images, video) from edge/factory to FSx for ONTAP may fail due to network instability.
- **Impact:** Medium — Payload data loss
- **Likelihood:** Medium (factory networks can be unstable)
- **Severity:** Medium
- **Mitigation:** (1) Implement retry with exponential backoff. (2) Use checksums for integrity verification. (3) Kafka metadata event only sent after payload upload confirmed. (4) Local edge buffering.
- **Status:** Requires PoC validation

---

## Governance Risks

### RSK-009: Split Governance Between Unity Catalog and FSx for ONTAP

- **Description:** Structured data is governed by Unity Catalog. Unstructured payloads are governed by FSx for ONTAP permissions. This creates a split governance model.
- **Impact:** Medium — Inconsistent access control, audit gaps
- **Likelihood:** High (inherent to the architecture)
- **Severity:** Medium
- **Mitigation:** (1) Document which system governs what. (2) Align access policies. (3) Centralize audit logs (CloudTrail + ONTAP audit). (4) Payload access requires both Delta table permission and FSx permission.
- **Status:** Accepted trade-off; document clearly

### RSK-010: Payload URI Integrity

- **Description:** Delta tables contain payload_uri referencing FSx for ONTAP. If payloads are moved, renamed, or deleted, references become stale.
- **Impact:** Medium — Broken references lead to analysis failures
- **Likelihood:** Medium
- **Severity:** Medium
- **Mitigation:** (1) Immutable payload storage (write-once, no rename/delete in hot path). (2) Use Snapshot for versioning. (3) Periodic URI validation job. (4) Include checksum for integrity verification.
- **Status:** Requires design validation in PoC

---

## Vendor/Product Risks

### RSK-011: ClickHouse Cloud Availability and Pricing Changes

- **Description:** ClickHouse Cloud is a relatively newer managed service. Pricing models and feature availability may change.
- **Impact:** Low — May affect cost or deployment model
- **Likelihood:** Low
- **Severity:** Low
- **Mitigation:** (1) Architecture is not locked to ClickHouse Cloud specifically. (2) Self-managed or BYOC are alternatives. (3) Monitor ClickHouse product roadmap.
- **Status:** Accepted

### RSK-012: Confluent Tableflow Regional Availability

- **Description:** Confluent Tableflow (Kafka→Delta Lake→UC automatic materialization) may not be available in all regions or for all Kafka deployment types (e.g., self-managed MSK).
- **Impact:** Low — Falls back to custom Structured Streaming (which is proven)
- **Likelihood:** Medium
- **Severity:** Low
- **Mitigation:** (1) Primary approach is Databricks Structured Streaming (always available). (2) Tableflow is an optional enhancement for Confluent Cloud users.
- **Status:** Accepted; Tableflow is optional

---

## Confidentiality Risks

### RSK-013: Public Repository Content Safety

- **Description:** All project content is published to a public GitHub repository. Accidental inclusion of confidential information is a risk.
- **Impact:** High — Reputation damage, NDA violations
- **Likelihood:** Low (with proper review process)
- **Severity:** High
- **Mitigation:** (1) Confidentiality review checklist for every document. (2) No real customer/partner names. (3) Synthetic data only. (4) Pre-commit hooks for secret detection. (5) Persona 5 review.
- **Status:** Active mitigation; requires ongoing vigilance

---

## Risk Summary Matrix

| Risk ID | Category | Severity | Likelihood | Status |
|---------|----------|----------|------------|--------|
| RSK-001 | Technical | Critical | Confirmed | Mitigated by design |
| RSK-002 | Technical | Low | Medium | Needs PoC validation |
| RSK-003 | Technical | Medium | Medium | Needs PoC validation |
| RSK-004 | Technical | Medium | Low | Mitigated by design |
| RSK-005 | Technical | High | Medium | Requires PoC setup |
| RSK-006 | Operational | Medium | High | Accepted for PoC |
| RSK-007 | Operational | Medium | Medium | Requires cost model |
| RSK-008 | Operational | Medium | Medium | Needs PoC validation |
| RSK-009 | Governance | Medium | High | Accepted trade-off |
| RSK-010 | Governance | Medium | Medium | Needs design validation |
| RSK-011 | Vendor | Low | Low | Accepted |
| RSK-012 | Vendor | Low | Medium | Accepted |
| RSK-013 | Confidentiality | High | Low | Active mitigation |
| RSK-014 | Technical | High | High | **Must Fix** — Not yet designed |
| RSK-015 | Technical | Medium | Medium | Accepted trade-off |
| RSK-016 | Technical | Medium | Medium | Needs design + PoC validation |
| RSK-017 | Positioning | Low | Medium | Acknowledged |

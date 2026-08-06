# 08: Design Concern Checklist — Manufacturing Data Platform Architecture

🌐 **English** | [日本語](../ja/08_design_concern_checklist.md)

---

## Scope

> Each numbered section below covers one design concern, checked against a checklist derived from AWS Well-Architected and industry practice. This is a structured self-review of our own design — not an interview, survey, or review by external experts, and not an approval by any body.

- **Analysis date:** 2026-06-07
- **Scope:** All 13 ADRs (ADR-001 through ADR-013), PoC plan, synthetic data generator, infrastructure templates
- **Deliverable Type:** Architecture + PoC Plan + Code (all ten concerns apply)

---

## 1. Partner Reusability and Methodology

### Assessment

| Question | Status | Finding |
|----------|--------|---------|
| Can a partner use this in a customer meeting tomorrow? | ⚠️ Partial | Architecture is well-documented but lacks a 1-page executive summary and customer-facing deck narrative |
| Is the first customer question clear? | ❌ Missing | No explicit "customer question" or problem statement framed from end-user perspective |
| Is the expected PoC output clear? | ✅ | TSK-000 defines 6 success criteria clearly |
| Are stakeholders and Business Sponsor identified? | ❌ Missing | No stakeholder map or business sponsor role defined |
| Is there a reusable checklist or template? | ⚠️ Partial | ADRs serve as templates but no "workshop outcome" template exists |
| Workshop-ready? | ❌ No | Cannot run as a partner workshop without facilitation guide |
| Handoff artifacts complete? | ⚠️ Partial | Runbooks not yet created; escalation path undefined |

### Improvement Recommendations

1. **Create `docs/en/09_customer_engagement_template.md`** — Map: Customer Question → Industry Pattern → Business Outcome → PoC Success Criteria → Go/No-Go Decision
2. **Add stakeholder roles** to the PoC plan: Business Sponsor, Technical Decision Maker, IT Operations Owner, Data Platform Owner
3. **Create a 1-page architecture summary** suitable for non-technical executive briefing
4. **Define handoff artifacts** for partner delivery: runbook, FAQ, escalation path, cost model template

### Priority: P1 (Should fix before positioning as partner-reusable asset)

---

## 2. Storage

### Assessment

| Question | Status | Finding |
|----------|--------|---------|
| Storage service choice justified by workload? | ✅ | ADR-003, ADR-013 clearly justify FSx for ONTAP for multiprotocol edge + FlexCache for cloud access |
| Object/file/block semantics correctly separated? | ✅ | Clear: files on ONTAP (NFS/SMB), Delta on S3 (object), no confusion |
| S3AP over-described as S3 bucket equivalent? | ✅ N/A | Architecture explicitly avoids S3AP dependency (ADR-004) |
| FlexCache, FlexClone, Snapshot accurately described? | ✅ | ADR-007 (FlexCache), ADR-013 (Snapshot, FlexClone) are accurate |
| Tail latency / P99 considered? | ❌ Missing | No P99 latency targets defined for FlexCache cache-miss or payload access |
| FSx throughput capacity implications clear? | ⚠️ Partial | 128 MB/s stated but shared throughput across NFS+SMB+S3 not analyzed |
| Authorization chain complete? | ⚠️ Partial | NFS export policy + security groups defined, but ONTAP S3 auth chain (IAM → S3AP policy → ONTAP user) not fully documented |
| Network path correct? | ⚠️ Partial | VPC diagram exists (DES-008) but FlexCache WAN path (VPN/DX → intercluster LIF) not detailed |
| Benchmark scoped? | ❌ Missing | No benchmark plan with controlled environment, object sizes, concurrency levels |

### Improvement Recommendations

1. **Define P99 latency targets** for: FlexCache cache hit, FlexCache cache miss (WAN), NFS file read, ONTAP S3 GET
2. **Document shared throughput budget**: 128 MB/s is shared across all protocols. At peak image upload (NFS) + ClickHouse cold read (S3) + FlexCache fill, what's the contention model?
3. **Complete ONTAP S3 authorization chain**: For ClickHouse cold tier access: ClickHouse → ONTAP S3 endpoint → SVM S3 user → bucket policy → volume. Document each hop.
4. **Add FlexCache network path detail**: VPN/DX bandwidth requirements, intercluster LIF placement, expected WAN latency for cache-miss scenario
5. **Define benchmark plan** for PoC: object sizes (5MB, 20MB, 50MB images), concurrency (1, 10, 50 parallel reads), controlled environment, benchmark_run_id convention

### Priority: P1 (Latency targets and throughput budget should be defined before PoC sizing is finalized)

---

## 3. Governance and Privacy

### Assessment

| Question | Status | Finding |
|----------|--------|---------|
| Overstate regulated workload readiness? | ✅ No | Clearly scoped as PoC, not production/regulatory |
| Legal/compliance/privacy not replaced? | ✅ | No claims about regulatory compliance |
| Decision owner defined? | ❌ Missing | No decision owner, approval flow, or data owner roles |
| Authoritative data source clear? | ✅ | On-prem ONTAP is origin (ADR-007), FlexCache is cache — clearly stated |
| Cached/cloned data paths auditable? | ⚠️ Partial | FlexCache is transparent to clients, but no audit logging strategy for cache access defined |
| Sample runs clearly non-production? | ✅ | "SYNTHETIC" markers throughout all generated data |
| Data readiness assessment included? | ❌ Missing | No data classification, data owner, retention, disposal assessment |

### Improvement Recommendations

1. **Add data classification** to ADR-013 or a new document: classify each data type (sensor readings = operational, quality images = potentially regulated, equipment status = operational)
2. **Define data ownership roles**: Who owns sensor data? Quality data? Payload images? Define per data type.
3. **Add FlexCache audit strategy**: Document how to track "who accessed which cached payload via FlexCache" — ONTAP audit log captures origin access, but FlexCache access auditing needs explicit design
4. **Add data retention/disposal policy**: How long are payloads kept? When are they deleted? Who authorizes deletion?
5. **State explicitly**: "This PoC does not address regulatory compliance, data residency, or privacy requirements. These must be assessed separately for production deployment."

### Priority: P2 (Important for production, acceptable to defer for PoC phase)

---

## 4. Business Outcome and Adoption

### Assessment

| Question | Status | Finding |
|----------|--------|---------|
| Business outcome defined? | ⚠️ Vague | "Manufacturing data consolidation, real-time analytics, AI activation" — but no specific measurable outcome |
| Success metrics defined before implementation? | ⚠️ Partial | 6 PoC success criteria (TSK-000) but they are technical ("events flow"), not business ("reduced defect detection time") |
| PoC goal measurable? | ✅ | Technical metrics are measurable (latency, throughput, data loss = 0) |
| Safe experimentation boundaries? | ✅ | PoC on AWS, synthetic data, no production impact |
| Next action clear? | ✅ | Phase A → Phase B transition well-documented |
| PoC-to-production journey clear? | ⚠️ Partial | Phase A/B defined but production Go/No-Go criteria not formalized |

### Improvement Recommendations

1. **Define business success metrics** alongside technical ones:
   - "Quality defect detected within X minutes of occurrence" (vs current: Y minutes)
   - "OEE dashboard refresh rate: real-time (< 5s)" (vs current: batch/daily)
   - "Time from image capture to AI classification: < Z minutes"
2. **Add Go/No-Go criteria** for Phase A → Phase B transition:
   - All 6 technical success criteria met ✅
   - Cost within budget ($610-1,480/month) ✅
   - No blocking vendor issues ✅
   - Instaclustr SE engagement confirmed ✅
3. **Define "what changed" narrative**: Before this platform: [current state]. After: [future state]. Make it 30-second readable.
4. **Add adoption narrative**: Who uses ClickHouse dashboards? Who uses Databricks? What decisions do they make differently?

### Priority: P1 (Business value framing needed before stakeholder engagement)

---

## 5. Security

### Assessment

| Question | Status | Finding |
|----------|--------|---------|
| Least privilege? | ⚠️ Partial | UC permissions (ADR-011) follow least privilege. Kafka IAM policy (msk-serverless.yaml) grants broad topic access `factory.*` |
| Secrets management? | ⚠️ Partial | "AWS Secrets Manager" mentioned (DES-009) but no implementation detail. ClickHouse/Kafka credentials not explicitly managed. |
| Encryption at rest + in transit? | ⚠️ Partial | TLS for Kafka confirmed. S3 SSE-KMS stated. FSx for ONTAP encryption not explicitly configured in ADR-013 |
| Audit trail complete? | ⚠️ Partial | UC audit + ONTAP audit mentioned. CloudTrail not configured. ClickHouse query audit not addressed. |
| Data classification boundaries in code? | ❌ Missing | No classification enforcement (e.g., preventing quality images from being written to wrong volume) |
| Policy boundaries explicit? | ⚠️ Partial | What is denied not documented — only what is allowed |

### Improvement Recommendations

1. **Tighten Kafka IAM policy**: Instead of `factory.*` for all topics, separate producer (write-only to specific topics) and consumer (read-only from specific topics) policies
2. **Document secrets management**: Where are SASL/SCRAM credentials, ONTAP S3 keys, ClickHouse passwords stored? How are they rotated? Add to PoC setup procedure.
3. **Explicitly configure FSx for ONTAP encryption**: State `EncryptionConfiguration` with KMS key in deployment (it's default-on but should be explicit)
4. **Add deny policies**: Document what each role CANNOT do (e.g., pipeline_service cannot SELECT, analysts cannot MODIFY)
5. **Add ClickHouse audit**: Enable `query_log` system table retention policy for audit of who queried what
6. **Add CloudTrail configuration**: Ensure S3 data events, KMS events, and Kafka API events are logged

### Priority: P1 (Security hardening should be part of PoC, not deferred to production)

---

## 6. Reliability and Operations

### Assessment

| Question | Status | Finding |
|----------|--------|---------|
| Runbook for every alarm? | ❌ Missing | ADR-008 defines monitoring metrics/thresholds but no runbook for remediation |
| SLOs defined? | ❌ Missing | No SLO table (target availability, latency percentiles, data loss tolerance) |
| Auto-recovery for common failures? | ⚠️ Partial | Kafka producer retries automatically. ClickHouse Kafka Engine retries. But Databricks streaming job restart is manual. |
| Rollback documented? | ❌ Missing | No rollback procedure for failed schema evolution, bad deployment, or corrupted state |
| Operational ownership assigned? | ❌ Missing | No "who gets paged" definition |
| Dependencies mapped? | ⚠️ Partial | Component diagram exists but no explicit dependency failure mode analysis |

### Improvement Recommendations

1. **Create SLO table**:
   | SLO | Target | Measurement |
   |-----|--------|-------------|
   | Event ingestion availability | 99.9% | % of time Kafka accepts writes |
   | ClickHouse query availability | 99.5% | % of successful queries |
   | Streaming pipeline freshness | < 5 min lag | Kafka offset lag → Delta table |
   | Payload availability | 99.9% | % of payload_uri resolvable |
   | Data loss | 0 events | Kafka offset vs Delta row count reconciliation |

2. **Create runbook index** for ADR-008 failure scenarios (at least stubs)
3. **Add auto-restart for Databricks streaming**: Configure Databricks job scheduler with retry policy
4. **Define rollback procedures**: Schema evolution rollback, bad data quarantine, pipeline checkpoint reset
5. **Add dependency failure mode table**: What happens when each component fails? What's the blast radius?

### Priority: P0 (SLOs and operational ownership should be defined before any PoC execution)

---

## 7. Cost

### Assessment

| Question | Status | Finding |
|----------|--------|---------|
| Cost assumptions stated explicitly? | ✅ | ADR-013 ($220/month FSx), PoC plan ($610-1,480/month total) |
| Sample vs production clearly separated? | ✅ | ADR-013 has both PoC sizing and production projection |
| Throughput/cost trade-offs? | ⚠️ Partial | FSx throughput tiers mentioned but cost delta not quantified |
| Business-hours scheduling? | ❌ Missing | ClickHouse Cloud, Databricks, MSK run 24/7 during PoC? |
| Cost controls? | ⚠️ Partial | "Set cost alerts" mentioned but no specific budget alarm configuration |

### Improvement Recommendations

1. **Add business-hours scheduling**: For PoC, consider stopping Databricks clusters and pausing ClickHouse Cloud during non-working hours (potential 60% cost reduction)
2. **Quantify throughput tier cost impact**: 128 MB/s = $87/month vs 256 MB/s = $174/month. Document when to scale.
3. **Add concrete cost alert**: CloudWatch Billing alarm at $1,000/month (PoC budget threshold)
4. **Document PoC exit cost**: What does it cost to tear down everything? Any minimum commitments?
5. **Add MSK Serverless cost model**: MSK Serverless charges per partition-hour + data. At low PoC volume, this could be very cheap ($20-50/month) — clarify.

### Priority: P2 (Acceptable for PoC start, but scheduling should be implemented early)

---

## 8. Documentation

### Assessment

| Question | Status | Finding |
|----------|--------|---------|
| New reader understands in 2 minutes? | ⚠️ Partial | 00_project_overview.md is good but ADR-heavy; no visual architecture diagram (image) |
| All links valid? | ✅ | Internal links reference existing files; external links verified during research |
| Series continuity? | ✅ | Language switcher headers on all docs; consistent ID scheme |
| Public wording appropriate? | ✅ | No internal jargon; clear technical language |
| Reader paths clear? | ⚠️ Partial | No explicit "start here" guide for different reader types (executive, engineer, partner) |
| Code examples copy-pasteable? | ✅ | generate_events.py runs with --dry-run; SQL examples are valid |

### Improvement Recommendations

1. **Add visual architecture diagram** (Mermaid or PNG): The ASCII diagrams are functional but a rendered diagram improves scannability
2. **Create reader path guide** in project README:
   - Executive → 00_project_overview + 06_decision_matrix (5 min read)
   - Engineer → 03_architecture_design + ADR index (30 min read)
   - Partner/SI → 09_customer_engagement_template (once created)
3. **Add project-level README.md** at `integrations/manufacturing-data-platform/README.md` with quick-start
4. **Add CHANGELOG.md** tracking major decisions and phase completions

### Priority: P2 (Polish before public visibility; acceptable for internal development)

---

## 9. Test Automation

### Assessment

| Question | Status | Finding |
|----------|--------|---------|
| Unit tests for business logic? | ❌ Missing | generate_events.py and generate_payloads.py have no test files |
| Integration tests for critical paths? | ⚠️ Defined | ADR-008 defines 8 test cases but no automated test implementation |
| Benchmark repeatability? | ❌ Missing | No fixed seeds, no benchmark_run_id, no controlled environment spec |
| Test fixtures versioned? | ❌ Missing | No sample event fixtures for reproducible testing |
| Quality gates in CI? | ❌ Missing | No GitHub Actions workflow for this sub-project |
| Tests run without external dependencies? | ⚠️ Partial | --dry-run works without Kafka, but no mocked integration test |

### Improvement Recommendations

1. **Add unit tests**: `tests/test_generate_events.py` — validate event schema, event_id uniqueness, payload_uri format
2. **Add test fixtures**: `tests/fixtures/sample_events.json` — known-good events for integration testing
3. **Add CI workflow**: `.github/workflows/manufacturing-poc-lint.yml` — Python lint (ruff) + type check (mypy) + unit tests
4. **Implement dedup verification test**: Automated script that sends duplicates and verifies single record in target
5. **Add benchmark reproducibility**: Fixed random seed option (`--seed 42`), benchmark_run_id in output, environment capture
6. **Add mock Kafka integration test**: Use `confluent_kafka.admin.MockProducer` or testcontainers for local Kafka

### Priority: P1 (Unit tests and CI should be added before PoC execution to prevent regression)

---

## 10. Product Decision

### Assessment

| Question | Status | Finding |
|----------|--------|---------|
| Success metrics before implementation? | ⚠️ Technical only | 6 technical success criteria. No business metrics. |
| Business sponsor who validates? | ❌ Missing | No business sponsor role defined |
| Go/No-Go criteria measurable? | ⚠️ Partial | Technical Go/No-Go implied but not formalized |
| Customer-specific baseline? | ❌ Missing | No "current state" baseline to compare against |
| Measurable value demonstrated? | ⚠️ Partial | "Sub-second queries" is measurable but "manufacturing data consolidation" is not |
| Adoption narrative for decision-makers? | ❌ Missing | No executive-friendly narrative |

### Improvement Recommendations

1. **Define 3 business metrics**:
   - Metric 1: "Time from quality event to dashboard visibility" (target: < 5s; baseline: TBD hours)
   - Metric 2: "Payload retrieval time for AI/ML pipeline" (target: < 10s via FlexCache; baseline: manual transfer hours)
   - Metric 3: "Data availability across on-prem and cloud" (target: same-day; baseline: batch overnight)
2. **Add Go/No-Go decision framework** to PoC plan:
   - GO if: all 6 technical criteria met + cost < $1,500/month + no vendor blockers
   - NO-GO if: data loss detected OR latency > 30s OR cost > $3,000/month
   - PIVOT if: ClickHouse↔ONTAP S3 tiering fails → fall back to native S3 cold tier
3. **Define business sponsor role**: Even for internal PoC, identify who approves Phase B budget
4. **Create "before/after" slide**: 1 slide showing current state (manual, batch, siloed) vs future state (automated, real-time, unified)

### Priority: P1 (Business framing needed for any stakeholder presentation)

---

## Consolidated Improvement Plan

### P0 (Must address before PoC execution)

| # | Item | Source Persona | Effort |
|---|------|---------------|--------|
| 1 | Define SLOs and operational ownership | Reliability and operations | Medium |
| 2 | Create dependency failure mode table | Reliability and operations | Low |

### P1 (Should address before external sharing)

| # | Item | Source Persona | Effort |
|---|------|---------------|--------|
| 3 | Define P99 latency targets and throughput budget | Storage | Medium |
| 4 | Define business success metrics (not just technical) | Business outcome, Product decision | Low |
| 5 | Tighten security: secrets management, deny policies, audit | Security | Medium |
| 6 | Add unit tests + CI workflow | Test automation | Medium |
| 7 | Create customer engagement template | Partner reusability | Medium |
| 8 | Add Go/No-Go decision framework | Product decision | Low |
| 9 | Complete ONTAP S3 authorization chain | Storage | Low |
| 10 | Add auto-restart for Databricks streaming | Reliability and operations | Low |

### P2 (Can defer to later iteration)

| # | Item | Source Persona | Effort |
|---|------|---------------|--------|
| 11 | Add data classification and ownership | Governance and privacy | Medium |
| 12 | Add business-hours scheduling for cost | Cost | Low |
| 13 | Create visual architecture diagram | Documentation | Low |
| 14 | Add reader path guide in README | Documentation | Low |
| 15 | Add FlexCache audit strategy | Governance and privacy | Medium |
| 16 | Define data retention/disposal policy | Governance and privacy | Medium |

---

## Overall Assessment

| Dimension | Rating | Notes |
|-----------|--------|-------|
| Architecture soundness | ✅ Strong | 13 ADRs cover all critical decisions with evidence |
| Technical feasibility | ✅ Confirmed | All integration paths validated with public sources |
| Partner/SI reusability | ⚠️ Needs work | Missing engagement template, stakeholder map, workshop materials |
| Security posture | ⚠️ Needs hardening | Basics present but secrets, deny policies, audit trail incomplete |
| Operational readiness | ❌ Gaps | No SLOs, no runbooks, no operational ownership |
| Business value articulation | ⚠️ Needs framing | Technical metrics defined; business outcomes not yet articulated |
| Test coverage | ❌ Gaps | No automated tests, no CI, no benchmark repeatability |
| Documentation quality | ✅ Good | Bilingual, well-structured, language switchers, clear IDs |
| Cost management | ✅ Good | Estimates present, production projection included |
| Confidentiality | ✅ Clear | No sensitive content found; safe for public repository |

### Overall: **feasible, conditional on the P0 and P1 items above**

Architecture is technically sound and well-documented. Before PoC execution:
1. Define SLOs (P0)
2. Add unit tests + CI (P1)
3. Define business metrics (P1)

Before external/partner sharing:
4. Create customer engagement template (P1)
5. Harden security configuration (P1)

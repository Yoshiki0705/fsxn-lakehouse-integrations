# Finding Classification & Routing Decision Matrix

> **Status**: Final
> **Last Updated**: 2026-07-21
> **Context**: Phase 4 — Stakeholder Communication (S3 AP + SnapMirror + FlexCache Multi-Cloud)

---

## Classification Scheme

All 41 findings are reclassified into 4 action-oriented categories:

| Category | Definition | Routing Target |
|----------|-----------|----------------|
| **works_as_expected** | Supported per documentation. No action required. | AWS Community (public) |
| **works_with_caveats** | Functional but with important operational constraints. Document in runbook. | AWS Community (public) + Field teams |
| **does_not_work_feature_request** | Not supported; workaround exists. Submit Feature Request. | AWS FSx PM / NetApp BU |
| **blocked_requires_product_change** | Architectural constraint; no practical workaround. Submit Feature Request. | AWS FSx PM / NetApp BU |

---

## Full Classification Table

### S3 AP + SnapMirror (SM-001 — SM-007)

| Finding ID | Topic | Final Classification | Routing | Public? |
|:----------:|-------|:--------------------:|---------|:-------:|
| SM-001 | S3 AP volume as SnapMirror Async source | works_as_expected | AWS Community | Yes |
| SM-002 | S3 AP metadata preservation after transfer | works_as_expected | AWS Community | Yes |
| SM-003 | Object Store Server constraint on dest SVM | works_as_expected | AWS Community | Yes |
| SM-004 | SVM-DR unsupported with S3 NAS bucket | blocked_requires_product_change | AWS FSx PM + NetApp BU | Yes |
| SM-005 | S3 AP re-attach after failover | works_with_caveats | AWS Community + Field | Yes |
| SM-006 | S3 AP IAM policy AWS-layer independence | works_as_expected | AWS Community | Yes |
| SM-007 | ONTAP S3 + SnapMirror compatibility overview | works_as_expected | AWS Community | Yes |

### S3 AP + FlexCache (FC-001 — FC-007)

| Finding ID | Topic | Final Classification | Routing | Public? |
|:----------:|-------|:--------------------:|---------|:-------:|
| FC-001 | S3 AP-attached volume as FlexCache Origin | works_as_expected | AWS Community | Yes |
| FC-002 | Independent S3 AP attachment on Cache Volume | works_as_expected (version_gated: 9.18.1+) | AWS Community | Yes |
| FC-003 | FlexCache version compatibility | works_as_expected | AWS Community | Yes |
| FC-004 | Write-back mode + S3 AP XLD behavior | works_with_caveats | NetApp BU (doc request) + Field | Yes |
| FC-005 | NFS v4 Delegation / Lock Propagation | works_with_caveats | AWS Community + Field | Yes |
| FC-006 | Eviction policy and cache hit measurement | works_as_expected | AWS Community | Yes |
| FC-007 | FlexGroup + S3 AP + FlexCache Origin | works_with_caveats | AWS Community + Field | Yes |

### Cross-Cloud SnapMirror Paths (XC-001 — XC-008)

| Finding ID | Topic | Final Classification | Routing | Public? |
|:----------:|-------|:--------------------:|---------|:-------:|
| XC-001 | FSx for ONTAP → FSx for ONTAP (same region) | works_as_expected | AWS Community | Yes |
| XC-002 | FSx for ONTAP → FSx for ONTAP (cross-region) | works_as_expected | AWS Community | Yes |
| XC-003 | FSx for ONTAP → On-premises ONTAP | works_as_expected | AWS Community | Yes |
| XC-004 | FSx for ONTAP → CVO on GCP | works_as_expected | AWS Community | Yes |
| XC-005 | FSx for ONTAP → CVO on Azure | works_as_expected | AWS Community | Yes |
| XC-006 | FSx for ONTAP → GCNV (External Replication) | works_as_expected | AWS Community | Yes |
| XC-007 | FSx for ONTAP → ANF | does_not_work_feature_request | NetApp BU | Yes |
| XC-008 | Encryption & Snapshot consistency | works_as_expected | AWS Community | Yes |

### NFS/SMB Authentication (AUTH-001 — AUTH-005)

| Finding ID | Topic | Final Classification | Routing | Public? |
|:----------:|-------|:--------------------:|---------|:-------:|
| AUTH-001 | NFS auth on SnapMirror destination | works_as_expected | AWS Community | Yes |
| AUTH-002 | NFS auth on FlexCache Cache Volume | works_as_expected | AWS Community | Yes |
| AUTH-003 | SMB auth on SnapMirror destination | works_as_expected | AWS Community | Yes |
| AUTH-004 | Volume security style preservation | works_as_expected | AWS Community | Yes |
| AUTH-005 | Cross-domain AD trust & name-mapping | works_as_expected | AWS Community | Yes |

### SVM Structural Constraints (implicit in SM-003, SM-004)

Covered by SM-003/SM-004 above. No additional standalone SVM findings require separate routing.

### FlexCache Cross-Region/Cross-Cloud (FCXC-001 — FCXC-007)

| Finding ID | Topic | Final Classification | Routing | Public? |
|:----------:|-------|:--------------------:|---------|:-------:|
| FCXC-001 | FSx for ONTAP inter-region FlexCache | works_as_expected | AWS Community | Yes |
| FCXC-002 | FSx for ONTAP → On-premises (DX/VPN) | works_as_expected | AWS Community | Yes |
| FCXC-003 | FSx for ONTAP → CVO (GCP/Azure) | works_as_expected | AWS Community | Yes |
| FCXC-004 | Intercluster LIF requirements (per-path) | works_as_expected | AWS Community | Yes |
| FCXC-005 | GCNV/ANF FlexCache support | works_with_caveats | AWS Community + Field | Yes |
| FCXC-006 | Network latency impact on FlexCache | works_as_expected | AWS Community | Yes |
| FCXC-007 | FlexCache disconnect mode | works_as_expected | AWS Community | Yes |

### Conditional Writes (CW-001 — CW-002)

| Finding ID | Topic | Final Classification | Routing | Public? |
|:----------:|-------|:--------------------:|---------|:-------:|
| CW-001 | S3 AP `If-None-Match` unsupported (501) | works_as_expected | AWS Community | Yes |
| CW-002 | Conditional Writes & SnapMirror consistency | works_as_expected | AWS Community | Yes |

---

## Summary by Category

| Category | Count | Finding IDs |
|----------|:-----:|-------------|
| works_as_expected | 32 | SM-001/002/003/006/007, FC-001/002/003/006, XC-001~006/008, AUTH-001~005, FCXC-001~004/006/007, CW-001/002 |
| works_with_caveats | 5 | SM-005, FC-004, FC-005, FC-007, FCXC-005 |
| does_not_work_feature_request | 2 | XC-007, FC-004 (documentation request) |
| blocked_requires_product_change | 2 | SM-004, XC-007 |

> **Note**: XC-007 appears in both `does_not_work_feature_request` and `blocked_requires_product_change` because it requires both a product enhancement (ANF Cluster Peering) and has a viable workaround (CVO on Azure). The feature request targets the long-term product direction while the workaround serves immediate needs.

> **Note**: FC-004 is classified as `works_with_caveats` (it functions correctly) but also warrants a documentation request to NetApp BU because the XLD revoke behavior with S3 AP writes is not explicitly documented.

---

## Feature Request Targets

| Finding ID | Target | Type | Priority |
|:----------:|--------|------|:--------:|
| SM-004 | AWS FSx PM + NetApp BU | Product Enhancement (SVM-DR + S3 NAS bucket) | High |
| XC-007 | NetApp BU (ANF team) | Product Enhancement (ANF External Cluster Peering) | Medium |
| FC-004 | NetApp BU (ONTAP docs) | Documentation Enhancement (XLD + S3 AP write interaction) | Medium |

---

## Public Disclosure Assessment

All 41 findings are based on publicly verifiable information (official documentation, public APIs, reproducible behavior). No findings contain:
- Internal IP addresses or account IDs
- Support case numbers or internal ticket references
- Customer-specific configuration details

**Conclusion**: All findings are safe for public disclosure in blog posts, conference presentations, and community documentation.

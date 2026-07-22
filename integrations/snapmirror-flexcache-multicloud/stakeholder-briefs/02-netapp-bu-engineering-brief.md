# Stakeholder Brief: NetApp BU / ONTAP Engineering

> **Audience**: NetApp Business Unit, ONTAP Engineering, ANF Engineering
> **Classification**: Shareable with NetApp internal
> **Date**: 2026-07-21
> **From**: AWS Community Builder (Storage/Data Analytics)

---

## Purpose

Technical memo summarizing FSx for ONTAP S3 AP + SnapMirror/FlexCache validation results, with two actionable items routed to NetApp BU:
1. **XC-007**: ANF External Cluster Peering feature request
2. **FC-004**: FlexCache write-back documentation enhancement for S3 NAS bucket interaction

---

## Validation Environment

| Component | Details |
|-----------|---------|
| FSx for ONTAP | 2nd Generation, Single-AZ, ap-northeast-1 |
| ONTAP Version | 9.17.1P7D1 |
| Test Scope | S3 AP + SnapMirror (intra-cluster), S3 AP + FlexCache (intra-cluster) |
| Test Cases | TC-01 through TC-05, all PASS |
| Methodology | ONTAP REST API + AWS CLI, manual execution with evidence capture |

---

## Key Technical Findings

### Confirmed: S3 NAS Bucket + SnapMirror Async Works

The S3 NAS bucket mechanism (underlying FSx for ONTAP S3 AP) creates a standard FlexVol with `object-store-server` configured. Since SnapMirror Async operates at the volume level:
- Volume-level SnapMirror relationship creation succeeds
- Data written via S3 API is replicated (crash-consistent at Snapshot boundary)
- Destination volume provides NFS/SMB access after SnapMirror break

This is architecturally straightforward — the S3 lens does not alter the volume's replication characteristics.

### Confirmed: S3 NAS Bucket + FlexCache Origin Works

FlexCache Origin requirements are met by any FlexVol/FlexGroup. The presence of `object-store-server` configuration does not block FlexCache relationship creation. Validated on 9.17.1:
- Cache Volume creation succeeds
- NFS read from Cache returns data written via S3 AP to Origin
- Write-back mode functions (with XLD caveat documented below)

### Caveat: FlexCache Write-Back XLD Revoke via S3 API Write (FC-004)

When S3 API writes to the Origin Volume (via S3 NAS bucket), ONTAP correctly treats this as an Origin-direct write and issues XLD revoke to any Cache holding dirty data for the same file.

**Observed behavior (expected, consistent with design):**
```
S3 PutObject → Origin WAFL commit → XLD revoke to Cache → Cache dirty flush → Origin wins
```

**Documentation gap**: The [FlexCache write-back guidelines](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-guidelines.html) page states that "writes to the origin will cause the exclusive lock to be revoked" but does not explicitly mention S3 NAS bucket / S3 API as a trigger path. Customers using both S3 AP ingestion and FlexCache write-back need this called out explicitly.

**Request**: Add S3 NAS bucket write as an explicit example of "Origin-direct write" in the FlexCache write-back documentation. See `feature-requests/netapp-bu/FC-004-writeback-xld-s3ap-documentation.md`.

---

## Feature Request: XC-007 — ANF External Cluster Peering

### Context

Multi-cloud ONTAP data distribution currently has an asymmetry:
- **GCP**: GCNV External Replication supports FSx for ONTAP → GCNV SnapMirror (GA 2024)
- **Azure**: ANF supports CVR (ANF-to-ANF) only; no external Cluster Peering exposed

### Request

Enable ANF to accept SnapMirror relationships from external ONTAP systems (FSx for ONTAP, CVO, on-premises), similar to how GCNV External Replication works.

### Technical Rationale

ANF runs ONTAP internally. The Cluster Peering control plane (TLS PSK authentication, Intercluster LIF communication) is a standard ONTAP capability. Exposing a managed peering endpoint (as GCNV does) would enable:
- FSx for ONTAP → ANF SnapMirror (block-level incremental, crash-consistent)
- Elimination of CVO-on-Azure intermediary for AWS → Azure data distribution
- Consistent tri-cloud architecture (AWS → GCP via GCNV, AWS → Azure via ANF)

### Detailed Request

See `feature-requests/netapp-bu/XC-007-anf-external-cluster-peering.md`

---

## Items NOT Routed to NetApp BU

| Finding | Reason Not Routed |
|---------|-------------------|
| SM-004 (SVM-DR + S3 NAS) | Routed to AWS FSx PM. This is a known ONTAP interoperability constraint documented in NetApp docs. Product roadmap decision. |
| CW-001 (Conditional Writes 501) | FSx for ONTAP S3 AP-specific. No SnapMirror integrity impact — WAFL atomicity protects. |
| SM-005 (FSx API VolumeType lag) | AWS FSx API behavior, not ONTAP-layer. |

---

## Validated Version Matrix (For Field Reference)

| Feature | Minimum ONTAP Version | Notes |
|---------|:---------------------:|-------|
| S3 NAS bucket (multiprotocol) | 9.12.1 | Required for S3 AP |
| SnapMirror Async + S3 NAS bucket volume | 9.11.1 (FSx baseline) | Volume-level only |
| FlexCache Origin with S3 NAS bucket | 9.12.1 | Origin version requirement |
| FlexCache write-back | 9.15.1 (both Origin + Cache) | 9.17.1P1+ recommended |
| Cluster Peering Encryption | 9.6 | Default enabled on new peers |
| GCNV External Replication | Source: 9.11.1+ (estimated) | GCNV manages destination |

---

## Summary

The ONTAP platform's separation of data plane (WAFL/volumes) from protocol plane (S3/NFS/SMB lenses) is validated as working correctly for this use case. The two actionable items (XC-007, FC-004) are product/documentation enhancements, not defects.

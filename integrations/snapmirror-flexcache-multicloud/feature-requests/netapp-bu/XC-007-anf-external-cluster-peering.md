# Feature Request: ANF External Cluster Peering for SnapMirror Interoperability

> **Finding ID**: XC-007
> **Target**: NetApp BU (Azure NetApp Files Engineering)
> **Priority**: Medium
> **Date**: 2026-07-21

---

## Use Case Description

Organizations operating multi-cloud architectures need to distribute data collected on AWS (via FSx for ONTAP S3 Access Points) to Azure environments where Azure NetApp Files (ANF) provides NFS/SMB storage. SnapMirror is the standard ONTAP mechanism for cross-platform data replication, but ANF currently does not expose Cluster Peering interfaces to external ONTAP systems.

**Workflow being enabled:**
1. Data is collected via FSx for ONTAP S3 AP on AWS
2. SnapMirror replicates data to Azure for local-speed NFS/SMB access by Azure workloads
3. Azure-based analytics, ML training, or application access reads from ANF volumes

**Gap:** ANF supports only Cross-Volume Replication (CVR) — an ANF-to-ANF mechanism. External ONTAP systems (FSx for ONTAP, CVO, on-premises ONTAP) cannot establish SnapMirror relationships with ANF.

---

## Impact Description

Without FSx for ONTAP → ANF SnapMirror:
- Customers must deploy CVO on Azure as an intermediary (additional infrastructure cost and management overhead)
- Alternatively, file-level sync tools (Azure DataSync, AzCopy, rsync) lose ONTAP-native efficiency (block-level incremental, crash-consistent snapshots)
- The multi-cloud data distribution architecture has an asymmetry: GCP (via GCNV External Replication) and Azure (only via CVO intermediary)

**Comparison with GCNV (Google Cloud):**
- GCNV supports External Replication from FSx for ONTAP (SnapMirror relationship, Google-managed destination)
- This capability was introduced in 2024 and demonstrates that managed ONTAP services can expose Cluster Peering to external systems

**Affected customers:**
- Multi-cloud enterprises with AWS primary + Azure secondary/DR architecture
- Organizations using Azure native services (Azure ML, Azure Databricks, Azure Synapse) that need NFS data access
- Hybrid scenarios where ANF provides the Azure storage layer

---

## Current Workaround

**Option A: CVO on Azure as intermediary**
```
FSx for ONTAP  →(SnapMirror)→  CVO on Azure  →(NFS/SMB)→  Azure Workloads
```
- Pro: Full ONTAP feature compatibility, standard SnapMirror
- Con: Additional CVO licensing and management; not a fully managed ANF experience

**Option B: File-level synchronization**
```
FSx for ONTAP  →(AWS DataSync / rsync / AzCopy)→  ANF
```
- Pro: Direct to ANF; no intermediary
- Con: File-level (not block-level) — slower, no crash-consistent snapshots, higher network usage for incremental updates

**Option C: Application-layer replication**
```
Application writes to both FSx for ONTAP S3 AP and ANF simultaneously
```
- Pro: Independent writes; no replication lag
- Con: Application complexity; no single source of truth; consistency challenges

---

## Proposed Behavior

ANF should support external Cluster Peering, enabling SnapMirror relationships from external ONTAP systems (FSx for ONTAP, CVO, on-premises ONTAP) to ANF volumes.

**Expected behavior after enhancement:**
1. ANF exposes Intercluster LIF endpoints for Cluster Peering (similar to GCNV External Replication)
2. External ONTAP cluster creates Cluster Peer relationship with ANF
3. SnapMirror Async relationship is established: `external-cluster://svm/vol → anf://svm/vol`
4. Block-level incremental replication operates with ONTAP-native efficiency
5. ANF volume provides NFS/SMB access to replicated data

**Reference implementation:** GCNV External Replication demonstrates this capability in production (GA since 2024). The ANF implementation could follow a similar model.

---

## Reproduction Steps

```bash
# 1. Verify ANF replication is ANF-to-ANF only
# Azure Portal → ANF → Volume → Replication
# Only ANF volumes in other regions/zones appear as valid targets

# 2. Attempt SnapMirror from FSx for ONTAP to ANF
# This is not possible because ANF does not expose:
#   - Intercluster LIF IP addresses
#   - Cluster Peering passphrase/authentication endpoint
#   - SnapMirror relationship acceptance interface

# 3. Expected: No mechanism exists to establish Cluster Peering with ANF
# The Azure CLI (az netappfiles) and REST API do not provide
# external replication endpoints
```

---

## Environment Information

| Item | Value |
|------|-------|
| Source: ONTAP Version | 9.17.1P7D1 (FSx for ONTAP) |
| Target: ANF | Azure NetApp Files (Standard/Premium/Ultra tiers) |
| ANF Replication | Cross-Volume Replication (CVR) — ANF-to-ANF only |
| Comparable feature | GCNV External Replication (GA, supports external ONTAP → GCNV) |
| Workaround tested | CVO on Azure as SnapMirror destination (functional) |

---

## Supporting Evidence

| Source | Key Statement |
|--------|--------------|
| [Microsoft Docs: Understand ANF Replication](https://learn.microsoft.com/en-us/azure/azure-netapp-files/replication) | Cross-region/cross-zone replication between ANF volumes only. No mention of external ONTAP sources. |
| [Microsoft Docs: ANF Replication Requirements](https://learn.microsoft.com/en-us/azure/azure-netapp-files/cross-region-replication-requirements-considerations) | Requirements reference ANF source and ANF destination only. |
| [Google Cloud Docs: GCNV External Replication](https://cloud.google.com/netapp/volumes/docs/protect-data/about-replication) | GCNV supports replication from external ONTAP systems (demonstrates feasibility). |
| [NetApp Docs: SnapMirror intercluster requirements](https://docs.netapp.com/us-en/ontap/peering/prerequisites-cluster-peering-reference.html) | Standard Cluster Peering prerequisites — ANF does not implement these endpoints. |

---

## Additional Context

This request complements the existing GCNV External Replication capability. If ANF added external Cluster Peering, ONTAP customers would have consistent multi-cloud data distribution options across all three major clouds:

| Cloud | Managed ONTAP Service | External SnapMirror From FSx for ONTAP |
|-------|----------------------|:--------------------------------------:|
| AWS | FSx for ONTAP | Yes (native) |
| GCP | GCNV | Yes (External Replication) |
| Azure | ANF | Not currently supported (this request) |
| Azure | CVO on Azure | Yes (standard SnapMirror) |

The gap is specific to ANF as a managed service. CVO on Azure provides full SnapMirror compatibility but is not a managed service equivalent.

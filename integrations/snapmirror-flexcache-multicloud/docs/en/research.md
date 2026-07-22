> 🌐 Language: [日本語](../ja/research.md) | **English**

# S3 AP + SnapMirror + FlexCache Multi-Cloud Data Distribution — Research Findings

> **Status**: Phase 3 Validation Complete | Phase 4 Communication Complete | Cross-Region SnapMirror Validated (2026-07-22)
> **Last Updated**: 2026-07-22
> **ONTAP Version Tested**: 9.17.1P7D1
> **Scope**: Multi-cloud data distribution of data collected via FSx for ONTAP S3 Access Points using SnapMirror/FlexCache
> **JA Primary**: Full research detail in `docs/ja/research.md` — this EN version provides equivalent technical depth for architecture-impacting findings

---

## Executive Summary

This research systematically evaluates the feasibility of distributing data collected via FSx for ONTAP S3 AP (S3 Access Points) to multi-cloud environments using SnapMirror and FlexCache, with NFS/SMB authenticated access at destinations.

### Findings Summary

| Classification | Count | Description |
|---------------|:-----:|-------------|
| **supported** | 32 | Confirmed via official documentation or Phase 3 validation |
| **partially_supported** | 3 | Supported under specific conditions or platform-dependent |
| **works_with_caveats** | 2+4 | Validated as working but with important operational constraints (original 2 + 4 cross-region validation findings) |
| **version_gated** | 1 | Supported from ONTAP 9.18.1; not supported on tested version (9.17.1) |
| **undocumented** | 1 | Not documented; requires hands-on validation to confirm |
| **unsupported** | 2 | Explicitly confirmed as unsupported |
| **Total** | **41** | |

### Key Conclusions

FSx for ONTAP S3 AP is based on ONTAP's "S3 NAS bucket (S3 multiprotocol)" mechanism — the volume itself remains a standard FlexVol/FlexGroup. This design enables S3 AP-attached volumes to be protected via **SnapMirror Asynchronous (Volume-level)**, making multi-cloud data distribution architecturally feasible. SnapMirror Synchronous and SVM-DR are not supported for configurations containing S3 NAS buckets.

### Top 3 Architecture-Impacting Findings

1. **SVM-DR unsupported (SM-004)**: Volume-level SnapMirror is the only option; destination SVM protocol configuration must be manually recreated
2. **ANF SnapMirror unsupported (XC-007)**: Azure data distribution requires CVO on Azure as intermediary
3. **S3 AP metadata not transferred via SnapMirror (SM-002)**: New S3 AP attachment required at destination; IAM policies must be separately configured

---

## Prerequisites & Constraints Summary

### Key Constraints (What doesn't work)

| Constraint | Finding ID | Impact |
|-----------|:----------:|--------|
| SVM-DR unsupported with S3 NAS bucket SVMs | SM-004 | Volume-level SnapMirror only. No automatic SVM config replication |
| ANF SnapMirror unsupported | XC-007 | Azure delivery requires CVO on Azure |
| SnapMirror Synchronous unsupported for S3 NAS bucket | SM-001 | RPO=0 not achievable. Async only (minimum 5-min intervals) |
| GCNV cannot be FlexCache Origin (Cache only) | FCXC-005 | Read distribution from GCNV requires SnapMirror |
| GCNV FlexCache does not support NFSv4 | FCXC-005 | NFSv3 access only to GCNV Cache Volumes |
| FlexCache write-back not recommended for RTT > 200ms | FCXC-006 | Write-around mode recommended for cross-cloud |

### Key Prerequisites (What you need)

| Prerequisite | Applicable Paths | Details |
|-------------|-----------------|---------|
| Intercluster LIF | All SnapMirror / FlexCache paths | Auto-configured on FSx for ONTAP; manual on on-premises/CVO |
| Cluster Peering (TLS 1.2 encryption) | All cross-cluster configs | Default enabled ONTAP 9.6+ |
| VPN / Direct Connect / Interconnect | On-premises / CVO / GCNV destinations | TCP 11104, 11105 + ICMP reachability required |
| Active Directory (for SMB access) | Destination SVM | AD join required. Same domain or trust relationship recommended |
| ONTAP 9.15.1+ (both Origin/Cache) | FlexCache write-back mode | 9.17.1P1+ recommended |
| ONTAP 9.12.1+ (Origin) | S3 NAS bucket + FlexCache | Minimum for S3 NAS bucket as FlexCache Origin |

### Supported Configuration Quick Reference

| Source | Destination | SnapMirror | FlexCache | Notes |
|--------|------------|:----------:|:---------:|-------|
| FSx for ONTAP | FSx for ONTAP (same region) | Yes | Yes | Simplest configuration |
| FSx for ONTAP | FSx for ONTAP (cross-region) | Yes | Yes | VPC Peering / Transit Gateway |
| FSx for ONTAP | On-premises ONTAP | Yes | Yes | Direct Connect / VPN |
| FSx for ONTAP | CVO on GCP | Yes | Yes | Cross-cloud VPN |
| FSx for ONTAP | CVO on Azure | Yes | Yes | Cross-cloud VPN |
| FSx for ONTAP | GCNV | Yes | Yes (Cache only) | External Replication / FlexCache Cache |
| FSx for ONTAP | ANF | No | No | Unsupported. Use CVO on Azure |

### S3 NAS Bucket Compatibility with FlexCache / SnapMirror

| Configuration | Supported | Min ONTAP | Official Source |
|---------------|:---------:|:---------:|----------------|
| S3 NAS bucket volume as **SnapMirror Async source** | ✅ | 9.12.1 | [S3 multiprotocol — Data protection](https://docs.netapp.com/us-en/ontap/s3-multiprotocol/index.html) |
| S3 NAS bucket volume as **SnapMirror Synchronous source** | ❌ | — | [S3 multiprotocol — Data protection](https://docs.netapp.com/us-en/ontap/s3-multiprotocol/index.html) |
| S3 NAS bucket volume in **SVM-DR** | ❌ | — | [S3 multiprotocol — Data protection](https://docs.netapp.com/us-en/ontap/s3-multiprotocol/index.html), [KB: SVM DR + S3](https://kb.netapp.com/onprem/ontap/dp/SnapMirror/Is_SVM_Disaster_Recovery_(SVM_DR)_of_S3_buckets_supported%3F) |
| S3 NAS bucket on **FlexCache Origin** volume | ✅ | 9.12.1 | [FlexCache supported features](https://docs.netapp.com/us-en/ontap/flexcache/supported-unsupported-features-concept.html) |
| S3 NAS bucket on **FlexCache Cache** volume | ✅ | **9.18.1** | [FlexCache supported features](https://docs.netapp.com/us-en/ontap/flexcache/supported-unsupported-features-concept.html), [FlexCache duality FAQ](https://docs.netapp.com/us-en/ontap/flexcache/flexcache-duality-faq.html) |
| FlexCache Cache S3 NAS bucket + **write-back mode** | ❌ | — | [FlexCache duality FAQ](https://docs.netapp.com/us-en/ontap/flexcache/flexcache-duality-faq.html) (write-around required) |
| FlexCache Cache S3 — Origin/Cache **both must be 9.18.1+** | Required | 9.18.1 | [FlexCache duality FAQ](https://docs.netapp.com/us-en/ontap/flexcache/flexcache-duality-faq.html) |
| FlexCache Origin with **SnapMirror Async relationship** | ✅ | 9.5+ | [FlexCache supported features](https://docs.netapp.com/us-en/ontap/flexcache/supported-unsupported-features-concept.html) |

---

## S3 AP + SnapMirror Interaction

### Architecture Premise

FSx for ONTAP S3 AP is based on ONTAP's **S3 multiprotocol (S3 NAS bucket)** mechanism. This is architecturally distinct from ONTAP's native S3 object store server (`vserver object-store-server`). S3 AP provides S3 protocol access to existing NAS volumes via an AWS-managed layer — the volume itself remains a standard FlexVol/FlexGroup.

This distinction is critical for SnapMirror compatibility.

---

### SM-001: S3 AP-Attached Volume as SnapMirror Source

| Item | Details |
|------|---------|
| **Finding ID** | SM-001 |
| **Classification** | `supported` (Async only) |
| **Disclosure** | publicly verifiable |

**Finding:**

NetApp ONTAP documentation states: "S3 NAS 'buckets' are simply mappings of NAS data for S3 clients, they are not standard S3 buckets. Therefore, there is no need to protect S3 NAS buckets using NetApp SnapMirror S3 functionality. Instead, you can protect volumes containing S3 NAS buckets using **SnapMirror asynchronous volume replication**."

S3 AP-attached volumes can serve as SnapMirror Async sources because the underlying volume is a standard NAS volume.

**Constraints:**
- SnapMirror **Synchronous** is NOT supported for volumes with S3 NAS buckets
- SnapMirror **Asynchronous** (schedule-based) is the only supported mode

**Evidence:**
- [NetApp Docs: ONTAP S3 multiprotocol — Data protection](https://docs.netapp.com/us-en/ontap/s3-multiprotocol/index.html)
- [AWS Docs: Replicating data using SnapMirror](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html)

---

### SM-002: S3 AP Metadata Preservation After SnapMirror Transfer

| Item | Details |
|------|---------|
| **Finding ID** | SM-002 |
| **Classification** | `supported (validated)` |
| **Disclosure** | validation evidence |

**Finding:**

S3 AP metadata exists on two layers:
1. **AWS layer (S3 AP itself)**: AP attachment, IAM policies, VPC config — AWS-managed resources not stored in ONTAP volume data
2. **ONTAP layer (`s3_unix` name-mapping)**: Auto-created by FSx on the SVM when S3 AP is attached (pattern: `amazon-fsx-<RANDOM>` → specified UNIX user)

**Phase 3 Validation (TC-01/TC-02):**
- S3 AP attachment is NOT transferred via SnapMirror (expected — it's an AWS-managed resource)
- `s3_unix` name-mapping is an SVM-level config, not transferred by volume-level SnapMirror
- Creating a new S3 AP on destination volume causes FSx to auto-create the corresponding `s3_unix` name-mapping — **no manual configuration required**
- Data (files, directories, UNIX permissions, ACLs) transfers correctly via SnapMirror

**Conclusion:** S3 AP metadata not transferring is "by design," not a limitation. Attach a new S3 AP at the destination and it works.

---

### SM-003: Object Store Server Exclusion Constraint on Destination SVM

| Item | Details |
|------|---------|
| **Finding ID** | SM-003 |
| **Classification** | `supported` (no impact) |
| **Disclosure** | publicly verifiable |

**Finding:**

The Object Store Server exclusion constraint ("ONTAP native S3 object-store-server and FSx S3 AP cannot coexist on the same SVM") does NOT propagate to the destination SVM via volume-level SnapMirror. Source and destination are independent SVMs. The destination SVM can have a new S3 AP attached as long as it does not have `vserver object-store-server` configured independently.

---

### SM-004: SVM-DR Compatibility with S3 Configurations

| Item | Details |
|------|---------|
| **Finding ID** | SM-004 |
| **Classification** | `unsupported` |
| **Disclosure** | publicly verifiable |

**Finding:**

SVM-DR is NOT supported for SVMs containing S3 NAS buckets.

**Evidence 1:** NetApp S3 multiprotocol documentation: "SnapMirror synchronous and **SVM disaster recovery are not supported**."

**Evidence 2:** NetApp KB: Error: "A Vserver DR relationship between Vserver [Source SVM] and Vserver [Destination/DR SVM] is not supported because Vserver [Source SVM] contains either an object store server, object store policy, object store user or object store bucket."

**What SVM-DR normally preserves (but cannot be used here):**
- SMB server settings (CIFS server name, AD domain)
- Name mapping and group mapping
- NFS export policies and rules
- DNS, LDAP, Kerberos settings
- UNIX user and UNIX group
- Audit information

Since SVM-DR is blocked, volume-level SnapMirror is the only option, and all above SVM configurations must be independently maintained at the destination.

**Evidence:**
- [NetApp Docs: ONTAP S3 multiprotocol](https://docs.netapp.com/us-en/ontap/s3-multiprotocol/index.html)
- [NetApp KB: Is SVM DR of S3 buckets supported?](https://kb.netapp.com/on-prem/ontap/DP/SnapMirror-KBs/Is_SVM_Disaster_Recovery_(SVM_DR)_of_S3_buckets_supported%3F)
- [NetApp Docs: SVM replication concept](https://docs.netapp.com/us-en/ontap/data-protection/snapmirror-svm-replication-concept.html)

---

### SM-005: S3 AP Re-Attachment After SnapMirror Failover

| Item | Details |
|------|---------|
| **Finding ID** | SM-005 |
| **Classification** | `supported (validated)` |
| **Disclosure** | validation evidence |

**Phase 3 Validated Procedure:**

1. Break SnapMirror relationship
2. Set junction path on destination volume (may be unset immediately after break)
3. Wait ~60s for FSx API `VolumeType` to reflect `RW` (ONTAP-level is RW immediately, but FSx API has propagation lag)
4. Create new S3 AP on destination volume:
```bash
aws fsx create-and-attach-s3-access-point \
  --name <ap-name> \
  --type ONTAP \
  --ontap-configuration \
    'VolumeId=<dest-vol-id>,FileSystemIdentity={Type=UNIX,UnixUser={Name=<unix-user>}}'
```

**Important considerations:**
- S3 AP does NOT "migrate" — a new one must be created at the destination
- New AP gets a new ARN and alias (different from source)
- Client applications must update to use the new S3 endpoint
- Cross-region: S3 AP can only be attached to volumes in the same region
- **Estimated RTO**: ~2 minutes (SnapMirror break ~instant + FSx API sync ~60s + S3 AP creation ~30s + DNS propagation ~30s)

**Additional finding (SM-VAL-004/007):** FSx API `describe-volumes` shows `VolumeType: DP` for ~60s after ONTAP break. S3 AP attachment requires `RW`. Automation scripts need a polling loop.

---

### SM-006: S3 AP IAM Policy AWS-Layer Independence

| Item | Details |
|------|---------|
| **Finding ID** | SM-006 |
| **Classification** | `supported` |
| **Disclosure** | publicly verifiable |

**Finding:** S3 AP IAM policies are AWS-layer constructs completely independent of ONTAP replication. IAM identity policies, AP resource policies, and VPC configurations exist in the AWS control plane and are not affected by SnapMirror operations. Destination S3 AP requires its own IAM configuration.

---

### SM-007: ONTAP S3 + SnapMirror Compatibility Overview

| Item | Details |
|------|---------|
| **Finding ID** | SM-007 |
| **Classification** | `supported` (Async Volume-level only) |
| **Disclosure** | publicly verifiable |

**Summary of supported/unsupported SnapMirror modes for S3 NAS bucket volumes:**

| SnapMirror Mode | Supported? | Notes |
|----------------|:----------:|-------|
| Asynchronous (Volume-level) | Yes | Standard data protection path |
| Synchronous | No | Explicitly listed as unsupported |
| SVM-DR | No | Blocked if SVM contains object-store-server |
| SnapMirror Cloud | No | Not supported for S3 NAS bucket |
| SnapMirror S3 (native S3) | N/A | Different mechanism; not applicable to S3 AP |

---

## S3 AP + FlexCache

### FC-001: S3 AP-Attached Volume as FlexCache Origin

| Item | Details |
|------|---------|
| **Finding ID** | FC-001 |
| **Classification** | `supported (validated)` |
| **Disclosure** | validation evidence |

**Finding:** S3 AP-attached volumes (S3 NAS bucket mechanism) can serve as FlexCache Origin Volumes. Validated on ONTAP 9.17.1 (intra-cluster). Origin requires ONTAP 9.12.1+ for S3 NAS bucket support.

**Phase 3 Validation (TC-03):** Cache Volume creation succeeded. NFS read from Cache returned data written via S3 AP to Origin. Data integrity confirmed with checksum comparison.

---

### FC-002: Independent S3 AP Attachment on Cache Volume

| Item | Details |
|------|---------|
| **Finding ID** | FC-002 |
| **Classification** | `version_gated` — unsupported on 9.17.1 (tested), supported from ONTAP 9.18.1 |
| **Disclosure** | publicly verifiable |

**Finding:** FlexCache Cache Volumes support ONTAP S3 NAS bucket (the mechanism underlying FSx for ONTAP S3 AP) **starting from ONTAP 9.18.1**. On ONTAP 9.17.1 (our validated environment), attempting to create an S3 AP on a FlexCache Cache Volume will fail with an error.

This is documented in NetApp's FlexCache supported/unsupported features table:
- **Origin Volume**: S3 NAS bucket supported since ONTAP 9.12.1
- **Cache Volume**: S3 NAS bucket supported since **ONTAP 9.18.1**

**Implication for FSx for ONTAP:**
- FSx for ONTAP running ONTAP 9.17.1 or earlier: S3 AP on Cache Volume is NOT possible
- FSx for ONTAP running ONTAP 9.18.1+: S3 AP on Cache Volume should be supported (pending FSx service adoption of 9.18.1)
- NFS/SMB access to Cache Volumes remains the primary access method on current FSx for ONTAP versions

**Evidence:**
- [NetApp Docs: Supported and unsupported features for FlexCache volumes](https://docs.netapp.com/us-en/ontap/flexcache/supported-unsupported-features-concept.html) — "ONTAP S3 NAS bucket: Cache — Supported beginning with ONTAP 9.18.1"
- [AWS Docs: Accessing data via S3 Access Points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)

---

### FC-003: FlexCache Version Compatibility Requirements

| Item | Details |
|------|---------|
| **Finding ID** | FC-003 |
| **Classification** | `supported` |
| **Disclosure** | publicly verifiable |

**Finding:** Origin and Cache clusters must be within 4 minor ONTAP versions of each other. Example: Cache on 9.14.1 requires Origin on 9.10.1 or later. NFSv4.x access to Cache Volumes requires both Origin and Cache on ONTAP 9.10.1+.

---

### FC-004: FlexCache Write-Back Mode + S3 AP Compatibility

| Item | Details |
|------|---------|
| **Finding ID** | FC-004 |
| **Classification** | `works_with_caveats` |
| **Disclosure** | validation evidence |

**Phase 3 Validation (TC-03/TC-05, ONTAP 9.17.1):**

FlexCache write-back mode combined with S3 AP-attached Origin volumes is functional. However, critical caveats exist:

**Confirmed behavior:**
1. Write-back FlexCache + S3 AP Origin works — Cache Volume local writes function normally
2. S3 AP writes to Origin trigger XLD (Exclusive Lock Delegation) revoke — Cache dirty data for the affected file is discarded (Origin version wins)
3. Concurrent writes to the same file from S3 AP (Origin) and NFS/SMB (Cache) result in Cache data loss

**Mechanism:**
```
S3 AP write to Origin
  → Origin detects conflicting XLD on Cache
  → XLD revoke sent to Cache
  → Cache dirty data flushed (overwritten by Origin version)
  → S3 AP write committed to Origin
  → Cache fetches updated data on next access (after TTL ~30s)
```

**Safe/Unsafe patterns:**

| Scenario | Risk | Recommendation |
|---------|------|----------------|
| S3 AP write (Origin) only, Cache is read-only | Safe | Recommended pattern |
| Cache write (NFS/SMB) only, S3 AP is read-only | Safe | Standard write-back use case |
| S3 AP write + Cache write (different files) | Safe | Per-file XLD protects |
| S3 AP write + Cache write (same file) | **Dangerous** | Cache dirty data lost. Avoid by design |

**Evidence:**
- [NetApp Docs: FlexCache write-back architecture](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-architecture.html)
- [NetApp Docs: FlexCache write-back guidelines](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-guidelines.html)
- Phase 3: TC-03, TC-05 (PASS)

---

### FC-005: NFS v4 Delegation and Lock Propagation

| Item | Details |
|------|---------|
| **Finding ID** | FC-005 |
| **Classification** | `partially_supported` |
| **Disclosure** | publicly verifiable |

**Finding:**
- NFSv4.0/4.1 access to Cache Volumes: supported since ONTAP 9.10.1
- FlexCache uses its own XLD mechanism (separate from NFSv4 protocol-level delegation)
- Write-back mode disconnected behavior: if WAN cuts out, XLD-holding Cache's files become inaccessible from all locations (consistency guarantee)
- Write-around mode: disconnection allows continued read from Origin

---

### FC-006: Eviction Policy and Cache Hit Ratio Measurement

| Item | Details |
|------|---------|
| **Finding ID** | FC-006 |
| **Classification** | `supported` |
| **Disclosure** | publicly verifiable |

**Eviction policies:**
1. **Space-based**: LRU eviction at 90% Cache Volume usage
2. **mtime-based scrubber**: 5-min cycle, flushes files unchanged for 2+ minutes
3. **RW lock limit**: Recalls lock delegations when per-constituent count exceeds 170

**Measurement:** `GET /api/storage/volumes/{uuid}/statistics` — fields: `client_requested_blocks`, `cache_miss_blocks`. Miss rate = `cache_miss_blocks / client_requested_blocks * 100`.

---

### FC-007: FlexGroup + S3 AP + FlexCache Origin

| Item | Details |
|------|---------|
| **Finding ID** | FC-007 |
| **Classification** | `partially_supported` |
| **Disclosure** | publicly verifiable |

**Finding:** FlexGroup volumes with S3 AP can serve as FlexCache Origin (ONTAP 9.13.1+). However, FlexGroup-backed FlexCache has specific constraints around constituent mapping and write-back mode stability. Recommended for read-heavy workloads; write-back with FlexGroup Origin requires validation.

---

## Cross-Cloud SnapMirror Paths

### XC-001 through XC-006: Supported Paths

| Finding ID | Path | Classification | Min ONTAP (Source) | Min ONTAP (Dest) | Network |
|:---:|------|:---:|:---:|:---:|------|
| XC-001 | FSx for ONTAP → FSx for ONTAP (same region) | `supported` | 9.11.1 | 9.11.1 | VPC internal (auto) |
| XC-002 | FSx for ONTAP → FSx for ONTAP (cross-region) | `supported` | 9.11.1 | 9.11.1 | Cross-region (auto) |
| XC-003 | FSx for ONTAP → On-Premises ONTAP | `supported` | 9.11.1 | IMT reference | DX / VPN |
| XC-004 | FSx for ONTAP → CVO on GCP | `supported` | 9.11.1 | CVO latest | AWS↔GCP VPN |
| XC-005 | FSx for ONTAP → CVO on Azure | `supported` | 9.11.1 | CVO latest | AWS↔Azure VPN |
| XC-006 | FSx for ONTAP → GCNV (External Replication) | `supported` | 9.11.1 (est.) | GCNV managed | AWS↔GCP VPN |

All paths use standard Cluster Peering with TLS 1.2 encryption (default enabled since ONTAP 9.6).

---

### XC-007: FSx for ONTAP → Azure NetApp Files (ANF)

| Item | Details |
|------|---------|
| **Finding ID** | XC-007 |
| **Classification** | `unsupported` |
| **Disclosure** | publicly verifiable |

**Finding:** ANF supports only Cross-Volume Replication (CVR) — an ANF-to-ANF mechanism. External ONTAP systems (including FSx for ONTAP) cannot establish SnapMirror relationships with ANF because ANF does not expose Cluster Peering interfaces.

**Technical reason:** ANF is built on Azure infrastructure and does not currently expose Intercluster LIF endpoints or Cluster Peering passphrase authentication to external systems. Its replication model is limited to ANF-to-ANF (Cross-Volume Replication).

**Alternatives:**
1. FSx for ONTAP → CVO on Azure (SnapMirror) → NFS/SMB from CVO
2. FSx for ONTAP → CVO on Azure (SnapMirror) → ANF (via AzCopy/DataSync for file-level sync)
3. AWS DataSync / rsync for direct file-level sync to ANF

**Context:** GCNV supports External Replication from external ONTAP systems (GA 2024). ANF does not currently offer an equivalent external peering interface. Each managed service has its own architectural decisions regarding external connectivity.

**Evidence:**
- [Microsoft Docs: Understand ANF Replication](https://learn.microsoft.com/en-us/azure/azure-netapp-files/replication)
- [Microsoft Docs: ANF Replication Requirements](https://learn.microsoft.com/en-us/azure/azure-netapp-files/cross-region-replication-requirements-considerations)

---

### XC-008: Encryption and Snapshot Consistency (Cross-Cloud)

| Item | Details |
|------|---------|
| **Finding ID** | XC-008 |
| **Classification** | `supported` |
| **Disclosure** | publicly verifiable |

**Cluster Peering Encryption:** TLS 1.2 AES-256 GCM, default enabled since ONTAP 9.6 for new peer relationships. No performance impact per NetApp KB. All data transferred between clusters is encrypted in transit.

**Encryption at rest (NAE/NVE):** At the storage layer, SnapMirror decrypts data at the source WAFL layer before transfer (since encryption keys are cluster-local), transmits over TLS-encrypted link, and the destination re-encrypts with its own key. Source/destination can independently use NVE, NAE, or plaintext — the at-rest encryption configuration is independent on each side.

**Snapshot + S3 AP write consistency:** ONTAP Snapshots are crash-consistent by default. Each completed S3 API PutObject is atomically committed to WAFL. SnapMirror transfers Snapshot-based content — always file-system consistent.

---

## NFS/SMB Authentication

| Finding ID | Topic | Classification | Key Point |
|:----------:|-------|:--------------:|-----------|
| AUTH-001 | NFS auth on SnapMirror destination | supported | All modes (AUTH_SYS, Kerberos v5/v5i/v5p) available after break |
| AUTH-002 | NFS auth on FlexCache Cache Volume | supported | Same authentication modes as Origin; credential caching at Cache |
| AUTH-003 | SMB auth on SnapMirror destination | supported | Destination SVM must be AD-joined (independent from source AD) |
| AUTH-004 | Volume security style preservation | supported | UNIX/NTFS/MIXED style preserved through SnapMirror transfer |
| AUTH-005 | Cross-domain AD trust & name-mapping | supported | Cross-domain trust or independent AD join at destination |

**Key point for AUTH-003:** After SnapMirror break, the destination SVM must have CIFS service configured and AD-joined BEFORE SMB clients can access data. This is SVM-level configuration not transferred by volume-level SnapMirror (reinforces SM-004 impact).

### Data Sovereignty Note

Cross-region and cross-cloud SnapMirror transfers move data to different geographic locations. For regulated data (GDPR, HIPAA, data residency requirements), verify that replication destinations comply with your organization's data governance policies before configuring SnapMirror relationships. FlexCache (read-only mode) also caches data blocks at remote sites — consider whether cached data residency meets compliance requirements.

---

## FlexCache Cross-Region/Cross-Cloud

| Finding ID | Topic | Classification | Key Detail |
|:----------:|-------|:--------------:|-----------|
| FCXC-001 | FSx for ONTAP inter-region FlexCache | supported (validated) | Same as intra-region; VPC Peering/TGW required. Validated 2026-07-22: ap-northeast-1 → us-west-2, data propagation <3s |
| FCXC-002 | FSx for ONTAP → On-premises (DX/VPN) | supported | Direct Connect or VPN; RTT impacts performance |
| FCXC-003 | FSx for ONTAP → CVO (GCP/Azure) | supported | Cross-cloud VPN; write-around recommended for high RTT |
| FCXC-004 | Intercluster LIF requirements | supported | TCP 11104/11105 + ICMP; auto-configured on FSx for ONTAP |
| FCXC-005 | GCNV/ANF FlexCache support | partially_supported | GCNV: Cache only (not Origin), NFSv3 only. ANF: unsupported |
| FCXC-006 | Network latency impact | supported | Read-heavy: tolerant to high RTT. Write-back: <= 200ms recommended |
| FCXC-007 | FlexCache disconnect mode | supported | Write-back: hung I/O until reconnect. Write-around: Origin reads continue |

### FCXC-005 Detail: GCNV FlexCache Constraints

- GCNV supports FlexCache as **Cache only** (cannot serve as Origin)
- NFSv3 access only to GCNV FlexCache Cache Volumes (NFSv4 not supported on GCNV FlexCache)
- If GCNV is the desired data access point, use SnapMirror (External Replication) rather than FlexCache for NFSv4 requirements

### FCXC-006 Detail: RTT Recommendations

| Mode | Max Recommended RTT | Rationale |
|------|:-------------------:|-----------|
| Read-only (write-around) | No hard limit (200+ ms acceptable) | Only metadata fetches traverse WAN; data cached locally |
| Write-back | <= 200ms | XLD acquisition/revocation latency impacts write performance |
| Cross-cloud typical RTT | 20–100ms (AWS↔GCP/Azure) | Within write-back tolerance for most regions |

---

## Conditional Writes Impact

### CW-001: FSx for ONTAP S3 AP `If-None-Match` Unsupported

| Item | Details |
|------|---------|
| **Finding ID** | CW-001 |
| **Classification** | `supported` (limitation confirmed) |

FSx for ONTAP S3 AP returns `501 Not Implemented` for requests with `If-None-Match` header. This affects Delta Lake, Apache Iceberg, and other table formats that use conditional writes for concurrent commit protection. Workaround: use ONTAP-level locking or application-level coordination.

### CW-002: Conditional Writes and SnapMirror Consistency

| Item | Details |
|------|---------|
| **Finding ID** | CW-002 |
| **Classification** | `supported` (no impact on SnapMirror integrity) |

**Analysis:** The absence of `If-None-Match` does NOT compromise SnapMirror data integrity because:
1. Each S3 API `PutObject` is atomically committed to WAFL
2. ONTAP Snapshots capture crash-consistent state (all committed writes included; in-flight writes excluded)
3. SnapMirror transfers Snapshot content — always consistent
4. Last-writer-wins semantics at the S3 layer do not affect ONTAP-level file system consistency

**Conclusion:** No SnapMirror integrity risk from conditional writes absence.

---

## Cross-Region SnapMirror Validation Findings (2026-07-22)

> Validated: ap-northeast-1 → us-west-2, ONTAP 9.17.1P7D1 both clusters

### SM-VAL-008: FSx API VolumeType:DP Display Lag (Cross-Region)

| Item | Details |
|------|---------|
| **Finding ID** | SM-VAL-008 |
| **Classification** | `works_with_caveats` |
| **Disclosure** | validation evidence |

**Finding:** After SnapMirror break, FSx API continues to report `OntapVolumeType: DP` for the destination volume for **>10 minutes** in cross-region scenarios (previous same-region testing showed ~60s). However, S3 AP attachment succeeds immediately once junction path is set — the check is at the ONTAP level, not the FSx API level.

**Scope clarification:** This lag is FSx-specific (AWS control-plane synchronization delay). On-premises ONTAP does not have this issue as there is no separate control plane layer. The ONTAP REST API correctly reports `type: rw` immediately after break in both scenarios.

**Impact on automation:**
- Do NOT poll `describe-volumes → OntapVolumeType` as the gate for S3 AP attachment
- Instead: (1) Break SnapMirror, (2) Set junction path via `update-volume`, (3) Wait for junction path to appear in FSx API (~2 min), (4) Attach S3 AP immediately

### SM-VAL-009: DP Volume Must Be Created via FSx API for S3 AP Attachment

| Item | Details |
|------|---------|
| **Finding ID** | SM-VAL-009 |
| **Classification** | `works_with_caveats` |
| **Disclosure** | validation evidence |

**Finding:** Volumes created exclusively via ONTAP REST API (`POST /api/storage/volumes {type: dp}`) do NOT appear in the FSx API (`describe-volumes`). S3 AP attachment requires a FSx volume ID (`fsvol-*`). Volumes must be created using `aws fsx create-volume --ontap-configuration '{"OntapVolumeType":"DP"}'` to be visible in both control planes.

**Workaround for existing ONTAP-created volumes:** Delete and recreate the volume via `aws fsx create-volume` with the same name and size. Data must be re-replicated via SnapMirror after recreation. There is no in-place "adoption" of ONTAP-created volumes into the FSx control plane.

### SM-VAL-010: Cross-Region S3 AP Re-Attach RTO

| Item | Details |
|------|---------|
| **Finding ID** | SM-VAL-010 |
| **Classification** | `supported (validated)` |
| **Disclosure** | validation evidence |

**Measured RTO (ap-northeast-1 → us-west-2):**

| Phase | Duration | Notes |
|-------|:--------:|-------|
| SnapMirror break | ~instant | ONTAP REST API PATCH |
| Junction path set + FSx API propagation | ~2 min | `update-volume` + polling |
| S3 AP creation (CREATING → AVAILABLE) | ~30s | `create-and-attach-s3-access-point` |
| First successful S3 API call | ~30s | ListObjectsV2 / GetObject |
| **Total** | **~3 min** | Cross-region. Same-region estimated ~2 min |

**RPO context**: SnapMirror Async replication runs on a schedule (minimum 5-minute intervals for FSx for ONTAP). The RPO is equal to the time since the last successful SnapMirror transfer. In a worst-case scenario, up to 5 minutes of data written to the source after the last transfer could be lost.

**Cross-region data transfer cost note**: SnapMirror transfers between regions incur standard AWS inter-region data transfer charges ($0.01–$0.02/GB depending on regions). Initial baseline transfer of large volumes should be factored into cost estimates. Subsequent incremental transfers are typically much smaller (only changed blocks).

### SM-VAL-011: Teardown Order — Critical Dependency

| Item | Details |
|------|---------|
| **Finding ID** | SM-VAL-011 |
| **Classification** | `works_with_caveats` |
| **Disclosure** | validation evidence |

**Finding:** Deleting VPC Peering or network routes before SVM peer deletion completes causes **permanent orphaned SVM peer records** that cannot be deleted via REST API. The FSx SVM enters MISCONFIGURED state and blocks file system deletion.

**Required teardown order:**
1. Delete SnapMirror relationships (both sides: `destination_only=true` on dest)
2. Delete SVM peers (both sides) — **wait until `num_records: 0` on BOTH clusters**
3. Delete Cluster peers
4. Delete VPC Peering / routes
5. Delete SVM via FSx API
6. Delete File System via FSx API

**Never:** Delete VPC Peering before step 2 is confirmed. The two-phase SVM peer deletion protocol requires bidirectional connectivity.

**Recovery if orphaned:** Use ONTAP CLI via SSH (`sshpass -p <pass> ssh fsxadmin@<mgmt-ip>`).

> **Note**: SSH access to `fsxadmin` must be enabled on the FSx file system (Settings → Administrative Endpoints). For production automation, prefer SSH key-based auth or AWS Systems Manager Session Manager over `sshpass`. Resolution time with AWS Support (if self-recovery fails): typically 1-3 business days.

1. From the **source** cluster: `snapmirror release -destination-path <dest> -source-path <src> -force true` (for each stale destination)
2. From the **source** cluster: `vserver peer delete -vserver <local-svm> -peer-vserver <remote-svm>` (triggers two-phase cleanup on both sides)
3. Retry `aws fsx delete-storage-virtual-machine` — should now succeed
4. Reference: [AWS re:Post — Delete SVM from FSx for ONTAP](https://repost.aws/knowledge-center/fsx-ontap-delete-svm), [FSx User Guide — Can't delete SVM](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/cannot-delete-svm.html)

---

## Version Matrix

| Feature | Minimum ONTAP | Notes |
|---------|:-------------:|-------|
| S3 Access Point (basic) | 9.14.1 | FSx for ONTAP feature |
| S3 NAS bucket (multiprotocol) | 9.12.1 | Underlying ONTAP mechanism |
| S3 NAS bucket on FlexCache Origin | 9.12.1 | Origin volume with S3 AP as FlexCache source |
| S3 NAS bucket on FlexCache Cache | **9.18.1** | Cache Volume S3 AP attachment (FC-002) |
| SnapMirror Async | 9.11.1 | FSx for ONTAP baseline |
| FlexCache (read-only) | 9.5 | Long-standing feature |
| FlexCache write-back | 9.15.1 | Both Origin and Cache |
| FlexCache write-back (recommended) | 9.17.1P1+ | Stability improvements |
| FlexCache Origin/Cache version gap | Within 4 minor | e.g., Cache 9.14.1 → Origin >= 9.10.1 |
| Cluster Peering Encryption | 9.6 | TLS 1.2, default enabled |
| NFSv4.x on FlexCache | 9.10.1 | Both Origin and Cache |
| FlexGroup as FlexCache Origin | 9.13.1 | With constraints |
| GCNV External Replication | Source 9.11.1+ (est.) | GCNV manages destination version |

---

## Recommended Architecture Patterns

### Pattern A: Single-Cloud Data Distribution (FSx for ONTAP cross-region)

- **Use case**: Distribute S3 AP-collected data across AWS regions for low-latency NFS/SMB access
- **Components**: SnapMirror Async for DR + FlexCache for read acceleration
- **Constraints**: SnapMirror Sync unsupported; S3 AP must be newly created at destination

### Pattern B: Hybrid Cloud (FSx for ONTAP to On-premises ONTAP)

- **Use case**: Deliver AWS-collected data to on-premises data centers for existing NFS/SMB clients
- **Components**: Direct Connect/VPN + SnapMirror or FlexCache
- **Constraints**: On-premises ONTAP version compatibility; FlexCache write-back requires RTT <= 200ms

### Pattern C: Multi-Cloud (FSx for ONTAP to GCP/Azure)

- **Use case**: Access AWS-collected data from GCP or Azure workloads
- **GCP options**: GCNV External Replication (SnapMirror), GCNV FlexCache Cache, CVO on GCP
- **Azure options**: CVO on Azure (SnapMirror/FlexCache). ANF is not supported
- **Constraints**: Cross-cloud VPN latency (20-100ms typical); write-around mode recommended

---

## Decision Tree: SnapMirror vs FlexCache

SnapMirror and FlexCache are **complementary technologies suited to different use cases**, not competing approaches.

| Use Case | Recommended | Rationale |
|----------|------------|-----------|
| Disaster Recovery | SnapMirror | Full copy at destination, immediate failover capability |
| Remote read acceleration | FlexCache | Local-speed cache hits, minimal storage consumption |
| Data migration (one-time) | SnapMirror | Full copy then release relationship |
| Remote write (synchronous) | FlexCache (write-around) | Writes forwarded to Origin synchronously. Default mode |
| Remote write (asynchronous) | FlexCache (write-back) | Writes cached locally, flushed to Origin asynchronously (RTT <= 200ms required) |
| DR + daily read acceleration | SnapMirror + FlexCache hybrid | SnapMirror for DR, FlexCache for daily performance |
| Multi-cloud distribution | SnapMirror | More reliable than FlexCache write-back across clouds |

---

## Open Questions

| # | Question | Finding ID | Priority | Resolution Path |
|---|---------|:----------:|:--------:|----------------|
| ~~1~~ | ~~Can Cache Volume have independent S3 AP attachment?~~ | FC-002 | ~~P2~~ | **Resolved**: Supported from ONTAP 9.18.1. Not supported on 9.17.1 (tested). |
| 2 | GCNV External Replication minimum source ONTAP version? | XC-006 | P2 | GCP docs or validation |
| 3 | FlexGroup + S3 AP + FlexCache Origin stability? | FC-007 | P2 | Hands-on validation |
| 4 | ANF alternative path (via CVO on Azure) practicality? | XC-007 | P3 | Architecture + cost eval |

### Resolved in Phase 3

| # | Question | Finding ID | Resolution |
|---|---------|:----------:|-----------|
| ~~1~~ | S3 AP-attached volume as FlexCache Origin? | FC-001 | **Yes** — validated on 9.17.1 |
| ~~2~~ | S3 AP writes + XLD interaction in write-back? | FC-004 | **Works with caveats** — XLD revoke on same-file |
| ~~3~~ | S3 AP attach to destination after SnapMirror break? | SM-005 | **Yes** — break → junction → ~60s → create AP |
| ~~4~~ | `s3_unix` name-mapping regeneration at destination? | SM-002 | **Yes** — FSx auto-manages on AP creation |

---

## Phase 3 Validation Summary

Validated on FSx for ONTAP (ONTAP 9.17.1P7D1, 2nd Generation, Single-AZ, ap-northeast-1).

### Test Case Results

| TC | Scope | Result | Key Finding |
|:--:|-------|:------:|-------------|
| TC-01 | S3 AP + SnapMirror create + transfer | PASS | Volume-level async works with S3 AP volume |
| TC-02 | SnapMirror break + S3 AP re-attach | PASS | ~60s FSx API lag; new AP works immediately after |
| TC-03 | S3 AP + FlexCache Origin | PASS | Cache reads data written via S3 AP |
| TC-04 | FlexCache NFS read verification | PASS | Data integrity confirmed (checksum match) |
| TC-05 | FlexCache write-back + S3 AP | PASS | XLD revoke on same-file; different-file is safe |

### Operational Notes (from validation)

| ID | Finding | Impact |
|:--:|---------|--------|
| FC-VAL-001 | Minimum FlexCache size on FSx for ONTAP: 50GB | Sizing constraint |
| FC-VAL-002 | `use_tiered_aggregate: true` required for FlexCache creation | API parameter |
| FC-VAL-003 | Intra-cluster SVM Peering required for same-cluster FlexCache | Setup requirement |
| FC-VAL-004 | S3 AP write propagates to Cache within ~30s (TTL) | Latency expectation |

### Classification Changes (Phase 2 → Phase 3)

| Finding | Before | After |
|---------|--------|-------|
| SM-002 | undocumented | supported (validated) |
| SM-005 | undocumented | supported (validated) |
| FC-001 | undocumented | supported (validated) |
| FC-004 | undocumented | works_with_caveats |
| SM-VAL-004/007 | (new) | works_with_caveats |

---

## References

### Primary Sources

- [AWS Docs: FSx for ONTAP SnapMirror](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html)
- [AWS Docs: FSx for ONTAP FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html)
- [AWS Docs: FSx for ONTAP S3 Access Points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)
- [NetApp Docs: ONTAP S3 multiprotocol](https://docs.netapp.com/us-en/ontap/s3-multiprotocol/index.html)
- [NetApp Docs: FlexCache supported features](https://docs.netapp.com/us-en/ontap/flexcache/supported-unsupported-features-concept.html)
- [NetApp Docs: FlexCache write-back](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-architecture.html)
- [NetApp Docs: SnapMirror SVM replication](https://docs.netapp.com/us-en/ontap/data-protection/snapmirror-svm-replication-concept.html)
- [NetApp KB: SVM DR of S3 buckets](https://kb.netapp.com/on-prem/ontap/DP/SnapMirror-KBs/Is_SVM_Disaster_Recovery_(SVM_DR)_of_S3_buckets_supported%3F)
- [GCP Docs: GCNV External Replication](https://cloud.google.com/netapp/volumes/docs/protect-data/replicate-ontap/overview)
- [GCP Docs: GCNV FlexCache](https://docs.cloud.google.com/netapp/volumes/docs/configure-and-use/volumes/cache-ontap-volumes/overview)
- [Microsoft Docs: ANF Replication](https://learn.microsoft.com/en-us/azure/azure-netapp-files/replication)

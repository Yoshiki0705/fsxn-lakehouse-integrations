# Feature Request: SVM-DR Support for SVMs with S3 NAS Buckets

> **Finding ID**: SM-004
> **Target**: AWS FSx for ONTAP Product Management + NetApp ONTAP Engineering
> **Priority**: High
> **Date**: 2026-07-21

---

## Use Case Description

Organizations using FSx for ONTAP S3 Access Points to collect data via S3 API need disaster recovery capabilities that include the full SVM configuration (CIFS server, name-mappings, export policies, DNS/LDAP/Kerberos settings). Currently, SVM-DR (SVM-level SnapMirror with `-identity-preserve true`) is the standard mechanism for replicating both data and protocol configuration to a secondary site.

**Workflow being enabled:**
1. Applications write data to FSx for ONTAP via S3 Access Point (Parquet, JSON, CSV)
2. SnapMirror replicates data to a secondary FSx for ONTAP (cross-region or cross-cloud)
3. On failover, the destination SVM provides NFS/SMB access with pre-configured authentication

**Gap:** Step 2 cannot use SVM-DR because the presence of an S3 NAS bucket (required for S3 AP) on the source SVM causes SVM-DR relationship creation to fail.

---

## Impact Description

Without SVM-DR, customers must:
1. Use volume-level SnapMirror (protects data only, not SVM configuration)
2. Manually recreate all SVM protocol configuration at the destination (CIFS server, AD join, name-mappings, export policies, DNS, LDAP)
3. Maintain configuration drift monitoring between source/destination SVM

This increases:
- **RTO**: Manual SVM configuration adds 15-30 minutes to failover procedure
- **Operational complexity**: Dual configuration management required
- **Error risk**: Configuration drift between source and destination SVMs

**Affected architecture patterns:**
- S3 AP data ingestion + SnapMirror cross-region DR (most common pattern)
- Hybrid cloud (FSx for ONTAP → On-premises ONTAP) with S3 AP workloads
- Multi-cloud distribution requiring AD-joined SVMs at destination

---

## Current Workaround

**Volume-level SnapMirror + manual SVM configuration at destination:**

1. Pre-configure destination SVM with matching protocol settings (CIFS, AD join, name-mappings, export policies)
2. Create volume-level SnapMirror relationships for each data volume
3. On failover:
   - Break SnapMirror relationship
   - Set junction path on destination volume
   - Wait ~60s for FSx API `VolumeType` to reflect `RW`
   - Create new S3 Access Point on destination volume (if S3 access also needed)
   - Verify NFS/SMB access with existing SVM configuration

**Workaround limitations:**
- SVM configuration is not automatically synchronized — requires manual/scripted maintenance
- Export policy rules, name-mapping entries, and CIFS shares must be tracked separately
- Failover runbook is more complex than standard SVM-DR procedure

---

## Proposed Behavior

SVM-DR should support SVMs that contain S3 NAS buckets (the underlying mechanism for FSx for ONTAP S3 Access Points).

**Expected behavior after enhancement:**
- SVM-DR relationship creation succeeds for SVMs with `vserver object-store-server` configured
- S3 NAS bucket configuration (object-store-server, policies, users) is replicated to destination SVM
- On SVM-DR activate, destination SVM has all protocol configurations pre-populated
- S3 Access Point remains an AWS-layer construct and must be separately created at destination (this is understood and acceptable)

**Acceptable alternative:** If full S3 NAS bucket replication is architecturally difficult, support SVM-DR with an option to exclude object-store-server resources (replicate everything else: CIFS, name-mappings, export-policies, DNS, etc.) while allowing the SVM to contain S3 NAS buckets.

---

## Reproduction Steps

```bash
# Environment: FSx for ONTAP with ONTAP 9.17.1

# 1. Create source SVM with S3 NAS bucket (via S3 AP attachment)
aws fsx create-and-attach-s3-access-point \
  --name test-ap \
  --type ONTAP \
  --ontap-configuration \
    'VolumeId=fsvol-XXXXXXXXXXXXXXXXX,FileSystemIdentity={Type=UNIX,UnixUser={Name=fsxuser}}'

# 2. Attempt SVM-DR relationship creation (via ONTAP REST API on destination cluster)
# POST /api/snapmirror/relationships
# Body:
# {
#   "source": {"path": "<source-svm>:"},
#   "destination": {"path": "<dest-svm>:"},
#   "policy": {"name": "MirrorAllSnapshots"}
# }

# 3. Expected result: Relationship creation fails with error:
# "A Vserver DR relationship between Vserver [Source SVM] and Vserver [Destination SVM]
#  is not supported because Vserver [Source SVM] contains either an object store server,
#  object store policy, object store user or object store bucket."
```

---

## Environment Information

| Item | Value |
|------|-------|
| ONTAP Version | 9.17.1P7D1 |
| FSx for ONTAP Generation | 2nd Generation (Single-AZ) |
| AWS Region | ap-northeast-1 |
| S3 AP Feature | S3 NAS bucket (multiprotocol) |
| SnapMirror Type Tested | Volume-level Async (works), SVM-DR (fails) |

---

## Supporting Evidence

| Source | Key Statement |
|--------|--------------|
| [NetApp Docs: ONTAP S3 multiprotocol](https://docs.netapp.com/us-en/ontap/s3-multiprotocol/index.html) | "SnapMirror synchronous and SVM disaster recovery are not supported." |
| [NetApp KB: SVM DR of S3 buckets](https://kb.netapp.com/on-prem/ontap/DP/SnapMirror-KBs/Is_SVM_Disaster_Recovery_(SVM_DR)_of_S3_buckets_supported%3F) | Error message confirming the constraint |
| [NetApp Docs: SVM replication concept](https://docs.netapp.com/us-en/ontap/data-protection/snapmirror-svm-replication-concept.html) | "ONTAP S3: Not supported with SVM disaster recovery." |
| [GitHub NetAppDocs/ontap: s3-config interoperability](https://github.com/NetAppDocs/ontap/blob/main/s3-config/ontap-s3-interoperability-concept.adoc) | Interoperability table lists SVM-DR as "Not supported" |
| Phase 3 Validation Evidence | `.private/evidence/s3ap-multicloud/` (internal) |

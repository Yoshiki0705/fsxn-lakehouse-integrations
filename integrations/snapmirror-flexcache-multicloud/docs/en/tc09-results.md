> 🌐 Language: [日本語](../ja/tc09-results.md) | **English**

# TC-09 Results: Lambda → S3 AP → FlexCache Cache Volume (SMB + NFS)

> **Status**: Pending Execution
> **Test Date**: TBD
> **ONTAP Version**: 9.17.1P7D1
> **Environment**: FSx for ONTAP, AD-joined SVMs, intra-cluster FlexCache
> **Test Plan**: [tc09-lambda-s3ap-flexcache-smb-nfs.md](tc09-lambda-s3ap-flexcache-smb-nfs.md)

---

## Summary

| Phase | Description | Result |
|:-----:|-------------|:------:|
| A | Environment Setup (AD, SVM join, FlexCache, SMB share) | ⏳ |
| B | Lambda → S3 AP data ingestion (5+1 files) | ⏳ |
| C | FlexCache NFS read/write verification | ⏳ |
| D | FlexCache SMB read/write verification (AD Kerberos) | ⏳ |
| E | Cross-protocol consistency (NFS ↔ SMB ↔ S3 AP) | ⏳ |

**Overall**: ⏳ Pending

---

## Environment

| Component | Value |
|-----------|-------|
| FSx for ONTAP File System | TBD |
| ONTAP Version | 9.17.1P7D1 |
| Source SVM | TBD (AD-joined) |
| Destination SVM | TBD (AD-joined, same domain) |
| AD Domain | TBD |
| Origin Volume | UNIX security style |
| Cache Volume | UNIX security style (multiprotocol) |
| Lambda Runtime | Python 3.12 (arm64) |
| S3 AP Type | Internet-origin, UNIX FileSystemIdentity |

---

## Phase B: Lambda → S3 AP Ingestion

### Lambda Invocation

```
TBD — paste aws lambda invoke output
```

### S3 AP ListObjectsV2 After Write

```
TBD — paste aws s3api list-objects-v2 output
```

---

## Phase C: NFS Verification (Linux EC2)

### C1: NFS Mount

```
TBD — mount command + output
```

### C2: File Listing

```
TBD — ls -la output
```

### C3: Checksum Comparison

```
TBD — sha256sum output (Cache vs Origin via S3)
```

### C4: NFS Write (write-back)

```
TBD — write command + confirmation
```

### C5: NFS-Written File Visible via S3 AP

```
TBD — aws s3api list-objects-v2 showing nfs-written file
```

---

## Phase D: SMB Verification (Windows EC2, Domain-Joined)

### D1: SMB Map Drive

```
TBD — net use command + output (Kerberos authentication)
```

### D2: File Listing (SMB)

```
TBD — dir Z:\ output
```

### D3: File Content Read (SMB)

```
TBD — Get-Content output
```

### D4: SMB Write

```
TBD — Set-Content command + confirmation
```

### D5: SMB-Written File Visible via S3 AP

```
TBD — aws s3api list-objects-v2 showing smb-written file
```

### D6: SMB-Written File Visible via NFS

```
TBD — cat output from Linux EC2
```

---

## Phase E: Cross-Protocol Consistency

### E1–E3: New S3 AP Write → NFS + SMB Visibility

```
TBD — Lambda invoke → NFS cat → SMB Get-Content (all same file)
```

### E4: Permission/ACL Consistency

```
TBD — ls -la (UNIX) + icacls (NTFS ACL) comparison
```

---

## Findings & Observations

| # | Finding | Category |
|---|---------|----------|
| 1 | TBD | TBD |

---

## Conclusion

TBD — Fill after execution.

---

## Evidence Files

| File | Description |
|------|-------------|
| `.private/evidence/s3ap-multicloud/tc09-step-a-env-setup.md` | Environment setup log |
| `.private/evidence/s3ap-multicloud/tc09-step-b-lambda-invoke.json` | Lambda response |
| `.private/evidence/s3ap-multicloud/tc09-step-c-nfs-verification.txt` | NFS test output |
| `.private/evidence/s3ap-multicloud/tc09-step-d-smb-verification.txt` | SMB test output |
| `.private/evidence/s3ap-multicloud/tc09-step-e-cross-protocol.txt` | Cross-protocol test |

---

## Reproduction

```bash
# Full reproduction steps
# See: docs/tc09-lambda-s3ap-flexcache-smb-nfs.md for detailed test plan
# See: scripts/validation/setup-tc09.sh for automated ONTAP-layer setup
```

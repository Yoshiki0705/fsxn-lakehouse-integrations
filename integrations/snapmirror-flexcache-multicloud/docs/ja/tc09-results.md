> 🌐 Language: **日本語** | [English](../en/tc09-results.md)

# TC-09 Results: Lambda → S3 AP → FlexCache Cache Volume (SMB + NFS)

> **Status**: PASS (All Tests Completed)
> **Test Date**: 2026-07-21
> **ONTAP Version**: 9.17.1P7D1
> **Environment**: FSx for ONTAP (Single-AZ, ap-northeast-1), intra-cluster FlexCache, AD-joined SVM
> **Test Plan**: [tc09-lambda-s3ap-flexcache-smb-nfs.md](../ja/tc09-lambda-s3ap-flexcache-smb-nfs.md)

---

## Summary

| Phase | Description | Result |
|:-----:|-------------|:------:|
| A | Environment Setup (Volume, S3 AP, FlexCache, AD join, CIFS share) | ✅ PASS |
| B | Lambda → S3 AP data ingestion (5 files) | ✅ PASS |
| C | FlexCache NFS read verification | ✅ PASS |
| D | FlexCache SMB read verification (AD Kerberos) | ✅ PASS |
| E | Cross-protocol consistency (NFS ↔ SMB ↔ S3 AP) | ✅ PASS |

**Overall**: ✅ **ALL PASS**

---

## Environment

| Component | Value |
|-----------|-------|
| FSx for ONTAP File System | Single-AZ, ap-northeast-1 |
| ONTAP Version | 9.17.1P7D1 |
| Source SVM | verification-svm (Origin Volume) |
| Destination SVM | svm_dest (AD-joined, CIFS enabled) |
| AD Domain | AWS Managed AD (private domain) |
| Origin Volume | vol_tc09_origin (UNIX style, 10GB) |
| Cache Volume | vol_tc09_cache (FlexGroup, 100GB, write-back enabled) |
| Lambda Runtime | Python 3.12 (arm64) |
| S3 AP | fsxn-tc09-flexcache (UNIX/root, internet-origin) |
| S3 AP Alias | fsxn-tc09-flexca-irbzszsfzi34wu67yx1itq63ry1qnapn1b-ext-s3alias |
| NFS Data LIF | 10.0.12.7 |
| Test Client | i-0ba1bdc87aa8349f3 (Amazon Linux, SSM) |

---

## Phase B: Lambda → S3 AP Ingestion

### Lambda Invocation

```json
{
  "StatusCode": 200,
  "ExecutedVersion": "$LATEST"
}
```

### Lambda Result

```json
{
  "statusCode": 200,
  "written": 5,
  "listed": 5,
  "files": [
    {"key": "demo-data/sensor-001.json", "etag": "\"8dad964d0e8f6643b120018b48795598-1\"", "http_status": 200, "size": 76},
    {"key": "demo-data/sensor-002.json", "etag": "\"1de82c1805c366706a51cbc2366a10d2-1\"", "http_status": 200, "size": 76},
    {"key": "demo-data/sensor-003.json", "etag": "\"86d2555545da1ce1981c1be6e51a1ed8-1\"", "http_status": 200, "size": 76},
    {"key": "demo-data/metrics.csv", "etag": "\"abd1f8b7cd63986e81192a3b936a409b-1\"", "http_status": 200, "size": 70},
    {"key": "demo-data/config.json", "etag": "\"3b337bfd26c7d574c99a471b0812f0f1-1\"", "http_status": 200, "size": 63}
  ],
  "verification": "PASS"
}
```

---

## Phase C: NFS Verification (Linux EC2)

### C1: NFS Mount

```
Filesystem                 Size  Used Avail Use% Mounted on
10.0.12.7:/vol_tc09_cache  9.5G  513M  9.0G   6% /mnt/tc09_cache
```

### C2: File Listing

```
total 24
drwxrwxrwx. 2 root bin  4096 Jul 21 12:29 .
drwxr-xr-x. 4 root root 4096 Jul 21 12:28 ..
-rw-r--r--. 1 root bin    63 Jul 21 12:29 config.json
-rw-r--r--. 1 root bin    70 Jul 21 12:29 metrics.csv
-rw-r--r--. 1 root bin    76 Jul 21 12:28 sensor-001.json
-rw-r--r--. 1 root bin    76 Jul 21 12:29 sensor-002.json
-rw-r--r--. 1 root bin    76 Jul 21 12:29 sensor-003.json
```

### C3: File Content + Checksum

```
{"sensor_id": "S001", "temperature": 23.5, "humidity": 65, "ts": 1784636938}

sha256: 0ed3f3650319cda7ed7e2335c559c36a71e95a7a5e42755033facd70f045fb63
```

---

## Phase D: SMB Verification (smbclient, AD-authenticated)

### D1: SMB Connection + File Listing

```
smbclient //10.0.12.7/tc09_cache -U TC09\Admin -m SMB3

  .                                   D        0  Tue Jul 21 12:29:02 2026
  ..                                  D        0  Tue Jul 21 12:28:59 2026
  sensor-001.json                     A       76  Tue Jul 21 12:28:59 2026
  sensor-002.json                     A       76  Tue Jul 21 12:29:00 2026
  sensor-003.json                     A       76  Tue Jul 21 12:29:01 2026
  metrics.csv                         A       70  Tue Jul 21 12:29:02 2026
  config.json                         A       63  Tue Jul 21 12:29:02 2026

        2490368 blocks of size 4096. 2359192 blocks available
```

### D3: File Content Read (SMB get)

```
getting file \demo-data\sensor-001.json of size 76 as /tmp/smb-sensor.json (14.8 KiloBytes/sec)
{"sensor_id": "S001", "temperature": 23.5, "humidity": 65, "ts": 1784636938}
```

---

## Phase E: Cross-Protocol Consistency

### E1: SMB write → NFS read

```
SMB put: putting file /tmp/smb-write-test.json as \demo-data\smb-written.json (2.4 kb/s)
NFS cat: {"source": "smb-client", "test": "cross-protocol", "ts": 1784637518}
```
**Result: PASS** ✅

### E2: NFS write → SMB read

```
NFS write: echo '{"source": "nfs-client", ...}' > /mnt/tc09_cache/demo-data/nfs-written.json
SMB get: getting file \demo-data\nfs-written.json of size 69 (16.8 KB/sec)
Content: {"source": "nfs-client", "test": "cross-protocol", "ts": 1784637525}
```
**Result: PASS** ✅

### E3: SMB write → S3 AP read (write-back flush)

```
aws s3api get-object --key demo-data/smb-written.json
ContentLength: 69, StorageClass: FSX_ONTAP
Content: {"source": "smb-client", "test": "cross-protocol", "ts": 1784637518}
```
**Result: PASS** ✅ (flush completed within ~60 seconds)

### E4: NFS write → S3 AP read (write-back flush)

```
aws s3api get-object --key demo-data/nfs-written.json
ContentLength: 69, StorageClass: FSX_ONTAP
Content: {"source": "nfs-client", "test": "cross-protocol", "ts": 1784637525}
```
**Result: PASS** ✅ (flush completed within ~60 seconds)

---

## Findings & Observations

| # | Finding | Category |
|---|---------|----------|
| 1 | `use_tiered_aggregate: true` required for FlexCache creation on FSx for ONTAP (FabricPool aggregate) | Operational |
| 2 | FlexCache write-back flush to Origin takes 30-90 seconds (not instant) | Expected behavior |
| 3 | SMB and NFS access the same data on FlexCache Cache Volume — full cross-protocol visibility | Confirmed |
| 4 | S3 AP FileSystemIdentity must use `root` (not `fsxadmin`) on verification-svm | Environment-specific |
| 5 | fsxadmin password resets via FSx API take 30-60 seconds to propagate | Operational |

---

## Conclusion

**Lambda → S3 AP → FlexCache → NFS + SMB** の完全な E2E パイプラインが ONTAP 9.17.1 で動作確認されました。

```
Lambda (S3 API PutObject) → S3 Access Point → Origin Volume (verification-svm)
                                                        │
                                                   FlexCache (intra-cluster)
                                                        │
                                                 Cache Volume (svm_dest)
                                                ┌───────┴───────┐
                                                │               │
                                           NFS read         SMB read
                                         ✅ PASS          ✅ PASS
                                                │               │
                                           NFS write        SMB write
                                         ✅ PASS          ✅ PASS
                                                │               │
                                         ┌──────┴───────────────┘
                                         │ write-back flush (~60s)
                                         ▼
                                    S3 AP read (Origin)
                                         ✅ PASS
```

**Cross-protocol consistency**: NFS で書いたファイルは SMB から見え、SMB で書いたファイルは NFS から見え、どちらも write-back 経由で Origin の S3 AP から読み取り可能。

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

> 🌐 Language: **日本語** | [English](../en/tc09-lambda-s3ap-flexcache-smb-nfs.md)

# TC-09: Lambda → S3 AP Write → FlexCache Cache Volume SMB + NFS Read/Write

> **Status**: Planned
> **Finding Ref**: FC-001, FC-004, AUTH-002, AUTH-003
> **Priority**: P1
> **Environment**: FSx for ONTAP 9.17.1+, AD-joined SVM, intra-cluster (same or cross-cluster)

---

## Test Objective

Validate the complete data flow:

```
Lambda (S3 API) → S3 AP → Origin Volume → FlexCache → Cache Volume → NFS read/write
                                                                    → SMB read/write
```

This proves the architecture pattern: "serverless S3 ingestion + distributed NFS/SMB access via FlexCache" works end-to-end, including AD-authenticated SMB access.

---

## Prerequisites

| Component | Requirement | Template/Script |
|-----------|-------------|----------------|
| FSx for ONTAP Cluster(s) | 9.17.1+ (existing or new) | — |
| AD Environment | AWS Managed AD or Self-Managed | `shared/templates/demo-ad-environment.yaml` |
| Source SVM | AD-joined (CIFS enabled) | `shared/scripts/demo-ad-join-svm.sh` |
| Destination SVM | AD-joined (CIFS enabled, same or trusted domain) | Same script |
| Windows EC2 | For SMB mount verification | UserData DNS + SSM domain join |
| Linux EC2 | For NFS mount verification | Already available or create |
| Lambda Function | Writes test data to S3 AP | Created by this test's template |

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│  VPC (private subnets)                                            │
│                                                                    │
│  ┌──────────┐    S3 API     ┌─────────────────────────────────┐  │
│  │  Lambda  │──────────────▶│ FSx for ONTAP — Source SVM      │  │
│  │ (writer) │   via S3 AP   │ ├── Origin Volume (UNIX style)  │  │
│  └──────────┘               │ ├── S3 AP attached              │  │
│                              │ └── AD-joined (CIFS enabled)    │  │
│                              └──────────────┬──────────────────┘  │
│                                             │ FlexCache           │
│                                             ▼                     │
│                              ┌─────────────────────────────────┐  │
│                              │ FSx for ONTAP — Dest SVM        │  │
│                              │ ├── Cache Volume                 │  │
│  ┌──────────┐    NFS mount   │ ├── NFS export (AUTH_SYS)       │  │
│  │ Linux EC2│◀──────────────│ ├── SMB share (AD Kerberos)     │  │
│  └──────────┘               │ └── AD-joined (same domain)     │  │
│                              └─────────────────────────────────┘  │
│  ┌──────────┐    SMB mount                                        │
│  │Windows EC│◀────────────────────────────────────────────────┘  │
│  │(domain)  │                                                     │
│  └──────────┘                                                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Test Steps

### Phase A: Environment Setup

| Step | Action | Verification |
|:----:|--------|-------------|
| A1 | Deploy AD environment (if not existing) | `demo-ad-environment.yaml` stack active |
| A2 | AD-join source SVM | `cifs show` returns domain-joined status |
| A3 | AD-join destination SVM (same domain) | `cifs show` returns domain-joined status |
| A4 | Create test Origin Volume (UNIX style, 10GB) on source SVM | Volume online, junction path set |
| A5 | Attach S3 AP to Origin Volume (UNIX FileSystemIdentity) | S3 AP status: AVAILABLE |
| A6 | Create SVM Peering (source ↔ dest, applications: flexcache) | Peering active |
| A7 | Create FlexCache Cache Volume (Origin = S3 AP vol) | Cache Volume online |
| A8 | Create SMB share on Cache Volume (CIFS share) | Share visible via `net view` |
| A9 | Configure NFS export policy on Cache Volume | Export policy allows client subnet |
| A10 | Deploy Lambda writer function | Lambda function active |
| A11 | Deploy/confirm Linux EC2 (NFS client) | SSM online, can mount |
| A12 | Deploy/confirm Windows EC2 (SMB client, domain-joined) | Domain-joined, SMB accessible |

### Phase B: S3 AP Data Ingestion via Lambda

| Step | Action | Verification |
|:----:|--------|-------------|
| B1 | Invoke Lambda — write 5 test files (Parquet, JSON, CSV) to S3 AP | Lambda returns 200, ListObjectsV2 shows 5 objects |
| B2 | Wait 30-60s for FlexCache TTL propagation | — |
| B3 | Invoke Lambda — write 1 additional file (incremental) | Lambda returns 200 |

### Phase C: FlexCache NFS Verification (Linux EC2)

| Step | Action | Verification |
|:----:|--------|-------------|
| C1 | NFS mount Cache Volume | `mount -t nfs <data-lif>:/<cache-vol> /mnt/cache` succeeds |
| C2 | List files — all 6 files visible | `ls -la` shows all 5 + 1 incremental |
| C3 | Read file content — checksum matches Origin | `sha256sum` comparison |
| C4 | Write new file via NFS on Cache (write-back test) | `echo "nfs-write" > /mnt/cache/nfs-written.txt` succeeds |
| C5 | Verify NFS-written file visible on Origin (via S3 AP ListObjectsV2) | Object appears in S3 listing |

### Phase D: FlexCache SMB Verification (Windows EC2)

| Step | Action | Verification |
|:----:|--------|-------------|
| D1 | SMB map drive to Cache Volume share | `net use Z: \\<cifs-name>\<share>` succeeds (Kerberos auth) |
| D2 | List files — all files visible (including NFS-written) | `dir Z:\` shows all files |
| D3 | Read file content — matches expected content | `Get-Content Z:\sensor-001.json` matches |
| D4 | Write new file via SMB on Cache | `Set-Content Z:\smb-written.txt "smb-write"` succeeds |
| D5 | Verify SMB-written file visible on Origin (via S3 AP ListObjectsV2) | Object appears in S3 listing |
| D6 | Verify SMB-written file visible via NFS (Linux EC2) | `cat /mnt/cache/smb-written.txt` shows content |

### Phase E: Cross-Protocol Consistency

| Step | Action | Verification |
|:----:|--------|-------------|
| E1 | Lambda writes new file via S3 AP to Origin | Lambda returns 200 |
| E2 | Verify new file visible via NFS (after TTL) | `ls` + `cat` on Linux EC2 |
| E3 | Verify new file visible via SMB (after TTL) | `dir` + `Get-Content` on Windows EC2 |
| E4 | Check NTFS ACL / UNIX perms consistency | `icacls` on Windows, `ls -la` on Linux |

### Phase F: Rollback

| Step | Action |
|:----:|--------|
| F1 | Unmount NFS / disconnect SMB drive |
| F2 | Delete FlexCache Cache Volume |
| F3 | Delete SVM Peering |
| F4 | Detach + delete S3 AP |
| F5 | Delete Origin test volume |
| F6 | (Optional) Delete Lambda stack |

---

## Expected Results

| Test Area | Expected Outcome |
|-----------|-----------------|
| Lambda → S3 AP → Origin | Standard S3 PutObject succeeds |
| FlexCache NFS read (Phase C) | Data matches Origin within TTL (~30s) |
| FlexCache SMB read (Phase D) | Data accessible via AD-authenticated Kerberos session |
| NFS write-back → Origin propagation | File appears in S3 AP ListObjectsV2 |
| SMB write-back → Origin propagation | File appears in S3 AP ListObjectsV2 |
| Cross-protocol visibility | NFS writes visible via SMB; SMB writes visible via NFS |

---

## Evidence Capture Plan

All logs and API responses will be saved to:
- **Public (GitHub)**: `integrations/snapmirror-flexcache-multicloud/docs/tc09-results.md`
- **Private (raw logs)**: `.private/evidence/s3ap-multicloud/tc09-*`

| Evidence File | Content |
|--------------|---------|
| `tc09-step-a-env-setup.md` | Environment creation log (sanitized) |
| `tc09-step-b-lambda-invoke.json` | Lambda invocation response + S3 listing |
| `tc09-step-c-nfs-verification.txt` | NFS mount, ls, cat, checksum, write output |
| `tc09-step-d-smb-verification.txt` | SMB net use, dir, Get-Content, write output |
| `tc09-step-e-cross-protocol.txt` | Cross-protocol visibility verification |
| `tc09-results.md` | **Public summary** (GitHub page) with sanitized logs |

---

## Volume Configuration Requirements

| Volume | Style | Why |
|--------|:-----:|-----|
| Origin Volume | UNIX | S3 AP FileSystemIdentity=UNIX works correctly; NFS is native |
| Cache Volume | UNIX (recommended) | Multiprotocol access; name-mapping handles win→unix for SMB |

**UNIX style + name-mapping** is preferred because:
- S3 AP uses UNIX identity (FileSystemIdentity Type=UNIX)
- FlexCache preserves security style from Origin
- SMB access works via win→unix name-mapping (AD user → UNIX UID)
- Avoids NTFS-only complications where name-mapping deny patterns don't apply

---

## SMB Share Creation on Cache Volume (ONTAP REST API)

```bash
# Create CIFS share on Cache Volume
POST /api/protocols/cifs/shares
{
  "svm": {"name": "<dest-svm>"},
  "name": "tc09_cache_share",
  "path": "/<cache-vol-junction-path>",
  "comment": "TC-09 FlexCache SMB verification",
  "acls": [
    {"user_or_group": "Everyone", "permission": "full_control"}
  ]
}
```

---

## Lambda Writer Function

Minimal Python Lambda that writes test data via S3 AP:

```python
import boto3
import json
import time

def handler(event, context):
    s3 = boto3.client('s3')
    ap_alias = event.get('ap_alias')  # S3 AP alias
    prefix = event.get('prefix', 'test-data')

    files = {
        f'{prefix}/sensor-001.json': json.dumps({"sensor": "S001", "temp": 23.5, "ts": int(time.time())}),
        f'{prefix}/sensor-002.json': json.dumps({"sensor": "S002", "temp": 24.1, "ts": int(time.time())}),
        f'{prefix}/metrics.csv': "id,value,ts\n1,100,{}\n2,200,{}".format(int(time.time()), int(time.time())),
        f'{prefix}/events.parquet': b'PAR1...',  # minimal parquet header for test
        f'{prefix}/config.json': json.dumps({"version": "1.0", "test": "tc09"}),
    }

    results = []
    for key, body in files.items():
        resp = s3.put_object(Bucket=ap_alias, Key=key, Body=body)
        results.append({"key": key, "etag": resp['ETag'], "status": resp['ResponseMetadata']['HTTPStatusCode']})

    return {"statusCode": 200, "files_written": len(results), "results": results}
```

---

## Deployment Order

```bash
# 1. AD Environment (if not existing)
aws cloudformation create-stack --stack-name tc09-ad-env \
  --template-body file://shared/templates/demo-ad-environment.yaml \
  --parameters file://cfn-params/tc09-ad.json \
  --capabilities CAPABILITY_NAMED_IAM

# 2. AD-join SVMs
./shared/scripts/demo-ad-join-svm.sh --svm-id <source-svm-id> --ad-stack-name tc09-ad-env
./shared/scripts/demo-ad-join-svm.sh --svm-id <dest-svm-id> --ad-stack-name tc09-ad-env

# 3. Deploy Lambda + test resources
aws cloudformation create-stack --stack-name tc09-lambda-flexcache \
  --template-body file://integrations/snapmirror-flexcache-multicloud/template-tc09.yaml \
  --parameters file://cfn-params/tc09-lambda-flexcache.json \
  --capabilities CAPABILITY_NAMED_IAM

# 4. Run ONTAP-layer setup (FlexCache, CIFS share, export policy)
./integrations/snapmirror-flexcache-multicloud/scripts/validation/setup-tc09.sh

# 5. Execute test
./integrations/snapmirror-flexcache-multicloud/scripts/validation/run-tc09.sh

# 6. Teardown
./integrations/snapmirror-flexcache-multicloud/scripts/validation/teardown-tc09.sh
aws cloudformation delete-stack --stack-name tc09-lambda-flexcache
```

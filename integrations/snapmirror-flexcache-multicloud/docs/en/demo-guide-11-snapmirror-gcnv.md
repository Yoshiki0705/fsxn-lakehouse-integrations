> 🌐 Language: [日本語](../ja/demo-guide-11-snapmirror-gcnv.md) | **English**

# Demo Guide 11: SnapMirror GCNV (FSx for ONTAP → Google Cloud NetApp Volumes)

> **Time Required**: ~90min(if VPN already configured)
> **Cost**: ~$15–25（AWS + GCP combined, if deleted after verification）
> **Audience**: engineers exploring AWS → GCP data replication
> **ONTAP Version**: FSx 9.17.1+ / GCNV（Google-managed、External Replication 対応）

---

## What This Demo Validates

```
AWS Cloud (ap-northeast-1)                  Google Cloud (us-central1)
┌────────────────────────────┐              ┌────────────────────────────┐
│  Lambda ──S3 API──▶ S3 AP  │              │                            │
│        │                   │              │  Google Cloud NetApp       │
│        ▼                   │  HA VPN      │  Volumes (GCNV)            │
│   Source Volume            │═════════════▶│    External Replication    │
│   (FSx for ONTAP)         │  SnapMirror  │    Destination Volume      │
│                            │  (External   │          │                 │
│                            │   Repl.)     │    NFS mount               │
│                            │              │   (GCE instance)           │
└────────────────────────────┘              └────────────────────────────┘

GCNV の External Replication:
  - Google-managed SnapMirror-compatible replication
  - GCNV manages the Destination Volume
  - After break, operates independently as GCNV Volume
```

```mermaid
flowchart LR
    subgraph AWS["AWS Cloud"]
        Lambda["Lambda"]
        S3AP["S3 AP"]
        Source["Source Volume\n(FSx for ONTAP)"]
    end
    subgraph GCP["Google Cloud"]
        GCNV["GCNV Volume\n(External Replication)"]
        GCE["GCE Instance\n(NFSv3)"]
    end

    Lambda -->|"S3 API"| S3AP --> Source
    Source ===|"SnapMirror\n(External Repl.)\nHA VPN"| GCNV
    GCNV -->|"break → RW\nNFSv3"| GCE
```


**Validation Points:**

| # | Validation Item | Action |
|:-:|---------|------|
| 1 | Write data via S3 AP on AWS | Lambda → S3 AP |
| 2 | GCNV External Replication のVerify | gcloud / GCP Console |
| 3 | Replication break 後の NFS アクセス | NFSv3 |

---

## Prerequisites

[Common Prerequisites](../en/demo-guide-00-prerequisites.md) plus the following:

| Resource | Cloud | Description |
|----------|---------|------|
| FSx for ONTAP | AWS | Source Volume + S3 AP |
| GCNV Storage Pool | GCP | Destination Volume |
| HA VPN | AWS ↔ GCP | Intercluster communication |
| GCP VPC (PSA 有効) | GCP | for GCNV connectivity |

### GCNV External Replication Characteristics

| Item | Details |
|------|------|
| Admin | Google (GCNV manages Destination) |
| Source Requirement | FSx for ONTAP の Intercluster LIF reachable from GCNV |
| Protocol | SnapMirror-compatible (GCNV internal implementation) |
| After break | independent operation as GCNV Volume (NFS access) |
| Constraint | NFSv3 only |

---

## Step 0: Set Environment Variables

```bash
# === AWS Side ===
export AWS_REGION="ap-northeast-1"
export FS_ID="fs-0EXAMPLE1234abcde"
export SVM_NAME_AWS="svm-source"
export SECRET_ARN="arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:fsxn-admin-XXXXXX"

# === GCP Side ===
export GCP_PROJECT="my-project-123456"
export GCP_REGION="us-central1"
export GCP_ZONE="us-central1-a"
export GCP_VPC="gcnv-vpc"

# === Common ===
export SOURCE_VOL="vol_sm_gcnv_src"
export S3AP_NAME="fsxn-sm-gcnv"
```

---

## Step 1: VPN 設定

> [Demo Guide 04 Step 1](../en/demo-guide-04-flexcache-cvo-gcp.md#step-1-gcp-ha-vpn-の作成) の HA VPN 設定. Refer to this guide.

---

## Step 2: Source Volume + S3 AP + Lambda Writer（AWS  side）

> [Demo Guide 01 Step 4-6](../en/demo-guide-01-flexcache-same-region.md#step-4-origin-volume-作成--s3-ap-アタッチ) . Refer to this guide.

---

## Step 3: Get FSx for ONTAP Intercluster LIF Information

Intercluster LIF information from FSx for ONTAP is needed to configure GCNV External Replication.

```bash
MGMT_IP=$(aws fsx describe-file-systems --file-system-ids "$FS_ID" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
  --output text --region "$AWS_REGION")

CREDS=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" \
  --query SecretString --output text --region "$AWS_REGION")
ONTAP_USER=$(echo "$CREDS" | jq -r '.username')
ONTAP_PASS=$(echo "$CREDS" | jq -r '.password')

# Intercluster LIF
IC_LIFS=$(curl -sk -u "${ONTAP_USER}:${ONTAP_PASS}" \
  "https://${MGMT_IP}/api/network/ip/interfaces?services=intercluster_core&fields=ip.address" \
  | jq -r '.records[].ip.address')
echo "FSx Intercluster LIFs: $IC_LIFS"

# Cluster Name (Peer に使用)
CLUSTER_NAME=$(curl -sk -u "${ONTAP_USER}:${ONTAP_PASS}" \
  "https://${MGMT_IP}/api/cluster" | jq -r '.name')
echo "Cluster Name: $CLUSTER_NAME"

# SVM UUID
SVM_UUID=$(curl -sk -u "${ONTAP_USER}:${ONTAP_PASS}" \
  "https://${MGMT_IP}/api/svm/svms?name=${SVM_NAME_AWS}" | jq -r '.records[0].uuid')
echo "SVM UUID: $SVM_UUID"
```

---

## Step 4: GCNV External Replication Volume の作成

GCNV の External Replication は GCP Console または `gcloud` CLI から設定します。

```bash
# GCNV Storage Pool 作成（まだない場合）
gcloud netapp storage-pools create gcnv-repl-pool \
  --location "$GCP_REGION" \
  --capacity 2048 \
  --service-level PREMIUM \
  --network "$GCP_VPC" \
  --project "$GCP_PROJECT"

# External Replication Volume の作成
# ※ gcloud netapp volumes create with replication source 設定
# Specific parameters depend on the GCNV External Replication GA status

gcloud netapp volumes create gcnv-repl-dest \
  --location "$GCP_REGION" \
  --capacity 1024 \
  --storage-pool gcnv-repl-pool \
  --protocols NFSv3 \
  --share-name gcnv_repl \
  --project "$GCP_PROJECT"

# External Replication の設定（GCP Console 経由を推奨）
# Source: FSx for ONTAP Cluster IP + SVM Name + Volume Name
# Intercluster LIFs: $IC_LIFS
# Replication Schedule: hourly / daily / custom
```

> **Note**: GCNV External Replication の具体的な CLI パラメータは Google Cloud のリリース状況により変動します。最新 procedureは GCP Console の NetApp Volumes > Volumes > Create Volume > External Replication セクションをrefer to this guideしてください。

---

## Step 5: Replication 状態のVerify

```bash
# GCNV Volume のレプリケーション status verified
gcloud netapp volumes describe gcnv-repl-dest \
  --location "$GCP_REGION" \
  --project "$GCP_PROJECT" \
  --format='yaml(replicationStatus, dataProtection)'
```

**Expectedされる出力例:**
```yaml
replicationStatus: MIRRORED
dataProtection:
  replication:
    mirrorState: MIRRORED
    healthy: true
```

---

## Step 6: Replication Break + NFS アクセス

```bash
# Break Replication (GCP Console or gcloud)
gcloud netapp volumes replications stop gcnv-repl-dest \
  --location "$GCP_REGION" \
  --project "$GCP_PROJECT"

# Break Complete待ち
sleep 30

gcloud netapp volumes describe gcnv-repl-dest \
  --location "$GCP_REGION" \
  --project "$GCP_PROJECT" \
  --format='value(replicationStatus)'
# Expected: STOPPED or BROKEN_OFF
```

```bash
# GCE インスタンスから NFS Mount
gcloud compute ssh gcnv-test-vm --zone "$GCP_ZONE" --project "$GCP_PROJECT"

# GCNV Mount Target の取得
GCNV_MOUNT=$(gcloud netapp volumes describe gcnv-repl-dest \
  --location "$GCP_REGION" --project "$GCP_PROJECT" \
  --format='value(mountOptions.export)')

sudo mkdir -p /mnt/gcnv_repl
sudo mount -t nfs -o vers=3,hard ${GCNV_MOUNT}:/gcnv_repl /mnt/gcnv_repl

# Verify data
ls -la /mnt/gcnv_repl/demo-data/
cat /mnt/gcnv_repl/demo-data/sensor-001.json | jq .
```

**Expected Output:**
```json
{
  "sensor_id": "S001",
  "temperature": 23.5,
  "humidity": 65,
  "ts": 1753090800
}
```

---

## Cleanup

```bash
# 1. GCE: NFS unmount
sudo umount /mnt/gcnv_repl

# 2. GCNV Replication 削除 + Volume 削除
gcloud netapp volumes delete gcnv-repl-dest \
  --location "$GCP_REGION" --project "$GCP_PROJECT" --quiet

# 3. Delete GCNV Storage Pool
gcloud netapp storage-pools delete gcnv-repl-pool \
  --location "$GCP_REGION" --project "$GCP_PROJECT" --quiet

# 4. VPN 削除（Demo Guide 04 refer to this guide）
# 5. AWS side: S3 AP + Volume + Lambda 削除（Demo Guide 01 refer to this guide）
```

---

## Troubleshooting

| Symptom | Cause | Resolution |
|------|------|------|
| External Replication 作成失敗 | IC LIF が GCNV から到達Not available | VPN + Firewall + ルーティングVerify |
| Replication が "INITIALIZING" のまま | Initial transfer in progress (depends on data volume) | A few minutes for 10GB. More time needed for large data |
| NFS mount: "access denied" | GCNV Volume export policy | GCP Console で allowed-clients をVerify |
| NFSv4 指定でエラー | GCNV only supports NFSv3 | `-o vers=3`  flag |
| After breakに書き込めない | GCNV Volume configuration | After breakは RW Volume。export policy をVerify |

---

## GCNV External Replication vs CVO SnapMirror の選び方

| Aspect | GCNV External Replication | CVO on GCP SnapMirror |
|------|:---:|:---:|
| Ease of management | ✅ Google-managed | △ Self-managed |
| Cost | ✅ GCNV pricing only | △ CVO license + VM cost |
| Write-back 対応 | ❌ Not available | ✅ FlexCache 経由で可能 |
| SMB 対応 | ❌ NFSv3 のみ | ✅ NFS + SMB |
| ONTAP CLI/API アクセス | ❌ Not available | ✅ Full access |
| FlexCache 併用 | ❌ Not available | ✅ 可能 |

**Selection Guide:**
- **Read-only で十分 + 管理Cost最小化** → GCNV External Replication
- **Write-back / SMB / full ONTAP features needed** → CVO on GCP

---

## References

- [GCP Docs: NetApp Volumes](https://cloud.google.com/netapp/volumes/docs)
- [GCP Docs: NetApp Volumes Replication](https://cloud.google.com/netapp/volumes/docs/configure-and-use/data-replication)
- [Demo Guide 06: FlexCache GCNV](../en/demo-guide-06-flexcache-gcnv.md)
- [Demo Guide 04: FlexCache CVO on GCP](../en/demo-guide-04-flexcache-cvo-gcp.md)（VPN 手順）
- [Demo Guide 01: FlexCache 同一リージョン](../en/demo-guide-01-flexcache-same-region.md)（Lambda Writer 手順）

> 🌐 Language: [日本語](../ja/demo-guide-02-flexcache-cross-region.md) | **English**

# Demo Guide 02: FlexCache Cross-Region (Region A → Region B)

> **Time Required**: ~60min(if FSx for ONTAP deployed in both regions)
> **Cost**: ~$15–20(if deleted after verification, VPC Peering + 2x FSx for ONTAP)
> **Audience**: infra/data engineers exploring multi-region architectures
> **ONTAP Version**: 9.17.1+(FlexCache write-back capable)

---

> ✅ **Validation Status**: E2E validated (2026-07-22). Cluster Peering + SVM Peering + FlexCache + NFS read confirmed.
> Data propagation: <3 seconds (ap-northeast-1 → us-west-2).
> Script: `scripts/validation/cross-region-deploy.sh` + `cross-region-test.sh`

## What This Demo Validates

```
Region A (ap-northeast-1)                    Region B (us-west-2)
┌──────────────────────────┐                ┌──────────────────────────┐
│  Lambda ──S3 API──▶ S3 AP │                │                          │
│        │                  │                │     FlexCache Cache      │
│        ▼                  │   VPC Peering  │        Volume            │
│   Origin Volume           │◄══════════════▶│          │               │
│   (FSx for ONTAP A)      │  Intercluster  │   ┌──────┴──────┐       │
│                           │                │   NFS mount   SMB mount  │
│                           │                │  (Linux EC2) (Win EC2)   │
└──────────────────────────┘                └──────────────────────────┘
```

```mermaid
flowchart LR
    subgraph RegionA["Region A (ap-northeast-1)"]
        Lambda["Lambda"]
        S3AP["S3 AP"]
        Origin["Origin Volume\n(FSx for ONTAP A)"]
    end
    subgraph RegionB["Region B (us-west-2)"]
        Cache["FlexCache Cache\n(FSx for ONTAP B)"]
        NFS["NFS Client"]
    end

    Lambda -->|"S3 API"| S3AP --> Origin
    Origin ===|"FlexCache\nVPC Peering"| Cache
    Cache --> NFS
```


**Validation Points:**

| # | Validation Item | Protocol |
|:-:|---------|-----------|
| 1 | Lambda writes data to Origin via S3 AP in Region A | S3 |
| 2 | FlexCache in Region B is readable via NFS mount | NFS |
| 3 | Cache write in Region B → reflected in Region A Origin | NFS write-back |
| 4 | Cross-region RTT latency impact measurement | ICMP/NFS |

---

## Prerequisites

[Common Prerequisites](../en/demo-guide-00-prerequisites.md) plus the following:

| Resource | Region | Description |
|----------|-----------|------|
| FSx for ONTAP A | ap-northeast-1 | hosts Origin Volume |
| FSx for ONTAP B | us-west-2 | hosts Cache Volume |
| VPC A + Private Subnets | ap-northeast-1 | Same VPC as FSx A |
| VPC B + Private Subnets | us-west-2 | Same VPC as FSx B |
| VPC Peering 接続 | Both regions | CIDR must not overlap |

> **Lambda Writer Setup**: Step 5-6 は [Demo Guide 01](../en/demo-guide-01-flexcache-same-region.md)  — identical procedure.Skip if Lambda function is already deployed.

---

## Step 0: Set Environment Variables

```bash
# === Region A (Origin Side) ===
export REGION_A="ap-northeast-1"
export FS_ID_A="fs-0EXAMPLE1111aaaaa"
export SVM_NAME_A="svm-origin"
export SECRET_ARN_A="arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:fsxn-admin-A-XXXXXX"
export VPC_ID_A="vpc-0aaaa1111"
export VPC_CIDR_A="10.0.0.0/16"

# === Region B (Cache Side) ===
export REGION_B="us-west-2"
export FS_ID_B="fs-0EXAMPLE2222bbbbb"
export SVM_NAME_B="svm-cache"
export SECRET_ARN_B="arn:aws:secretsmanager:us-west-2:123456789012:secret:fsxn-admin-B-XXXXXX"
export VPC_ID_B="vpc-0bbbb2222"
export VPC_CIDR_B="10.1.0.0/16"

# === Common ===
export ORIGIN_VOL="vol_cross_origin"
export CACHE_VOL="vol_cross_cache"
export S3AP_NAME="fsxn-cross-region-demo"
```

---

## Step 1: Create VPC Peering

```bash
# Request VPC Peering connection (Region A → Region B)
PEERING_ID=$(aws ec2 create-vpc-peering-connection \
  --vpc-id "$VPC_ID_A" \
  --peer-vpc-id "$VPC_ID_B" \
  --peer-region "$REGION_B" \
  --region "$REGION_A" \
  --query 'VpcPeeringConnection.VpcPeeringConnectionId' \
  --output text)
echo "Peering ID: $PEERING_ID"
```

**Expected Output:**
```
Peering ID: pcx-0abcdef1234567890
```

```bash
# Accept Peering in Region B
aws ec2 accept-vpc-peering-connection \
  --vpc-peering-connection-id "$PEERING_ID" \
  --region "$REGION_B" | jq '.VpcPeeringConnection.Status'
```

**Expected Output:**
```json
{
  "Code": "active",
  "Message": "Active"
}
```

```bash
# Add peering route to Route Table (Region A → Region B CIDR)
RT_A=$(aws ec2 describe-route-tables \
  --filters Name=vpc-id,Values="$VPC_ID_A" Name=association.main,Values=true \
  --query 'RouteTables[0].RouteTableId' --output text --region "$REGION_A")

aws ec2 create-route \
  --route-table-id "$RT_A" \
  --destination-cidr-block "$VPC_CIDR_B" \
  --vpc-peering-connection-id "$PEERING_ID" \
  --region "$REGION_A"

# Add peering route to Route Table (Region B → Region A CIDR)
RT_B=$(aws ec2 describe-route-tables \
  --filters Name=vpc-id,Values="$VPC_ID_B" Name=association.main,Values=true \
  --query 'RouteTables[0].RouteTableId' --output text --region "$REGION_B")

aws ec2 create-route \
  --route-table-id "$RT_B" \
  --destination-cidr-block "$VPC_CIDR_A" \
  --vpc-peering-connection-id "$PEERING_ID" \
  --region "$REGION_B"
```

```bash
# Security Group to allow access from peer region
# Region A: Region B  Intercluster communication
SG_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
  --query 'FileSystems[0].SubnetIds[0]' --output text --region "$REGION_A")

aws ec2 authorize-security-group-ingress \
  --group-id "sg-0EXAMPLE_FSX_A" \
  --protocol tcp --port 11104-11105 \
  --cidr "$VPC_CIDR_B" --region "$REGION_A"

# Region B: Region A  Intercluster communication
aws ec2 authorize-security-group-ingress \
  --group-id "sg-0EXAMPLE_FSX_B" \
  --protocol tcp --port 11104-11105 \
  --cidr "$VPC_CIDR_A" --region "$REGION_B"
```

---

## Step 2: Create Cluster Peering

```bash
# Region A  Intercluster LIF IPs
MGMT_IP_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
  --output text --region "$REGION_A")

CREDS_A=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN_A" \
  --query SecretString --output text --region "$REGION_A")
USER_A=$(echo "$CREDS_A" | jq -r '.username')
PASS_A=$(echo "$CREDS_A" | jq -r '.password')

IC_LIFS_A=$(curl -sk -u "${USER_A}:${PASS_A}" \
  "https://${MGMT_IP_A}/api/network/ip/interfaces?services=intercluster_core&fields=ip.address" \
  | jq -r '[.records[].ip.address] | join(",")')
echo "Region A Intercluster LIFs: $IC_LIFS_A"

# Region B  Intercluster LIF IPs
MGMT_IP_B=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_B" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
  --output text --region "$REGION_B")

CREDS_B=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN_B" \
  --query SecretString --output text --region "$REGION_B")
USER_B=$(echo "$CREDS_B" | jq -r '.username')
PASS_B=$(echo "$CREDS_B" | jq -r '.password')

IC_LIFS_B=$(curl -sk -u "${USER_B}:${PASS_B}" \
  "https://${MGMT_IP_B}/api/network/ip/interfaces?services=intercluster_core&fields=ip.address" \
  | jq -r '[.records[].ip.address] | join(",")')
echo "Region B Intercluster LIFs: $IC_LIFS_B"
```

```bash
# Create Cluster Peer from Region A
curl -sk -u "${USER_A}:${PASS_A}" \
  -X POST "https://${MGMT_IP_A}/api/cluster/peers" \
  -H "Content-Type: application/json" \
  -d "{
    \"remote\": {\"ip_addresses\": [$(echo $IC_LIFS_B | sed 's/,/\",\"/g' | sed 's/^/\"/;s/$/\"/')]}
    \"authentication\": {\"passphrase\": \"cross-region-demo-2026\"},
    \"encryption\": {\"proposed\": \"tls_psk\"}
  }" | jq '{job: .job.uuid}'
```

```bash
# Accept Cluster Peer from Region B
curl -sk -u "${USER_B}:${PASS_B}" \
  -X POST "https://${MGMT_IP_B}/api/cluster/peers" \
  -H "Content-Type: application/json" \
  -d "{
    \"remote\": {\"ip_addresses\": [$(echo $IC_LIFS_A | sed 's/,/\",\"/g' | sed 's/^/\"/;s/$/\"/')]}
    \"authentication\": {\"passphrase\": \"cross-region-demo-2026\"}
  }" | jq '{job: .job.uuid}'
```

```bash
# Cluster Peer  status verified
sleep 15
curl -sk -u "${USER_A}:${PASS_A}" \
  "https://${MGMT_IP_A}/api/cluster/peers?fields=status" \
  | jq '.records[] | {name, status: .status.state}'
```

**Expected Output:**
```json
{
  "name": "Clus_xxxx",
  "status": "available"
}
```

---

## Step 3: Create SVM Peering

```bash
# Get SVM UUID
SVM_UUID_A=$(curl -sk -u "${USER_A}:${PASS_A}" \
  "https://${MGMT_IP_A}/api/svm/svms?name=${SVM_NAME_A}" \
  | jq -r '.records[0].uuid')

SVM_UUID_B=$(curl -sk -u "${USER_B}:${PASS_B}" \
  "https://${MGMT_IP_B}/api/svm/svms?name=${SVM_NAME_B}" \
  | jq -r '.records[0].uuid')

# Region A  create SVM Peer
PEER_CLUSTER_NAME=$(curl -sk -u "${USER_A}:${PASS_A}" \
  "https://${MGMT_IP_A}/api/cluster/peers" \
  | jq -r '.records[0].name')

curl -sk -u "${USER_A}:${PASS_A}" \
  -X POST "https://${MGMT_IP_A}/api/svm/peers" \
  -H "Content-Type: application/json" \
  -d "{
    \"svm\": {\"name\": \"${SVM_NAME_A}\"},
    \"peer\": {
      \"svm\": {\"name\": \"${SVM_NAME_B}\"},
      \"cluster\": {\"name\": \"${PEER_CLUSTER_NAME}\"}
    },
    \"applications\": [\"flexcache\"]
  }" | jq '{job: .job.uuid}'
```

```bash
# Region B  accept SVM Peer (skip if auto-accepted)
sleep 10
curl -sk -u "${USER_B}:${PASS_B}" \
  "https://${MGMT_IP_B}/api/svm/peers?fields=state" \
  | jq '.records[] | {svm: .svm.name, peer_svm: .peer.svm.name, state}'
```

**Expected Output:**
```json
{
  "svm": "svm-cache",
  "peer_svm": "svm-origin",
  "state": "peered"
}
```

---

## Step 4: Create Origin Volume + Attach S3 AP (Region A)

> This procedure is  [Demo Guide 01 Step 4](../en/demo-guide-01-flexcache-same-region.md#step-4-origin-volume-作成--s3-ap-アタッチ)  — identical procedure.

```bash
# Create Origin Volume
curl -sk -u "${USER_A}:${PASS_A}" \
  -X POST "https://${MGMT_IP_A}/api/storage/volumes" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"${ORIGIN_VOL}\",
    \"svm\": {\"name\": \"${SVM_NAME_A}\"},
    \"size\": 10737418240,
    \"nas\": {\"path\": \"/${ORIGIN_VOL}\", \"security_style\": \"unix\", \"unix_permissions\": \"0777\"},
    \"guarantee\": {\"type\": \"none\"}
  }" | jq '{job: .job.uuid}'

sleep 10

# Attach S3 AP
VOL_ID_A=$(aws fsx describe-volumes \
  --filters Name=file-system-id,Values="$FS_ID_A" \
  --query "Volumes[?Name=='${ORIGIN_VOL}'].VolumeId" \
  --output text --region "$REGION_A")

aws fsx create-and-attach-s3-access-point \
  --name "$S3AP_NAME" --type ONTAP \
  --ontap-configuration "{
    \"VolumeId\": \"${VOL_ID_A}\",
    \"FileSystemIdentity\": {\"Type\": \"UNIX\", \"UnixUser\": {\"Name\": \"fsxadmin\"}}
  }" --region "$REGION_A" | jq '{Name: .S3AccessPoint.Name, Status: .S3AccessPoint.Lifecycle}'
```

---

## Step 5-6: Lambda Writer デプロイ & データ書き込み

> [Demo Guide 01 Step 5-6](../en/demo-guide-01-flexcache-same-region.md#step-5-lambda-writer-関数のデプロイ) . Refer to this guide.Region A で Lambda をデプロイし、S3 AP 経由でテストデータを書き込みます。

---

## Step 7: Create FlexCache Cache Volume (Region B)

```bash
# Create FlexCache in Region B (Origin = Region A volume)
curl -sk -u "${USER_B}:${PASS_B}" \
  -X POST "https://${MGMT_IP_B}/api/storage/flexcache/flexcaches" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"${CACHE_VOL}\",
    \"svm\": {\"name\": \"${SVM_NAME_B}\"},
    \"size\": 64424509440,
    \"type\": \"rw\",
    \"style\": \"flexgroup\",
    \"use_tiered_aggregate\": true,
    \"nas\": {\"path\": \"/${CACHE_VOL}\"},
    \"flexcache\": {
      \"fill_policy\": \"demand\",
      \"writeback\": {\"enabled\": true},
      \"origins\": [{
        \"volume\": {\"name\": \"${ORIGIN_VOL}\"},
        \"svm\": {\"name\": \"${SVM_NAME_A}\"}
      }]
    }
  }" | jq '{job_uuid: .job.uuid, state: .job.state}'
```

```bash
# 作成CompleteVerify
sleep 45
curl -sk -u "${USER_B}:${PASS_B}" \
  "https://${MGMT_IP_B}/api/storage/volumes?name=${CACHE_VOL}&fields=state,flexcache" \
  | jq '.records[0] | {name, state, origin: .flexcache.origins[0].volume.name}'
```

**Expected Output:**
```json
{
  "name": "vol_cross_cache",
  "state": "online",
  "origin": "vol_cross_origin"
}
```

---

## Step 8: NFS Verification（Region B Linux EC2）

```bash
# Get Region B Data LIF
DATA_LIF_B=$(curl -sk -u "${USER_B}:${PASS_B}" \
  "https://${MGMT_IP_B}/api/network/ip/interfaces?svm.name=${SVM_NAME_B}&services=data_nfs&fields=ip.address" \
  | jq -r '.records[0].ip.address')

# Execute on Region B Linux EC2
sudo mkdir -p /mnt/cross_cache
sudo mount -t nfs -o vers=3 ${DATA_LIF_B}:/${CACHE_VOL} /mnt/cross_cache

# Data written by Lambda in Region A is readable
ls -la /mnt/cross_cache/demo-data/
cat /mnt/cross_cache/demo-data/sensor-001.json | jq .
```

```bash
# Write-back test: Region B → Region A
echo '{"source": "region-b-nfs", "ts": '$(date +%s)'}' > /mnt/cross_cache/demo-data/cross-region-test.json

# Region A で S3 AP 経由でVerify (after flush)
sleep 30
aws s3api get-object --bucket "$S3AP_ALIAS" --key "demo-data/cross-region-test.json" \
  /tmp/cross-region-result.json --region "$REGION_A" && cat /tmp/cross-region-result.json
```

---

## Step 9: Latency Measurement

```bash
# RTT from Region B EC2 to Region A Intercluster LIF
ping -c 5 $IC_LIFS_A | tail -1
```

**Expectedされる出力例（ap-northeast-1 ↔ us-west-2）:**
```
rtt min/avg/max/mdev = 105.2/108.4/112.1/2.3 ms
```

> **Note**: FlexCache の初回読み取り（cache miss）はこの RTT 分のレイテンシが加算されます。2回目以降はキャッシュヒットによりローカル速度で読めます。Write-back の flush も RTT にImpactされますが、バックグラウンド処理のためクライアント体感にはImpactしません。

---

## Cleanup

```bash
# 1. NFS unmount（Region B EC2）
sudo umount /mnt/cross_cache

# 2. Delete FlexCache (Region B)
CACHE_UUID=$(curl -sk -u "${USER_B}:${PASS_B}" \
  "https://${MGMT_IP_B}/api/storage/volumes?name=${CACHE_VOL}&svm.name=${SVM_NAME_B}" \
  | jq -r '.records[0].uuid')
curl -sk -u "${USER_B}:${PASS_B}" -X DELETE "https://${MGMT_IP_B}/api/storage/volumes/${CACHE_UUID}"
sleep 30

# 3. Delete SVM Peering
# 4. Delete Cluster Peering
# 5. S3 AP デタッチ + Delete Origin Volume (Region A)
# 6. Delete VPC Peering
aws ec2 delete-vpc-peering-connection --vpc-peering-connection-id "$PEERING_ID" --region "$REGION_A"

# 7. Delete Route Table entries
aws ec2 delete-route --route-table-id "$RT_A" --destination-cidr-block "$VPC_CIDR_B" --region "$REGION_A"
aws ec2 delete-route --route-table-id "$RT_B" --destination-cidr-block "$VPC_CIDR_A" --region "$REGION_B"

# 8. Lambda 削除（Demo Guide 01 refer to this guide）
```

---

## Troubleshooting

| Symptom | Cause | Resolution |
|------|------|------|
| Cluster Peer が "unavailable" | VPC Peering route not configured | Add peer VPC CIDR → pcx route to Route Table |
| Cluster Peer Connection timeout | SG で 11104-11105 未許可 | Both regionsの FSx SG でポート許可をVerify |
| FlexCache 作成失敗: "peer not found" | SVM Peering not created | Create SVM Peer from Step 3 |
| Cache miss で高レイテンシ | Normal behavior (first access fetches from Origin) | 2回目のアクセスではキャッシュヒットをVerify |
| Write-back が反映されない | Cross-region flush takes time | Wait 60+ seconds (RTT × batch size) |
| VPC Peering が "failed" | CIDR overlap | VPC CIDR が重複していないかVerify |

---

## References

- [AWS Docs: VPC Peering](https://docs.aws.amazon.com/vpc/latest/peering/)
- [AWS Docs: FSx for ONTAP FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html)
- [NetApp Docs: Cluster Peering](https://docs.netapp.com/us-en/ontap/peering/index.html)
- [Demo Guide 01: FlexCache 同一リージョン](../en/demo-guide-01-flexcache-same-region.md)

> 🌐 Language: **日本語** | [English](../en/demo-guide-04-flexcache-cvo-gcp.md)

# Demo Guide 04: FlexCache CVO on GCP（FSx for ONTAP → Cloud Volumes ONTAP on GCP）

> **所要時間**: 約120分（CVO デプロイ含む）
> **コスト**: ~$20–30（AWS + GCP 合算、検証後に削除する場合）
> **対象読者**: マルチクラウド構成を検討するインフラ/データエンジニア
> **ONTAP バージョン**: FSx 9.17.1+ / CVO 9.15.1+

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## このデモで検証すること

```
AWS Cloud (ap-northeast-1)                  Google Cloud (us-central1)
┌────────────────────────────┐              ┌────────────────────────────┐
│  Lambda ──S3 API──▶ S3 AP  │              │                            │
│        │                   │              │  Cloud Volumes ONTAP (GCP) │
│        ▼                   │  HA VPN /    │    FlexCache Cache Volume  │
│   Origin Volume            │  Cloud VPN   │           │                │
│   (FSx for ONTAP)         │◄════════════▶│    NFS mount               │
│                            │  Intercluster│   (GCE instance)           │
└────────────────────────────┘              └────────────────────────────┘
```

```mermaid
flowchart LR
    subgraph AWS["AWS Cloud"]
        Lambda["Lambda"]
        S3AP["S3 AP"]
        Origin["Origin Volume\n(FSx for ONTAP)"]
    end
    subgraph GCP["Google Cloud"]
        Cache["FlexCache Cache\n(CVO on GCP)"]
        GCE["GCE Instance\n(NFS)"]
    end

    Lambda -->|"S3 API"| S3AP --> Origin
    Origin ===|"FlexCache\nHA VPN"| Cache
    Cache --> GCE
```


**検証ポイント:**

| # | 検証項目 | プロトコル |
|:-:|---------|-----------|
| 1 | Lambda → S3 AP で Origin にデータ書き込み | S3 |
| 2 | GCP 側 CVO FlexCache で NFS アクセス | NFS |
| 3 | GCP → AWS write-back が S3 AP に反映 | NFS write-back |
| 4 | クロスクラウドレイテンシの影響 | NFS |

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## 前提条件

[共通前提条件](./demo-guide-00-prerequisites.md) に加え:

| リソース | クラウド | 説明 |
|----------|---------|------|
| FSx for ONTAP | AWS | Origin Volume |
| Cloud Volumes ONTAP | GCP | FlexCache Cache (PAYGO or BYOL) |
| HA VPN or Cloud Interconnect | AWS ↔ GCP | 暗号化トンネル |
| GCP VPC + Subnet | GCP | CVO デプロイ先 |

### 追加ツール

| ツール | 用途 |
|--------|------|
| `gcloud` CLI | GCP リソース管理 |
| Terraform（任意） | CVO + VPN の IaC デプロイ |

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## Step 0: 環境変数の設定

```bash
# === AWS 側 ===
export AWS_REGION="ap-northeast-1"
export FS_ID="fs-0EXAMPLE1234abcde"
export SVM_NAME_AWS="svm-origin"
export SECRET_ARN="arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:fsxn-admin-XXXXXX"
export AWS_VPC_ID="vpc-0aaaa1111"
export AWS_VPC_CIDR="10.0.0.0/16"

# === GCP 側 ===
export GCP_PROJECT="my-project-123456"
export GCP_REGION="us-central1"
export GCP_ZONE="us-central1-a"
export GCP_VPC="cvo-vpc"
export GCP_SUBNET="cvo-subnet"
export GCP_CIDR="10.100.0.0/16"
export CVO_CLUSTER_IP="198.51.100.40"    # CVO management IP (デプロイ後に確定)
export CVO_IC_LIF="198.51.100.41"         # CVO Intercluster LIF
export CVO_SVM="svm-gcp-cache"

# === 共通 ===
export ORIGIN_VOL="vol_gcp_origin"
export CACHE_VOL="vol_gcp_cache"
```

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## Step 1: GCP HA VPN の作成

```bash
# GCP 側 VPN Gateway 作成
gcloud compute vpn-gateways create aws-vpn-gw \
  --network "$GCP_VPC" \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT"

# Cloud Router 作成
gcloud compute routers create aws-router \
  --network "$GCP_VPC" \
  --region "$GCP_REGION" \
  --asn 65001 \
  --project "$GCP_PROJECT"
```

```bash
# AWS 側 VPN Gateway / Customer Gateway 作成
AWS_VGW=$(aws ec2 create-vpn-gateway --type ipsec.1 \
  --query 'VpnGateway.VpnGatewayId' --output text --region "$AWS_REGION")
aws ec2 attach-vpn-gateway --vpn-gateway-id "$AWS_VGW" --vpc-id "$AWS_VPC_ID" --region "$AWS_REGION"

# GCP VPN Gateway の外部 IP を取得して Customer Gateway 作成
GCP_VPN_IP=$(gcloud compute vpn-gateways describe aws-vpn-gw \
  --region "$GCP_REGION" --format='value(vpnInterfaces[0].ipAddress)' --project "$GCP_PROJECT")

AWS_CGW=$(aws ec2 create-customer-gateway --type ipsec.1 \
  --bgp-asn 65001 --public-ip "$GCP_VPN_IP" \
  --query 'CustomerGateway.CustomerGatewayId' --output text --region "$AWS_REGION")

# Site-to-Site VPN 接続作成
aws ec2 create-vpn-connection \
  --type ipsec.1 \
  --vpn-gateway-id "$AWS_VGW" \
  --customer-gateway-id "$AWS_CGW" \
  --options '{"StaticRoutesOnly": false}' \
  --region "$AWS_REGION"
```

> **注意**: 実際の VPN 構成は AWS/GCP のドキュメントに従ってトンネル設定（PSK、BGP パラメータ）を行ってください。ここでは概要のみ示します。

```bash
# VPN 接続後のルーティング確認
# AWS Route Table に GCP CIDR → VGW のルートが BGP で伝播されていることを確認
aws ec2 describe-route-tables --filters Name=vpc-id,Values="$AWS_VPC_ID" \
  --query 'RouteTables[0].Routes[?DestinationCidrBlock==`10.100.0.0/16`]' \
  --region "$AWS_REGION"
```

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## Step 2: CVO on GCP のデプロイ

CVO は ONTAP REST API 経由で管理します。デプロイには Terraform または GCP Marketplace を使用します。

```bash
# Terraform を使用する場合（例: netapp-cloudmanager/cvo-gcp module）
# ※ Terraform テンプレートは別途用意

# CVO デプロイ完了後、管理 IP を確認
echo "CVO Cluster Management IP: $CVO_CLUSTER_IP"

# ONTAP REST API 疎通確認
curl -sk -u "admin:<CVO_PASSWORD>" \
  "https://${CVO_CLUSTER_IP}/api/cluster?fields=version" | jq '.version'
```

**期待される出力:**
```json
{
  "full": "NetApp Release 9.15.1P2",
  "generation": 9,
  "major": 15,
  "minor": 1
}
```

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## Step 3: Cluster Peering（AWS ↔ GCP）

```bash
# AWS 側 Intercluster LIF を取得
MGMT_IP=$(aws fsx describe-file-systems --file-system-ids "$FS_ID" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
  --output text --region "$AWS_REGION")

CREDS=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" \
  --query SecretString --output text --region "$AWS_REGION")
ONTAP_USER=$(echo "$CREDS" | jq -r '.username')
ONTAP_PASS=$(echo "$CREDS" | jq -r '.password')

AWS_IC_LIFS=$(curl -sk -u "${ONTAP_USER}:${ONTAP_PASS}" \
  "https://${MGMT_IP}/api/network/ip/interfaces?services=intercluster_core&fields=ip.address" \
  | jq -r '[.records[].ip.address] | join(",")')

# AWS 側から Cluster Peer 作成
curl -sk -u "${ONTAP_USER}:${ONTAP_PASS}" \
  -X POST "https://${MGMT_IP}/api/cluster/peers" \
  -H "Content-Type: application/json" \
  -d "{
    \"remote\": {\"ip_addresses\": [\"${CVO_IC_LIF}\"]},
    \"authentication\": {\"passphrase\": \"gcp-cross-cloud-2026\"},
    \"encryption\": {\"proposed\": \"tls_psk\"}
  }" | jq '{job: .job.uuid}'
```

```bash
# GCP CVO 側で Cluster Peer を承認
curl -sk -u "admin:<CVO_PASSWORD>" \
  -X POST "https://${CVO_CLUSTER_IP}/api/cluster/peers" \
  -H "Content-Type: application/json" \
  -d "{
    \"remote\": {\"ip_addresses\": [$(echo $AWS_IC_LIFS | sed 's/,/\",\"/g' | sed 's/^/\"/;s/$/\"/')]},
    \"authentication\": {\"passphrase\": \"gcp-cross-cloud-2026\"}
  }" | jq '{job: .job.uuid}'
```

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## Step 4: SVM Peering + FlexCache 作成

```bash
# SVM Peer 作成（AWS 側から）
curl -sk -u "${ONTAP_USER}:${ONTAP_PASS}" \
  -X POST "https://${MGMT_IP}/api/svm/peers" \
  -H "Content-Type: application/json" \
  -d "{
    \"svm\": {\"name\": \"${SVM_NAME_AWS}\"},
    \"peer\": {\"svm\": {\"name\": \"${CVO_SVM}\"}},
    \"applications\": [\"flexcache\"]
  }" | jq '{job: .job.uuid}'

sleep 15

# GCP CVO 側で FlexCache を作成
curl -sk -u "admin:<CVO_PASSWORD>" \
  -X POST "https://${CVO_CLUSTER_IP}/api/storage/flexcache/flexcaches" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"${CACHE_VOL}\",
    \"svm\": {\"name\": \"${CVO_SVM}\"},
    \"size\": 107374182400,
    \"type\": \"rw\",
    \"style\": \"flexgroup\",
    \"nas\": {\"path\": \"/${CACHE_VOL}\"},
    \"flexcache\": {
      \"fill_policy\": \"demand\",
      \"writeback\": {\"enabled\": true},
      \"origins\": [{
        \"volume\": {\"name\": \"${ORIGIN_VOL}\"},
        \"svm\": {\"name\": \"${SVM_NAME_AWS}\"}
      }]
    }
  }" | jq '{job_uuid: .job.uuid}'
```

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## Step 5: Origin Volume + S3 AP + Lambda Writer

> [Demo Guide 01 Step 4-6](./demo-guide-01-flexcache-same-region.md#step-4-origin-volume-作成--s3-ap-アタッチ) を参照。AWS 側で Origin Volume を作成し S3 AP をアタッチ、Lambda でデータを書き込みます。

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## Step 6: NFS 検証（GCE インスタンス）

```bash
# GCE インスタンスに SSH
gcloud compute ssh cvo-test-vm --zone "$GCP_ZONE" --project "$GCP_PROJECT"

# CVO Data LIF の IP（デプロイ後に確認）
CVO_DATA_LIF="198.51.100.42"

# NFS マウント
sudo mkdir -p /mnt/gcp_cache
sudo mount -t nfs -o vers=3 ${CVO_DATA_LIF}:/${CACHE_VOL} /mnt/gcp_cache

# Lambda が書き込んだデータの読み取り
ls -la /mnt/gcp_cache/demo-data/
cat /mnt/gcp_cache/demo-data/sensor-001.json | jq .
```

```bash
# Write-back テスト
echo '{"source": "gcp-cvo", "ts": '$(date +%s)'}' > /mnt/gcp_cache/demo-data/gcp-written.json

# AWS S3 AP で確認
sleep 30
aws s3api get-object --bucket "$S3AP_ALIAS" --key "demo-data/gcp-written.json" \
  /tmp/gcp-result.json --region "$AWS_REGION" && cat /tmp/gcp-result.json
```

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## クリーンアップ

```bash
# 1. GCE: NFS アンマウント
sudo umount /mnt/gcp_cache

# 2. CVO: FlexCache 削除
# 3. SVM Peering / Cluster Peering 削除
# 4. CVO インスタンス削除 (Terraform destroy or Marketplace から)
# 5. VPN トンネル削除
gcloud compute vpn-tunnels delete <tunnel-name> --region "$GCP_REGION" --project "$GCP_PROJECT"
gcloud compute vpn-gateways delete aws-vpn-gw --region "$GCP_REGION" --project "$GCP_PROJECT"
aws ec2 delete-vpn-connection --vpn-connection-id <vpn-id> --region "$AWS_REGION"
aws ec2 detach-vpn-gateway --vpn-gateway-id "$AWS_VGW" --vpc-id "$AWS_VPC_ID" --region "$AWS_REGION"
aws ec2 delete-vpn-gateway --vpn-gateway-id "$AWS_VGW" --region "$AWS_REGION"

# 6. AWS 側: Origin Volume + S3 AP 削除（Demo Guide 01 参照）
```

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| VPN トンネルが UP にならない | PSK / BGP ASN 不一致 | 両側の VPN パラメータを確認 |
| Cluster Peer "unavailable" | VPN 経由で 11104-11105 到達不可 | GCP Firewall + AWS SG を確認 |
| CVO の REST API 応答なし | CVO がブート中 or SG 不正 | GCP Firewall で 443 を許可 |
| FlexCache 作成: "cannot reach origin" | VPN 経由の MTU 問題 | MTU 1400 に調整（VPN overhead） |
| Write-back が遅い | クロスクラウド RTT > 50ms | 正常動作。バッチ flush のため体感影響は少ない |

---

> ⚠️ **検証ステータス**: 手順レベルのガイド（実環境での E2E 検証は未実施）。
> コマンドとアーキテクチャは公式ドキュメントおよび Guide 01/02（同一リージョン / クロスリージョン FSx for ONTAP）で検証済みのパターンに基づいています。
> 完全な検証には外部環境が必要です — BACKLOG items 7–12 を参照。


## 参考リンク

- [GCP Docs: HA VPN](https://cloud.google.com/network-connectivity/docs/vpn/concepts/overview)
- [AWS Docs: Site-to-Site VPN](https://docs.aws.amazon.com/vpn/latest/s2svpn/)
- [NetApp Docs: CVO on GCP](https://docs.netapp.com/us-en/cloud-volumes-ontap-relnotes/)
- [Demo Guide 01: FlexCache 同一リージョン](./demo-guide-01-flexcache-same-region.md)

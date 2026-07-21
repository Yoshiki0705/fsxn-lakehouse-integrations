> 🌐 Language: **日本語** | [English](../en/demo-guide-06-flexcache-gcnv.md)

# Demo Guide 06: FlexCache GCNV（FSx for ONTAP → Google Cloud NetApp Volumes）

> **所要時間**: 約90分（VPN 構成済みの場合）
> **コスト**: ~$15–25（AWS + GCP 合算、検証後に削除する場合）
> **対象読者**: GCP ネイティブストレージと AWS データ連携を検討するエンジニア
> **ONTAP バージョン**: FSx 9.17.1+ / GCNV（Google 管理、バージョン自動）

---

## このデモで検証すること

```
AWS Cloud (ap-northeast-1)                  Google Cloud (us-central1)
┌────────────────────────────┐              ┌────────────────────────────┐
│  Lambda ──S3 API──▶ S3 AP  │              │                            │
│        │                   │              │  Google Cloud NetApp       │
│        ▼                   │  HA VPN      │  Volumes (GCNV)            │
│   Origin Volume            │◄════════════▶│    FlexCache Cache Volume  │
│   (FSx for ONTAP)         │  Intercluster│           │                │
│                            │              │    NFSv3 mount             │
│                            │              │   (GCE instance)           │
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
        GCNV["GCNV FlexCache\n(Cache only, NFSv3)"]
        GCE["GCE Instance"]
    end

    Lambda -->|"S3 API"| S3AP --> Origin
    Origin ===|"FlexCache\nHA VPN"| GCNV
    GCNV -->|"NFSv3\n(read-only)"| GCE
```


**重要な制約:**

| 制約 | 詳細 |
|------|------|
| GCNV は Cache のみ | GCNV を Origin にすることはできない |
| NFSv3 のみ | GCNV FlexCache は NFSv4 未対応 |
| Write-back 非対応 | GCNV FlexCache は read-only |
| Google 管理 | ONTAP CLI/REST API への直接アクセス不可 |

**検証ポイント:**

| # | 検証項目 | プロトコル |
|:-:|---------|-----------|
| 1 | Lambda → S3 AP で Origin にデータ書き込み | S3 |
| 2 | GCNV FlexCache で NFSv3 データアクセス | NFSv3 |
| 3 | Origin 更新 → GCNV Cache 反映の遅延測定 | NFSv3 |

---

## 前提条件

[共通前提条件](./demo-guide-00-prerequisites.md) に加え:

| リソース | クラウド | 説明 |
|----------|---------|------|
| FSx for ONTAP | AWS | Origin Volume |
| GCNV Storage Pool + Volume | GCP | FlexCache Cache |
| HA VPN | AWS ↔ GCP | 暗号化トンネル |
| GCP VPC (PSA 有効) | GCP | GCNV 接続用 Private Service Access |

### 追加ツール

| ツール | 用途 |
|--------|------|
| `gcloud` CLI | GCP / GCNV リソース管理 |

---

## Step 0: 環境変数の設定

```bash
# === AWS 側 ===
export AWS_REGION="ap-northeast-1"
export FS_ID="fs-0EXAMPLE1234abcde"
export SVM_NAME_AWS="svm-origin"
export SECRET_ARN="arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:fsxn-admin-XXXXXX"

# === GCP 側 ===
export GCP_PROJECT="my-project-123456"
export GCP_REGION="us-central1"
export GCP_ZONE="us-central1-a"
export GCP_VPC="gcnv-vpc"
export GCP_CIDR="10.150.0.0/16"

# === 共通 ===
export ORIGIN_VOL="vol_gcnv_origin"
```

---

## Step 1: GCP HA VPN 設定

> VPN の設定手順は [Demo Guide 04 Step 1](./demo-guide-04-flexcache-cvo-gcp.md#step-1-gcp-ha-vpn-の作成) と同一です。AWS ↔ GCP 間の HA VPN を構成してください。

```bash
# VPN 接続確認
gcloud compute vpn-tunnels describe <tunnel-name> \
  --region "$GCP_REGION" --project "$GCP_PROJECT" \
  --format='value(status)'
# 期待値: ESTABLISHED
```

---

## Step 2: GCNV Storage Pool の作成

```bash
# Private Service Access の設定（GCNV 接続に必要）
gcloud compute addresses create gcnv-psa-range \
  --global \
  --purpose VPC_PEERING \
  --prefix-length 20 \
  --network "$GCP_VPC" \
  --project "$GCP_PROJECT"

gcloud services vpc-peerings connect \
  --service netapp.servicenetworking.goog \
  --ranges gcnv-psa-range \
  --network "$GCP_VPC" \
  --project "$GCP_PROJECT"

# Storage Pool 作成
gcloud netapp storage-pools create gcnv-demo-pool \
  --location "$GCP_REGION" \
  --capacity 2048 \
  --service-level PREMIUM \
  --network "$GCP_VPC" \
  --project "$GCP_PROJECT"
```

**期待される出力:**
```
Created storage pool [gcnv-demo-pool].
```

---

## Step 3: GCNV FlexCache Volume の作成

GCNV の FlexCache は `gcloud` CLI または GCP Console から作成します。Origin として FSx for ONTAP の Intercluster LIF を指定します。

```bash
# FSx for ONTAP の Intercluster LIF を取得
MGMT_IP=$(aws fsx describe-file-systems --file-system-ids "$FS_ID" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
  --output text --region "$AWS_REGION")

CREDS=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN" \
  --query SecretString --output text --region "$AWS_REGION")
ONTAP_USER=$(echo "$CREDS" | jq -r '.username')
ONTAP_PASS=$(echo "$CREDS" | jq -r '.password')

AWS_IC_LIFS=$(curl -sk -u "${ONTAP_USER}:${ONTAP_PASS}" \
  "https://${MGMT_IP}/api/network/ip/interfaces?services=intercluster_core&fields=ip.address" \
  | jq -r '.records[].ip.address')
echo "AWS Intercluster LIFs: $AWS_IC_LIFS"
```

```bash
# GCNV FlexCache Volume 作成
# ※ GCNV FlexCache は Google Cloud Console または API 経由で作成
# 以下は gcloud netapp volumes create の例（FlexCache パラメータは GA 時点で確認）

gcloud netapp volumes create gcnv-cache-vol \
  --location "$GCP_REGION" \
  --capacity 1024 \
  --storage-pool gcnv-demo-pool \
  --protocols NFSv3 \
  --share-name gcnv_cache \
  --project "$GCP_PROJECT"

# ※ FlexCache Origin の設定は GCNV の Replication / Cache 機能経由で構成
# 詳細は GCP Console > NetApp Volumes > Volume > Create Cache を参照
```

> **注意**: GCNV FlexCache の作成手順は Google Cloud のリリース状況により異なる場合があります。最新の手順は [GCNV Documentation](https://cloud.google.com/netapp/volumes/docs) を参照してください。

---

## Step 4: Origin Volume + S3 AP + Lambda Writer（AWS 側）

> [Demo Guide 01 Step 4-6](./demo-guide-01-flexcache-same-region.md#step-4-origin-volume-作成--s3-ap-アタッチ) を参照。

---

## Step 5: NFSv3 検証（GCE インスタンス）

```bash
# GCE インスタンスに SSH
gcloud compute ssh gcnv-test-vm --zone "$GCP_ZONE" --project "$GCP_PROJECT"

# GCNV マウントポイント確認
GCNV_MOUNT_IP=$(gcloud netapp volumes describe gcnv-cache-vol \
  --location "$GCP_REGION" --project "$GCP_PROJECT" \
  --format='value(mountOptions.export)')

# NFSv3 マウント
sudo mkdir -p /mnt/gcnv_cache
sudo mount -t nfs -o vers=3,hard,rsize=65536,wsize=65536 \
  ${GCNV_MOUNT_IP}:/gcnv_cache /mnt/gcnv_cache

# マウント確認
df -h /mnt/gcnv_cache
```

```bash
# Lambda が書き込んだデータの読み取り
ls -la /mnt/gcnv_cache/demo-data/
cat /mnt/gcnv_cache/demo-data/sensor-001.json | jq .
```

**期待される出力:**
```json
{
  "sensor_id": "S001",
  "temperature": 23.5,
  "humidity": 65,
  "ts": 1753090800
}
```

> **注意**: GCNV FlexCache は read-only です。書き込み試行は `Read-only file system` エラーになります。

```bash
# Write テスト（失敗することを確認）
echo "test" > /mnt/gcnv_cache/demo-data/write-test.json
# 期待: "Read-only file system"
```

---

## Step 6: Origin 更新 → Cache 反映テスト

```bash
# AWS 側で Lambda からデータを追加
aws lambda invoke \
  --function-name tc09-s3ap-writer \
  --payload '{"prefix": "demo-data/gcnv-test"}' \
  --cli-binary-format raw-in-base64-out \
  /tmp/gcnv-test.json --region "$AWS_REGION"

# GCE 側で反映確認（TTL 経過後）
sleep 60
ls /mnt/gcnv_cache/demo-data/gcnv-test/
```

---

## クリーンアップ

```bash
# 1. GCE: NFS アンマウント
sudo umount /mnt/gcnv_cache

# 2. GCNV Volume 削除
gcloud netapp volumes delete gcnv-cache-vol \
  --location "$GCP_REGION" --project "$GCP_PROJECT" --quiet

# 3. GCNV Storage Pool 削除
gcloud netapp storage-pools delete gcnv-demo-pool \
  --location "$GCP_REGION" --project "$GCP_PROJECT" --quiet

# 4. VPN 削除（Demo Guide 04 参照）

# 5. AWS 側: Origin Volume + S3 AP 削除（Demo Guide 01 参照）
```

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|------|------|------|
| GCNV Volume 作成失敗 | PSA 未設定 | `vpc-peerings connect` が完了しているか確認 |
| NFSv4 マウント不可 | GCNV FlexCache は NFSv3 のみ | `-o vers=3` を指定 |
| "Read-only file system" | GCNV FlexCache は read-only | 正常動作。書き込みは Origin (AWS) 経由 |
| Cache にデータが見えない | VPN 経由の接続問題 | VPN トンネル状態 + Intercluster ポートを確認 |
| TTL 後もデータ反映されない | GCNV Cache 管理はGoogle側 | GCP Console で Volume 状態を確認 |

---

## 参考リンク

- [GCP Docs: NetApp Volumes](https://cloud.google.com/netapp/volumes/docs)
- [GCP Docs: HA VPN](https://cloud.google.com/network-connectivity/docs/vpn/concepts/overview)
- [NetApp Docs: FlexCache](https://docs.netapp.com/us-en/ontap/flexcache/index.html)
- [Demo Guide 04: FlexCache CVO on GCP](./demo-guide-04-flexcache-cvo-gcp.md)
- [Demo Guide 01: FlexCache 同一リージョン](./demo-guide-01-flexcache-same-region.md)

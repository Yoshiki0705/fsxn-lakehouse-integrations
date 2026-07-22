> 🌐 Language: **日本語** | [English](../en/demo-guide-00-prerequisites.md)

# Demo Guide: 共通前提条件 / Common Prerequisites

> 各デモガイドから参照される共通の前提条件・ツール・変数設定。
> Each demo guide references this document for shared prerequisites.

> 📐 **設計ガイド**: デモを実行する前に、以下の設計考慮事項を確認することを推奨します。
> - [S3 AP 設計考慮事項](../../docs/ja/s3ap-design-considerations.md) — ディレクトリ設計、性能特性、PoC チェックリスト
> - [FlexCache / SnapMirror 利用時の追加考慮事項](../../docs/ja/s3ap-flexcache-snapmirror-considerations.md) — 書き込みモード選択、キャッシュ伝搬、Teardown 順序

---

## Required Tools

| Tool | Version | Check Command |
|------|---------|---------------|
| AWS CLI | v2.15+ | `aws --version` |
| jq | 1.6+ | `jq --version` |
| curl | 7.x+ | `curl --version` |
| Python | 3.12+ | `python3 --version` |

## ONTAP Version Requirements

| Feature | Minimum ONTAP |
|---------|:-------------:|
| S3 Access Point | 9.14.1 |
| S3 NAS bucket on FlexCache Origin | 9.12.1 |
| S3 NAS bucket on FlexCache Cache | **9.18.1** |
| FlexCache write-back | 9.15.1 |
| FlexCache (read-only) | 9.5 |
| SnapMirror Async | 9.11.1 |
| Cluster Peering Encryption (TLS 1.2) | 9.6 |

## Common Environment Variables

```bash
export AWS_REGION="ap-northeast-1"
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```

## ONTAP REST API Helper

All guides use this pattern for ONTAP REST API calls:

```bash
# Get management IP
MGMT_IP=$(aws fsx describe-file-systems \
  --file-system-ids "$FS_ID" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
  --output text --region "$AWS_REGION")

# Get credentials from Secrets Manager
CREDS=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ARN" --query SecretString --output text --region "$AWS_REGION")
ONTAP_USER=$(echo "$CREDS" | jq -r '.username')
ONTAP_PASS=$(echo "$CREDS" | jq -r '.password')

# ONTAP REST API call template
ontap_api() {
  curl -sk -u "${ONTAP_USER}:${ONTAP_PASS}" \
    -X "$1" "https://${MGMT_IP}/api$2" \
    -H "Content-Type: application/json" ${3:+-d "$3"}
}
```

## Network Ports Required

| Port | Protocol | Purpose |
|------|----------|---------|
| 443 | TCP | ONTAP REST API (management) |
| 2049 | TCP | NFS |
| 445 | TCP | SMB/CIFS |
| 11104 | TCP | SnapMirror / FlexCache intercluster |
| 11105 | TCP | SnapMirror / FlexCache intercluster |

## Related Documentation

- [AWS Docs: FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/)
- [NetApp Docs: ONTAP REST API](https://docs.netapp.com/us-en/ontap-automation/)
- [Research Document (EN)](./en/research.md)
- [Research Document (JA)](./ja/research.md)

- [Research Document (EN)](../en/research.md)
- [Research Document (JA)](./research.md)

---

## FSx for ONTAP 固有の注意事項（実機検証で確認済み）

以下は本プロジェクトの検証中に確認された、ドキュメントに明記されていない FSx for ONTAP 固有の動作です。デモガイドの手順はこれらを織り込んで記述されています。

### FlexCache 作成

| 項目 | 内容 |
|------|------|
| **API エンドポイント** | `/api/storage/flexcache/flexcaches` を使用。`/api/storage/volumes` では FlexCache パラメータが無効 |
| **`use_tiered_aggregate: true`** | FSx for ONTAP では必須。FabricPool aggregate を使用するため、指定しないと "No suitable storage" エラー |
| **最小サイズ** | 60GB 以上（FlexGroup タイプのため） |
| **削除手順** | ① junction path を空にする (PATCH `nas.path: ""`) → ② write-back 有効の場合は無効化 → ③ DELETE |

### fsxadmin パスワード

| 項目 | 内容 |
|------|------|
| **リセット後の反映遅延** | FSx API でパスワード変更後、ONTAP REST API に反映されるまで 30-60 秒かかる |
| **推奨パターン** | Secrets Manager に保存し、スクリプトから動的に取得する（ハードコード禁止） |

### S3 Access Point

| 項目 | 内容 |
|------|------|
| **FileSystemIdentity** | UNIX タイプの場合、ユーザーは SVM 上に存在する UNIX ユーザーを指定。`root` は常に存在 |
| **作成完了までの時間** | 30-60 秒。AVAILABLE になるまでポーリングが必要 |
| **削除コマンド** | `aws fsx detach-and-delete-s3-access-point --name <name>` |

### VPC Peering（クロスリージョン）

| 項目 | 内容 |
|------|------|
| **ルーティング** | EC2 のサブネットが明示的 Route Table に紐付いている場合、main RT へのルート追加では到達不可。EC2 サブネットの RT に個別追加が必要 |
| **Security Group** | FSx 側の SG に相手 VPC CIDR からのインバウンド (all traffic or 443+11104-11105) を許可 |
| **Accept** | 同一アカウントでもクロスリージョンの場合は明示的に `accept-vpc-peering-connection` が必要 |

### FlexCache Write-Back

| 項目 | 内容 |
|------|------|
| **Origin への反映時間** | Cache での書き込みが Origin (S3 AP) で読めるまで 30-90 秒 |
| **S3 AP 書き込みとの併用** | 同一ファイルへの同時書き込みは XLD revoke により Cache 側データ消失。ファイルセット分離が必須 |
| **削除前の無効化** | `writeback.enabled: false` に PATCH してから FlexCache を削除 |

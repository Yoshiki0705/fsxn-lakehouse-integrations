# インフラ依頼テンプレート: FSx for ONTAP + S3 Access Point

🌐 日本語 | [English](infrastructure-request-template.md)

## 目的

このテンプレートは、データエンジニアが Iceberg メタデータカタログを実際の FSx for ONTAP データで実行するために必要なインフラをインフラ/プラットフォームチームに依頼する際に使用します。

---

## 依頼概要

**必要なもの**: 非構造化ファイルへの読み取りアクセスを許可する FSx for ONTAP S3 Access Point

**理由**: 既存の NAS ファイル（PDF、画像、CAD、ログ）を S3 にコピーせずに SQL と AI で即座に検索可能にするため

**影響**: 既存の NFS/SMB ワークフローへの変更はゼロ。同じファイルへの読み取り専用 S3 API アクセス。

---

## 必要なリソース

### 1. FSx for ONTAP S3 Access Point

| 設定 | 推奨値 | 備考 |
|------|--------|------|
| 対象ボリューム | カタログ化するファイルを含むボリューム | 読み取り専用アクセスで十分 |
| S3 AP 名 | `metadata-catalog-ap` | `-ext-s3alias` で終わるエイリアスが付与される |
| ファイルシステムアイデンティティ | 専用サービスアカウント（例: `metadata-reader`） | 最小権限: 対象パスへの読み取り専用 |
| セキュリティスタイル | UNIX または Mixed | ボリュームのセキュリティスタイルに合わせる |
| ネットワークアクセス | Lambda/EMR と同じ VPC | または開発用にインターネットアクセス可能 |

### 2. S3 Access Point 用 IAM ポリシー

データエンジニアリングチームには以下の権限を持つ IAM ロール/ユーザーが必要:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:<REGION>:<ACCOUNT_ID>:accesspoint/<AP_NAME>",
        "arn:aws:s3:<REGION>:<ACCOUNT_ID>:accesspoint/<AP_NAME>/*"
      ]
    }
  ]
}
```

---

## データエンジニアリングチームが行うこと

S3 Access Point が準備できたら:

1. `./check-prerequisites.sh --ap-alias <alias>` でアクセスを確認
2. ファイルメタデータをスキャン（読み取り専用、ファイル変更なし）
3. メタデータを S3 Tables に書き込み（FSx とは別）
4. Athena SQL でメタデータをクエリ
5. オプション: Bedrock による AI 分類（ファイル内容を読み取り、S3 Tables にのみ書き込み）

**FSx 上の既存ファイルや権限への変更はありません。**

---

## セットアップ後に必要な情報

| 項目 | 例 |
|------|------|
| S3 AP エイリアス | `metadata-catal-abc123def456-ext-s3alias` |
| リージョン | `ap-northeast-1` |
| 対象ボリュームパス | `/vol1/documents/`, `/vol1/images/` |
| 使用するファイルシステムアイデンティティ | `metadata-reader` (UID 1001) |
| パス制限 | `/vol1/public/` のみアクセス可能 |

---

## インフラチーム向け FAQ

**Q: FSx 上のファイルは変更されますか？**
A: いいえ。S3 AP はこのパイプラインでは読み取り専用で使用（書き込みもサポート）アクセスを提供します。ファイルの変更、移動、削除は行いません。

**Q: NFS/SMB パフォーマンスに影響しますか？**
A: 最小限の影響です。大規模スキャン（10万ファイル以上）はオフピーク時間にスケジュールしてください。

**Q: S3 AP を取り消すとどうなりますか？**
A: メタデータカタログは引き続き動作します（メタデータは S3 Tables にあります）。新しいファイルスキャンは復旧まで失敗します。データ損失はありません。

---

## S3 Access Point セットアップ手順（インフラチーム向け）

### 前提条件チェック

S3 AP 作成前に確認:
- [ ] FSx for ONTAP ファイルシステムが存在し `AVAILABLE` 状態
- [ ] 対象ボリュームが存在し、マウント済み（ジャンクションパスあり）で、カタログ化するファイルを含む
- [ ] VPC で DNS 解決が有効
- [ ] IAM ユーザー/ロールに `fsx:CreateAndAttachS3AccessPoint`, `s3:CreateAccessPoint`, `s3:GetAccessPoint` 権限あり

### オプション A: AWS Console

1. Amazon FSx コンソール (https://console.aws.amazon.com/fsx/) を開く
2. 左ナビゲーションペインで **Volumes** を選択
3. S3 Access Point をアタッチする FSx for ONTAP ボリュームを選択
4. **Actions** メニューから **Create S3 access point** を選択
5. 設定:
   - **Access point name**: `metadata-catalog-ap`（小文字、3-50文字）
   - **File system user identity type**: UNIX または Windows
   - **Username**: 例: `metadata-reader`（ファイルシステム上に存在し、適切な読み取り権限を持つユーザー）
   - **Network origin**: **Internet**（開発用）または **Virtual private cloud (VPC)**（本番用）
6. （オプション）アクセスポイントポリシーを追加して使用可能な IAM プリンシパルを制限
7. **Create access point** を選択
8. 生成された **Alias**（`-ext-s3alias` で終わる）をメモ — これがデータエンジニアリングチームに必要な情報

### オプション B: AWS CLI

```bash
# まず、ボリューム ID を確認:
aws fsx describe-volumes \
  --filters Name=file-system-id,Values=<FSX_FILE_SYSTEM_ID> \
  --query "Volumes[*].{VolumeId:VolumeId,Name:Name,JunctionPath:OntapConfiguration.JunctionPath}" \
  --output table --region <REGION>

# S3 Access Point を作成:
aws fsx create-and-attach-s3-access-point \
  --name metadata-catalog-ap \
  --type ONTAP \
  --ontap-configuration '{
    "VolumeId": "<VOLUME_ID>",
    "FileSystemIdentity": {
      "Type": "UNIX",
      "UnixUser": {
        "Name": "metadata-reader"
      }
    }
  }' \
  --s3-access-point '{
    "VpcConfiguration": {
      "VpcId": "<VPC_ID>"
    }
  }' \
  --region <REGION>
```

**必須パラメータ**:
- `--name`: アクセスポイント名（小文字、3-50文字）
- `--type`: `ONTAP`
- `--ontap-configuration`: ボリューム ID + ファイルシステムアイデンティティ（UNIX ユーザーまたは Windows ユーザー）
- `--s3-access-point`（オプション）: VPC 制限。省略するとインターネットアクセス可能。

`Lifecycle` が `AVAILABLE` になるまで待機してから使用:
```bash
aws fsx describe-s3-access-point-attachments \
  --filters Name=name,Values=metadata-catalog-ap \
  --region <REGION>
```

> **参考**: [AWS ドキュメント — FSx for ONTAP のアクセスポイント作成](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-access-points.html)

---

## ネットワーク構成

```
┌─────────────────────────────────────────────────────────────┐
│  VPC（FSx for ONTAP と同じ）                                  │
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────────┐     │
│  │  プライベートサブネット │    │  FSx for ONTAP          │     │
│  │                     │    │                         │     │
│  │  Lambda / EMR       │───▶│  S3 Access Point        │     │
│  │  (メタデータスキャン)  │    │  (読み取り専用)           │     │
│  │                     │    │                         │    │
│  └──────────┬──────────┘    │  NFS/SMB (変更なし)      │    │
│             │               │  ↕ 既存アプリ             │    │
│             │ NAT GW        └─────────────────────────┘     │
│             ▼                                               │
│  ┌──────────────────────┐                                   │
│  │  AWS サービス         │                                   │
│  │  • S3 Tables         │                                   │
│  │  • Athena            │                                   │
│  │  • Bedrock           │                                   │
│  │  • OpenSearch        │                                   │
│  └──────────────────────┘                                   │
└─────────────────────────────────────────────────────────────┘
```

**ポイント**:
- Lambda/EMR は同じ VPC 内で S3 AP 経由で FSx にアクセス
- AWS サービスへのアウトバウンドは NAT Gateway または VPC Endpoints 経由
- 既存の NFS/SMB トラフィックは影響なし
- インバウンドインターネットアクセスは不要

---

## セキュリティ & 監査

| 制御 | 実装 |
|------|------|
| アクセス範囲 | 専用ファイルシステムアイデンティティによる読み取り専用 S3 AP |
| 最小権限 | IAM ポリシーが特定の AP ARN のみに制限 |
| 監査証跡 | CloudTrail が全 S3 AP API コールを記録 |
| データ分類 | メタデータのみが FSx を離れる; 生ファイルはそのまま |
| ネットワーク分離 | 同じ VPC、プライベートサブネット、パブリックアクセスなし |
| 取り消し | S3 AP または IAM ポリシーを削除して即座に取り消し |

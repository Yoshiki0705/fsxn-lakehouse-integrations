# FSx for ONTAP S3 AP ネットワーキング考慮事項

## 概要

FSx for ONTAP S3 Access Points には、通常の S3 バケットアクセスとは異なるネットワーキング要件があります。本ドキュメントは複数の検証ラウンドからの知見を集約しています。

## 主な発見

### 1. S3 Gateway エンドポイントと FSx for ONTAP S3 AP

**既知の問題**（[FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) で文書化済み）:

> VPC 内 Lambda からタイムアウト | Internet Origin AP に S3 Gateway EP 経由でアクセス | Lambda を VPC 外に配置、または NAT Gateway 経由に変更

**説明**: VPC アタッチされた Lambda または EC2 インスタンスが internet-origin FSx for ONTAP S3 AP にアクセスする際、S3 Gateway VPC エンドポイントがトラフィックをインターセプトするが、FSx for ONTAP S3 AP バックエンドに正しくルーティングできない場合があります。FSx for ONTAP S3 AP alias は `s3-r-w.<region>.amazonaws.com` に解決され、Gateway エンドポイントが通常の S3 バケットトラフィックと同じ方法で処理できない可能性があるためです。

**回避策**:
1. Lambda を VPC 外に配置（VPC アタッチメントなし）— internet-origin AP に最もシンプル
2. S3 AP トラフィックに NAT Gateway を使用
3. 特定のルートテーブルから S3 Gateway エンドポイントを削除（本番非推奨 — 通常の S3 アクセス最適化が失われる）

### 2. Internet-Origin vs VPC-Origin

| AP タイプ | VPC Lambda からのアクセス | 非 VPC Lambda からのアクセス | EC2（パブリックサブネット）からのアクセス |
|---------|----------------------|---------------------------|-------------------------------|
| Internet-origin | ⚠️ Gateway EP 経由でタイムアウトの可能性 | ✅ 動作 | ✅ 動作（IGW 経由） |
| VPC-origin | ✅ 動作（Interface EP 経由） | ❌ 設計上ブロック | ✅ 動作（同一 VPC） |

### 3. AWS サービスアクセスパターン

| サービス | ネットワークパス | FSx for ONTAP S3 AP 互換性 |
|---------|-------------|------------------------|
| Athena | AWS マネージド（顧客 VPC なし） | ✅ Internet-origin 必須 |
| Glue ETL | AWS マネージドまたは VPC アタッチ | ✅ Internet-origin（非 VPC）または NAT Gateway（VPC） |
| EMR Serverless | AWS マネージド | ✅ Internet-origin 必須 |
| Lambda（VPC なし） | インターネット | ✅ Internet-origin で直接動作 |
| Lambda（VPC アタッチ） | VPC ルーティング | ⚠️ NAT Gateway または S3 Gateway EP なしが必要 |
| Redshift Spectrum | AWS マネージド | ✅ Internet-origin 必須 |
| Databricks | Customer-managed VPC | ⚠️ セッションポリシーでブロック（別問題） |

### 4. DNS 解決

FSx for ONTAP S3 AP alias は通常の S3 バケットとは異なる解決をします:

```
通常の S3 バケット:
  my-bucket.s3.ap-northeast-1.amazonaws.com → S3 サービス IP（プレフィックスリスト内）

FSx for ONTAP S3 AP alias:
  my-ap-alias-ext-s3alias.s3.ap-northeast-1.amazonaws.com → s3-r-w.ap-northeast-1.amazonaws.com
```

`s3-r-w` ホスト名は FSx for ONTAP S3 AP バックエンドです。その IP アドレスは、S3 Gateway エンドポイントが使用する S3 プレフィックスリスト（ap-northeast-1 では `pl-61a54008`）に含まれている場合と含まれていない場合があります。

### 5. トラブルシューティングチェックリスト

FSx for ONTAP S3 AP アクセスがタイムアウトする場合:

1. **DNS 解決を確認**: `nslookup <alias>.s3.<region>.amazonaws.com`
2. **TCP 接続性を確認**: `curl -s -o /dev/null -w '%{http_code}' --max-time 5 https://<alias>.s3.<region>.amazonaws.com/`
3. **通常の S3 をテスト**: `aws s3 ls s3://<regular-bucket>/` — これが動作すれば問題は S3 AP 固有
4. **S3 Gateway エンドポイントを確認**: ルートテーブルが Gateway エンドポイントに関連付けられているか？ はいの場合、一時的に削除を試行
5. **AP ライフサイクルを確認**: `aws fsx describe-s3-access-point-attachments` — AVAILABLE であるべき
6. **ボリュームステータスを確認**: `aws fsx describe-volumes --volume-ids <vol-id>` — CREATED/AVAILABLE であるべき
7. **SVM S3 プロトコルを確認**: SVM で S3 プロトコルが有効で、ボリュームがマウントされていることを確認

### 6. VPC 内アクセスの推奨アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│  VPC                                                             │
│                                                                  │
│  ┌──────────────────┐     ┌──────────────────┐                  │
│  │ プライベートサブネット │────▶│ NAT Gateway       │────▶ IGW ──▶ FSx for ONTAP S3 AP
│  │ (Lambda/EC2)      │     │                   │                  │
│  └──────────────────┘     └──────────────────┘                  │
│         │                                                        │
│         │ S3 Gateway EP（通常の S3 バケットアクセス用）            │
│         └──────────────────────────────────────▶ S3 サービス      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

通常の S3 と FSx for ONTAP S3 AP の両方が必要な VPC 内ワークロード向け:
- 通常の S3 バケットアクセスには S3 Gateway エンドポイントを維持（無料、低レイテンシ）
- FSx for ONTAP S3 AP トラフィックは NAT Gateway 経由でルーティング（またはコンピュートを VPC 外に配置）

---

## 7. SVM の DNS/AD 設定と S3 AP 可用性

### 問題: 到達不能な DNS サーバーによる S3 AP ReadTimeout

SVM に DNS サーバーが設定されており（Active Directory ドメイン参加のため）、その DNS サーバーが到達不能になった場合、**その SVM 上の全 S3 Access Point がタイムアウトします** — 以下の条件であっても:
- S3 AP ボリュームが UNIX セキュリティスタイルである
- 顧客設定の FPolicy が無効化されている
- NFS エクスポートポリシーが全アクセスを許可している
- S3 AP のライフサイクル状態が AVAILABLE である

これは、S3 AP リクエスト処理パスが SVM のネームサービススタックを経由するためです。CIFS/AD が設定されている場合、ONTAP はユーザーマッピング解決（UNIX ↔ Windows）を試み、これにドメインコントローラーとの DNS 通信が必要になります。

### 根本原因のメカニズム

```
S3 API リクエスト
  → FSx for ONTAP S3 AP バックエンド
    → SVM ファイルシステムアクセス
      → ONTAP ネームサービススタック (ns-switch: files, dns)
        → CIFS サーバーが存在 → ユーザーマッピングに DC 参照が必要
          → 設定された DNS サーバーに問い合わせ (例: 10.0.x.x)
            → DNS サーバー到達不能 → タイムアウト (30秒以上)
              → S3 API クライアントが ReadTimeout を受信
```

### 認証方式ごとの挙動マトリクス

| SVM 構成 | S3 AP の DNS 依存 | DNS ダウン時の S3 AP 挙動 |
|---|---|---|
| NFS のみ（CIFS なし、DNS なし） | なし | ✅ 正常動作 |
| CIFS ワークグループモード（AD 非参加） | なし | ✅ 正常動作 |
| CIFS + AD ドメイン参加 + DNS 設定 + DNS 到達可能 | あり（透過的） | ✅ 正常動作 |
| CIFS + AD ドメイン参加 + DNS 設定 + **DNS 到達不能** | あり（ブロック） | ❌ ReadTimeout |
| FPolicy 設定あり（任意の状態）+ CIFS/DNS なし | なし | ✅ 正常動作 |

**重要な知見**: DNS 依存は AD ドメインに参加した CIFS サーバーの存在によってトリガーされます。FPolicy、エクスポートポリシー、ボリュームセキュリティスタイルは関係ありません。

### 診断コマンド

```bash
# 1. SVM の DNS 設定を確認
vserver services dns show -vserver <SVM名>

# 2. DNS サーバーの到達性を確認（重要）
vserver services dns check -vserver <SVM名>
# ステータスが "down" または "Operation timed out" → これが原因の可能性が高い

# 3. CIFS/AD メンバーシップを確認
vserver cifs show -vserver <SVM名>

# 4. ns-switch 設定を確認
vserver services name-service ns-switch show -vserver <SVM名>
# hosts データベースのソースに "dns" が含まれているか確認
```

### 解決オプション

**オプション A: DNS と CIFS を削除（AD/SMB が不要な場合）**

```bash
# CIFS を強制削除（AD サーバーが消失している場合、force フラグを使用）
set adv -c off
vserver cifs delete -vserver <SVM名> -admin-username x -admin-password x -force-account-delete true

# DNS 設定を削除
vserver services dns delete -vserver <SVM名>

# ns-switch から DNS を除去
vserver services name-service ns-switch modify -vserver <SVM名> -database hosts -sources files
```

**オプション B: DNS を到達可能なサーバーに変更（AD/SMB が必要な場合）**

```bash
# VPC 提供の DNS（AmazonProvidedDNS）に更新
# VPC CIDR が 10.0.0.0/16 の場合、リゾルバーは 10.0.0.2
vserver services dns modify -vserver <SVM名> -name-servers 10.0.0.2 -domains <ドメイン>
```

注意: オプション B は DNS 解決を復旧しますが、ドメインコントローラーも到達可能でない限り CIFS/AD 認証は失敗します。

**オプション C: AD ドメインコントローラーを復旧**

同じ IP アドレスで AD サーバーを再作成します。最も重い選択肢であり、AD 認証付きの CIFS/SMB アクセスが必要な場合のみ必要です。

### 検証結果（2026-05-24）

| テスト | SVM | DNS 設定 | CIFS/AD | S3 AP 結果 |
|------|-----|-----------|---------|-------------|
| 修正前 | FSxN_OnPre | `<DNS-IP-1>, <DNS-IP-2>`（両方 DOWN） | FPOLICY.LOCAL ドメイン | ❌ ReadTimeout |
| 修正前 | verification-svm | なし | なし | ✅ 即座に成功 |
| 修正後（オプション A） | FSxN_OnPre | 削除済み | 削除済み | ✅ 即座に成功 |

### 予防策

- **孤立した DNS/AD 設定を放置しない。** AD ドメインコントローラーを廃止する場合、SVM から CIFS サーバーと DNS 設定を削除すること。
- **DNS ヘルスを監視する。** 定期的に `vserver services dns check` を実行して DNS サーバーの到達性を確認する。
- **関心の分離。** S3 AP アクセスが主要なユースケースの場合、CIFS/AD 依存のない専用 SVM の使用を検討する。これにより DNS 依存を完全に排除できる。
- **AD サーバーのライフサイクルを文書化する。** どの SVM がどの AD サーバーに依存しているかを追跡し、AD サーバーの廃止時に SVM 設定のクリーンアップをトリガーする。

---

## 参考資料

- [FSx for ONTAP S3 Access Points ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)
- [S3 アクセスポイントのネットワークアクセス設定](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
- [S3 Gateway エンドポイント](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)
- [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns — s3ap-authorization-model.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/s3ap-authorization-model.md)

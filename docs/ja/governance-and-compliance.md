# ガバナンスとコンプライアンス

## 概要

本ドキュメントは、FSx for ONTAP Lakehouse 統合のガバナンス、セキュリティ、コンプライアンスフレームワークを定義します。データ分類、アクセス制御、監査、責任分界を導入判断前に明確にする必要がある規制産業（医療、金融、公共）向けに設計されています。

## データ分類

| 分類 | 説明 | データ例 | アクセス制御 |
|------|------|---------|------------|
| **Public** | 非機密、公開可能 | 集計レポート、公開データセット | Internet-origin AP で読み取り公開 |
| **Internal** | 業務上機密、規制対象外 | 内部分析、運用メトリクス | VPC-origin AP、チームスコープの IAM ロール |
| **Confidential** | 業務上重要、契約上の義務あり | 金融取引、顧客記録 | VPC-origin AP、ユーザー単位 IAM、制限付きファイルシステムユーザー |
| **Regulated** | 法的/規制要件の対象 | PHI（HIPAA）、PII（GDPR）、PCI DSS データ | VPC-origin AP、最小権限 IAM、読み取り専用 AP ユーザー、監査ログ必須 |

## アクセス制御アーキテクチャ

FSx for ONTAP S3 Access Points は**二層認可モデル**を使用します（[ソース](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html)）：

```
┌─────────────────────────────────────────────────────────────────┐
│                    リクエストフロー                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  呼び出し元（IAM プリンシパル）                                    │
│       │                                                           │
│       ▼                                                           │
│  ┌─────────────────────────────────────────┐                     │
│  │  レイヤー 1: AWS IAM 認可                 │                     │
│  │  ─────────────────────────────────────── │                     │
│  │  • IAM アイデンティティポリシー            │                     │
│  │  • S3 Access Point リソースポリシー       │                     │
│  │  • VPC エンドポイントポリシー（該当時）    │                     │
│  │  • サービスコントロールポリシー（SCP）     │                     │
│  │  • ネットワークオリジンチェック（VPC/Internet）│                  │
│  └─────────────────┬───────────────────────┘                     │
│                    │ ALLOW                                         │
│                    ▼                                               │
│  ┌─────────────────────────────────────────┐                     │
│  │  レイヤー 2: ファイルシステム認可          │                     │
│  │  ─────────────────────────────────────── │                     │
│  │  • ファイルシステムユーザー（UNIX/Windows）│                     │
│  │  • UNIX: mode-bits または NFSv4 ACL      │                     │
│  │  • NTFS: Windows ACL                     │                     │
│  │  • ディレクトリ/ファイルレベル権限         │                     │
│  └─────────────────┬───────────────────────┘                     │
│                    │ ALLOW                                         │
│                    ▼                                               │
│              アクセス許可                                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

**両方のレイヤーがリクエストを許可する必要があります。** いずれかのレイヤーでの明示的な Deny は、他のレイヤーの Allow ステートメントを上書きします。

### レイヤー 1: IAM 認可の詳細

| ポリシータイプ | スコープ | 使用例 |
|-------------|--------|--------|
| IAM アイデンティティポリシー | プリンシパル単位（ユーザー/ロール） | アナリストロールに AP への読み取り専用アクセスを付与 |
| アクセスポイントポリシー | アクセスポイント単位 | AP を特定の IAM ロールまたは VPC に制限 |
| VPC エンドポイントポリシー | VPC エンドポイント単位 | VPC からアクセス可能な AP を制限 |
| サービスコントロールポリシー | OU/アカウント単位 | 組織全体の制限を強制 |
| ネットワークオリジン | アクセスポイント単位（作成後変更不可） | VPC-origin: バインドされた VPC 外からの全リクエストを拒否 |

### レイヤー 2: ファイルシステム認可の詳細

| セキュリティスタイル | 権限モデル | ユースケース |
|------------------|-----------|------------|
| UNIX | mode-bits (rwx) または NFSv4 ACL | Linux/NFS ワークロード |
| NTFS | Windows ACL (full/modify/read) | Windows/SMB ワークロード |
| Mixed | UNIX 有効、Windows クライアント用 NTFS | ハイブリッド環境 |

**重要**: アクセスポイントに関連付けられたファイルシステムユーザーが、その AP を通じた全リクエストの権限レベルを決定します。最小権限の原則を使用してください：
- 読み取り専用分析 → 読み取り専用ファイルシステムユーザー
- ETL 書き戻し → 特定ディレクトリにスコープされた読み書きユーザー
- 本番アクセスポイントには root（UID 0）を使用しない

## ネットワークセキュリティ

### Block Public Access

Amazon S3 は FSx for ONTAP ボリュームに接続された全アクセスポイントに対して Block Public Access をデフォルトで強制します。**この設定は変更または無効化できません。**（[ソース](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html)）

### ネットワークオリジンオプション

| オリジン | セキュリティレベル | ユースケース | 制限 |
|---------|----------------|------------|------|
| **VPC** | 最高 | 規制データ、内部分析 | 作成後変更不可。Athena/マネージドサービスからアクセス不可 |
| **Internet** | 標準（IAM 制御） | AWS マネージドサービス（Athena、Bedrock、Glue） | アクセス制御に強力な IAM ポリシーが必要 |

**注**: 「Internet origin」はパブリックアクセスを意味しません。全リクエストに有効な IAM 認証情報が必要です。Block Public Access が匿名アクセスを防止します。（[ソース](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)）

## 監査とログ

| ログソース | キャプチャ対象 | 保持期間 | 用途 |
|-----------|-------------|---------|------|
| **AWS CloudTrail** | FSx API コール（CreateAccessPoint 等）、S3 データイベント（AP 経由の GetObject、PutObject） | 設定可能（コンプライアンスには 1 年以上推奨） | 誰が何にいつどこからアクセスしたか |
| **FSx for ONTAP 監査ログ** | NFS/SMB ファイルアクセスイベント（ONTAP fpolicy/audit 経由） | ONTAP 上で設定可能 | S3 AP を経由しない直接ファイルシステムアクセス |
| **Lakehouse 監査ログ** | クエリ履歴、テーブル変更（プラットフォーム固有） | プラットフォーム依存 | 分析アクティビティ追跡 |
| **VPC フローログ** | FSx ENI へ/からのネットワークトラフィック | 設定可能 | ネットワークレベルのアクセス検証 |
| **S3 Access Point アクセスログ** | CloudTrail 経由の S3 データイベント | CloudTrail と同じ | S3 API レベルのアクセス監査 |

## 暗号化

| レイヤー | メカニズム | 鍵管理 | 備考 |
|---------|----------|--------|------|
| **保存時** | SSE-FSX（自動） | AWS KMS マネージド | 全 FSx ファイルシステムがデフォルトで暗号化。アプリケーションに透過的 |
| **転送中（S3 API）** | TLS 1.2+ | AWS マネージド | S3 API コールに HTTPS 強制 |
| **転送中（NFS）** | Kerberos 暗号化（オプション） | 顧客管理 | 同じデータにアクセスする NFS クライアント用 |
| **転送中（SMB）** | SMB 暗号化（オプション） | 顧客管理 | 同じデータにアクセスする SMB クライアント用 |

**注**: SSE-FSX は S3 Access Points でサポートされる唯一のサーバーサイド暗号化モードです。SSE-S3、SSE-KMS、SSE-C は非サポートです。（[ソース](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)）

## データ所在地

| 観点 | 保証 |
|------|------|
| 保存データ | FSx for ONTAP がデプロイされた AWS リージョンに留まる |
| S3 Access Point | FSx ボリュームと同じリージョンに作成必須（[ソース](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html)） |
| DR レプリケーション | 指定された DR リージョンへの SnapMirror（顧客制御） |
| クエリ結果 | 顧客指定の S3 バケットに書き込み（同一または異なるリージョン） |
| バックアップストレージ | ファイルシステムと同じリージョン、複数 AZ にまたがる冗長性 |

## 責任分界マトリクス（RACI）

| 責任 | AWS | FSx 管理者 | Lakehouse 管理者 | データオーナー |
|------|-----|-----------|-----------------|-------------|
| 物理インフラセキュリティ | **R** | — | — | — |
| FSx ファイルシステム保存時暗号化 | **R** | — | — | — |
| FSx ファイルシステムプロビジョニング | I | **R** | — | — |
| S3 Access Point 作成・ポリシー | I | **R** | C | — |
| 分析用 IAM ロール/ポリシー | I | C | **R** | — |
| ファイルシステムユーザー権限 | I | **R** | C | A |
| データ分類 | — | — | C | **R** |
| Lakehouse テーブルアクセス制御 | — | — | **R** | A |
| 監査ログレビュー | — | C | C | **R** |
| コンプライアンス検証 | — | C | C | **R** |
| インシデント対応 | C | **R** | **R** | A |

R = 実行責任、A = 説明責任、C = 相談、I = 情報提供

## 業界別考慮事項

### 医療（HIPAA）

| 要件 | 実装 |
|------|------|
| PHI アクセス制御 | VPC-origin AP + 最小権限 IAM + 読み取り専用ファイルシステムユーザー |
| 監査証跡 | AP に対する CloudTrail S3 データイベント有効化 |
| 暗号化 | SSE-FSX（保存時）+ TLS（転送中）— 両方自動 |
| データ所在地 | 単一リージョンデプロイ、BAA なしでの PHI クロスリージョンレプリケーション禁止 |
| 匿名化 | 分析アクセス前の匿名化用 Glue ETL パイプライン |
| サンプルデータ | 開発/テストには合成データのみ使用 |

### 金融サービス（PCI DSS / SOX）

| 要件 | 実装 |
|------|------|
| 職務分掌 | 管理者とアナリストで別々の IAM ロール。ドメインごとに別々の AP |
| データメッシュドメインオーナーシップ | ドメインごとの SVM とコンシューマーごとのアクセスポイント |
| 監査保持 | CloudTrail ログを 7 年以上保持（SOX） |
| 変更管理 | Infrastructure as Code（CloudFormation）、PR ベースの変更 |
| DR/BCP | SnapMirror クロスリージョン、文書化された RTO/RPO |

### 製造（OT/IT 境界）

| 要件 | 実装 |
|------|------|
| OT/IT 分離 | OT データ収集と IT 分析で別々の VPC |
| エッジ取り込み | NFS/SMB 書き込み（エッジから）→ S3 AP 読み取り（分析用） |
| 長期保持 | コールドデータの FabricPool 階層化 |
| データ鮮度 | ほぼリアルタイム（NFS 書き込みが S3 AP 経由で即座に可視） |

## セキュアリファレンスデプロイメント: 医療読み取り専用分析

```yaml
# 医療分析向け最小セキュアデプロイメント
Components:
  FSx for ONTAP:
    deployment_type: MULTI_AZ
    throughput_capacity: 512  # MB/s
    storage_capacity: 1024   # GB
    ontap_version: "9.17.1+"
    
  S3 Access Point:
    network_origin: VPC      # プライベートアクセスのみ
    file_system_user: 
      type: UNIX
      username: analytics_reader  # 読み取り専用ユーザー
    block_public_access: true     # 強制（無効化不可）
    
  IAM:
    role: healthcare-analytics-role
    policy:
      - Effect: Allow
        Action: [s3:GetObject, s3:ListBucket]
        Resource: 
          - "arn:aws:s3:REGION:ACCOUNT:accesspoint/healthcare-ap"
          - "arn:aws:s3:REGION:ACCOUNT:accesspoint/healthcare-ap/object/*"
      # PutObject、DeleteObject なし — 読み取り専用
      
  VPC:
    endpoint_type: Gateway  # VPC 内分析用
    endpoint_policy: healthcare-ap のみにスコープ
    
  Audit:
    cloudtrail: 
      data_events: enabled
      resource: "arn:aws:s3:REGION:ACCOUNT:accesspoint/healthcare-ap"
      retention: 7_years
      
  Data:
    type: 合成データのみ（開発/テストに実際の PHI を使用しない）
    format: Parquet（匿名化済み）
```

## デプロイ前チェックリスト

### 医療
- [ ] 匿名化パイプラインの検証
- [ ] サンプル/テストデータに PHI がないことの確認
- [ ] VPC-origin アクセスポイント（Athena/マネージドサービスを使用しない場合）
- [ ] 読み取り専用ファイルシステムユーザー
- [ ] CloudTrail S3 データイベント有効化
- [ ] 監査ログ保持期間の設定（7 年以上）
- [ ] AWS との BAA 締結
- [ ] データ所在地の確認（単一リージョン）

### 金融サービス
- [ ] 職務分掌の検証（管理者 ≠ アナリストロール）
- [ ] ドメインごとのアクセスポイント（スコープ付きポリシー）
- [ ] CloudTrail 有効化（長期保持）
- [ ] SnapMirror DR の設定とテスト
- [ ] 変更管理プロセスの文書化
- [ ] 暗号化の検証（保存時 + 転送中）

### 製造
- [ ] OT/IT ネットワーク分離の確認
- [ ] エッジデータ取り込みパスの検証
- [ ] データ鮮度 SLA の文書化
- [ ] 長期保持ポリシーの設定（FabricPool）

## 参考資料

- [アクセスポイントアクセスの管理 — 二層認可](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-ap-manage-access-fsxn.html)
- [S3 アクセスポイントのネットワークアクセス設定](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
- [アクセスポイントの互換性](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)
- [CloudTrail による FSx for ONTAP API コールのモニタリング](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/logging-using-cloudtrail-win.html)
- [アクセスポイントの命名規則、制限事項](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-point-for-fsxn-restrictions-limitations-naming-rules.html)

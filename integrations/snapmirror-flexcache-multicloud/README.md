> 🌐 Language: **日本語** | [English](docs/en/README.md)

# S3 AP + SnapMirror + FlexCache マルチクラウドデータ配信

> FSx for ONTAP S3 Access Point 経由で収集されたデータを SnapMirror/FlexCache でマルチクラウド配信し、宛先で NFS/SMB 認証アクセスを実現するフィージビリティ調査・検証プロジェクト

## 概要

Amazon FSx for NetApp ONTAP の S3 Access Point（FSx for ONTAP S3 AP）を利用して S3 API でデータを収集し、そのデータを SnapMirror および FlexCache で以下の宛先に配信するユースケースを調査・検証する:

- FSx for ONTAP（同一/別リージョン）
- On-premises ONTAP
- Cloud Volumes ONTAP on GCP / Azure
- Google Cloud NetApp Volumes (GCNV)

宛先では NFS/SMB プロトコルによるセキュアなファイルレベル認証アクセスを提供する。

### FlexCache vs SnapMirror — 用途に応じて選択

- **FlexCache**: リモートサイトでの読み取り高速化。Origin データのキャッシュを配置し、ローカル速度で NFS/SMB read を提供。ストレージ効率が高い（アクセスされたデータのみキャッシュ）
- **SnapMirror**: DR（災害復旧）/ データ移行。宛先にフルコピーを作成し、フェイルオーバー可能。RPO 5 分以上

## 現在のステータス

| フェーズ | 状態 | 説明 |
|:-------:|:----:|------|
| 1. 調査 | ✅ 完了 | 41 項目の調査結果（32 サポート確認、3 条件付き、2+4 注意事項あり、1 未文書化、2 非サポート） |
| 2. 文書化 | ✅ 完了 | 調査ドキュメント (JA/EN)、検証計画、バージョンマトリクス |
| 3. 検証 | ✅ 完了 | TC-01〜TC-05（同一クラスター内）全 PASS。Cross-region E2E 検証済み（2026-07-22） |
| 4. ステークホルダー連携 | ✅ 完了 | Feature Request (3)、Stakeholder Brief (4)、分類マトリクス |

## ディレクトリ構成

```
integrations/snapmirror-flexcache-multicloud/
├── README.md                           # 本ファイル（日本語）
├── docs/en/README.md                   # 英語版
├── template.yaml                       # CloudFormation: クラスター間検証スタック
├── docs/
│   ├── ja/                             # 日本語ドキュメント
│   │   ├── research.md                 # 調査ドキュメント（41 Findings、~2400 行）
│   │   ├── validation-plan.md          # 検証計画（8 テストケース、~1400 行）
│   │   └── demo-guide-00〜11.md        # デモガイド 12 本
│   ├── en/                             # 英語ドキュメント
│   │   ├── README.md                   # 英語版 README
│   │   ├── research.md                 # 調査ドキュメント英語版（~730 行）
│   │   └── demo-guide-00〜11.md        # デモガイド 12 本
│   └── finding-classification-routing.md  # Phase 4: 4 分類 + ルーティング
├── scripts/validation/                 # 検証スクリプト（自動デプロイ/テスト/削除）
│   ├── tc09-deploy-validate-teardown.sh  # TC-09 ワンコマンド E2E
│   ├── cross-region-deploy.sh            # Cross-region インフラ構築
│   ├── cross-region-test.sh              # Cross-region FlexCache + SnapMirror テスト
│   ├── cross-region-teardown.sh          # ⚠️ 安全な削除（SM-VAL-011 準拠）
│   ├── setup-intercluster.sh             # クラスター間 ONTAP セットアップ
│   └── teardown-intercluster.sh          # クラスター間クリーンアップ
├── feature-requests/                   # Feature Request テンプレート
└── stakeholder-briefs/                 # ステークホルダー向け文書
```

## 主要な調査・検証結果

| トピック | 状態 | 備考 |
|---------|:----:|------|
| S3 AP ボリュームを SnapMirror Async ソースに | ✅ 検証済み | S3 NAS bucket メカニズムにより Volume-level レプリケーション可能 |
| SnapMirror failover 後の S3 AP 再アタッチ | ✅ 検証済み | break → junction path → ~60s → S3 AP 作成。Cross-region RTO ~3 分 |
| S3 AP 付き SVM の SVM-DR | ❌ 非サポート | Volume-level SnapMirror のみ。宛先 SVM 構成は手動 |
| FSx for ONTAP → ANF（SnapMirror） | ❌ 非サポート | ANF は外部 Cluster Peering 不可。CVO on Azure 経由で代替 |
| S3 AP ボリュームを FlexCache Origin に | ✅ 検証済み | ONTAP 9.17.1 で確認（同一クラスター + cross-region） |
| FlexCache write-back + S3 AP | ⚠️ 注意事項あり | 動作するが、S3 AP Origin 書き込みが Cache XLD を revoke（同一ファイル同時書き込みにデータ損失リスク） |
| クロスクラウド暗号化 | ✅ 確認済み | Cluster Peering Encryption（TLS 1.2）デフォルト有効 |
| SnapMirror データ整合性 | ✅ 確認済み | WAFL 原子性 + crash-consistent Snapshot が全パスを保護 |

凡例: ✅ 確認済み/検証済み | ❌ 非サポート | ⚠️ 動作するが注意事項あり

## はじめ方

```bash
# 1. リポジトリをクローン
git clone https://github.com/Yoshiki0705/fsxn-lakehouse-integrations.git
cd fsxn-lakehouse-integrations/integrations/snapmirror-flexcache-multicloud

# 2. パラメータをコピーして編集
cp scripts/validation/cross-region-params.env.example scripts/validation/cross-region-params.env
# 編集: FS_ID_A, VPC_ID_A, SECRET_ARN_A, SVM_NAME_A, REGION_B, FSX_PASSWORD_B

# 3. Cross-region インフラをデプロイ（VPC B + Peering + FSx B）
./scripts/validation/cross-region-deploy.sh deploy    # ~50 分（FSx 作成含む）

# 4. Cross-region FlexCache + SnapMirror テスト実行
./scripts/validation/cross-region-test.sh             # ~15 分

# 5. 安全な削除（SM-VAL-011 の順序に従う）
./scripts/validation/cross-region-teardown.sh         # ~35 分
```

> ⚠️ **前提条件**: `sshpass` が必要（`brew install sshpass` または `apt install sshpass`）。削除スクリプトは SSH 経由で `vserver peer delete` と `snapmirror release` を実行する。REST API では信頼性の高い two-phase cleanup が行えないため CLI アクセスが必要。

## デモガイド一覧

> ⏱️ 所要時間は FSx for ONTAP がデプロイ済みの前提。新規作成から始める場合は +30 分程度。

### FlexCache パターン

| # | ガイド | パターン | ネットワーク | 所要時間 |
|:-:|--------|---------|:----------:|:-------:|
| 00 | [共通前提条件](docs/ja/demo-guide-00-prerequisites.md) | — | — | — |
| 01 | [FlexCache 同一リージョン](docs/ja/demo-guide-01-flexcache-same-region.md) | FSx → FSx（同一リージョン） | VPC | ~45分 |
| 02 | [FlexCache クロスリージョン](docs/ja/demo-guide-02-flexcache-cross-region.md) | FSx → FSx（別リージョン） | VPC Peering | ~60分 |
| 03 | [FlexCache オンプレミス](docs/ja/demo-guide-03-flexcache-on-premises.md) | FSx → オンプレ ONTAP | DX / VPN | ~90分 |
| 04 | [FlexCache CVO on GCP](docs/ja/demo-guide-04-flexcache-cvo-gcp.md) | FSx → CVO on GCP | HA VPN | ~120分 |
| 05 | [FlexCache CVO on Azure](docs/ja/demo-guide-05-flexcache-cvo-azure.md) | FSx → CVO on Azure | Azure VPN GW | ~120分 |
| 06 | [FlexCache GCNV](docs/ja/demo-guide-06-flexcache-gcnv.md) | FSx → GCNV（Cache のみ） | HA VPN | ~90分 |

### SnapMirror パターン

| # | ガイド | パターン | ネットワーク | 所要時間 |
|:-:|--------|---------|:----------:|:-------:|
| 07 | [SnapMirror クロスリージョン](docs/ja/demo-guide-07-snapmirror-cross-region.md) | FSx → FSx（DR + S3 AP 再アタッチ） | VPC Peering | ~60分 |
| 08 | [SnapMirror オンプレミス](docs/ja/demo-guide-08-snapmirror-on-premises.md) | FSx → オンプレ ONTAP | DX / VPN | ~60分 |
| 09 | [SnapMirror CVO on GCP](docs/ja/demo-guide-09-snapmirror-cvo-gcp.md) | FSx → CVO on GCP | HA VPN | ~120分 |
| 10 | [SnapMirror CVO on Azure](docs/ja/demo-guide-10-snapmirror-cvo-azure.md) | FSx → CVO on Azure | Azure VPN GW | ~120分 |
| 11 | [SnapMirror GCNV](docs/ja/demo-guide-11-snapmirror-gcnv.md) | FSx → GCNV（External Replication） | HA VPN | ~90分 |

### パス選択ガイド

```
どのパターンを使うべきか？

├─ 宛先が AWS 内
│   ├─ 同一リージョン → Guide 01 (FlexCache) or Guide 07 (SnapMirror DR)
│   └─ 別リージョン → Guide 02 (FlexCache) or Guide 07 (SnapMirror DR)
│
├─ 宛先がオンプレミス
│   ├─ 読み取り高速化 → Guide 03 (FlexCache, RTT < 200ms 推奨)
│   └─ DR / データ移行 → Guide 08 (SnapMirror)
│
├─ 宛先が GCP
│   ├─ フル ONTAP 機能が必要 → Guide 04 (FlexCache CVO) or Guide 09 (SnapMirror CVO)
│   ├─ マネージドで手軽に → Guide 06 (FlexCache GCNV, read-only)
│   └─ マネージドで DR → Guide 11 (SnapMirror GCNV External Replication)
│
└─ 宛先が Azure
    ├─ CVO 利用可能 → Guide 05 (FlexCache CVO) or Guide 10 (SnapMirror CVO)
    └─ ANF を使いたい → ❌ 直接 SnapMirror 未サポート (XC-007)。CVO 経由で代替。
```

## 関連リンク

- [FSx for ONTAP S3 AP ネットワーキング](../../docs/ja/fsx-ontap-s3ap-networking.md)
- [調査ドキュメント（日本語）](docs/ja/research.md)
- [検証計画](docs/ja/validation-plan.md)
- [Spec 定義](../../.kiro/specs/s3ap-snapmirror-flexcache-multicloud/)

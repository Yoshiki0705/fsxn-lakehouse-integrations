# S3 AP + SnapMirror + FlexCache Multi-Cloud Data Distribution

> FSx for ONTAP S3 Access Point 経由で収集されたデータを SnapMirror/FlexCache でマルチクラウド配信し、宛先で NFS/SMB 認証アクセスを実現するフィージビリティ調査・検証プロジェクト

## Overview

Amazon FSx for NetApp ONTAP の S3 Access Point（FSx for ONTAP S3 AP）を利用して S3 API でデータを収集し、そのデータを SnapMirror および FlexCache で以下の宛先に配信するユースケースを調査・検証する:

- FSx for ONTAP（同一/別リージョン）
- On-premises ONTAP
- Cloud Volumes ONTAP on GCP / Azure
- Google Cloud NetApp Volumes (GCNV)

宛先では NFS/SMB プロトコルによるセキュアなファイルレベル認証アクセスを提供する。

### FlexCache vs SnapMirror — When to use which

- **FlexCache**: リモートサイトでの読み取り高速化。Origin データのキャッシュを配置し、ローカル速度で NFS/SMB read を提供。ストレージ効率が高い（アクセスされたデータのみキャッシュ）
- **SnapMirror**: DR（災害復旧）/ データ移行。宛先にフルコピーを作成し、フェイルオーバー可能。RPO 5 分以上

## Status

| Phase | Status | Description |
|:-----:|:------:|-------------|
| 1. Research | ✅ Complete | 41 Findings (32 supported, 3 partial, 2 caveats, 2 undocumented, 2 unsupported) |
| 2. Documentation | ✅ Complete | Research Document (JA/EN), Validation Plan, Version Matrix |
| 3. Validation | ✅ Complete | TC-01〜TC-05 executed (intra-cluster). All PASS. |
| 4. Communication | ✅ Complete | Feature Requests (3), Stakeholder Briefs (4), Classification Matrix |

## Directory Structure

```
integrations/snapmirror-flexcache-multicloud/
├── README.md                           # This file
├── template.yaml                       # CloudFormation: inter-cluster validation stack
├── docs/
│   ├── demo-guide-00-prerequisites.md  # 共通前提条件
│   ├── demo-guide-01-flexcache-same-region.md      # FlexCache 同一リージョン (NFS + SMB)
│   ├── demo-guide-02-flexcache-cross-region.md     # FlexCache クロスリージョン
│   ├── demo-guide-03-flexcache-on-premises.md      # FlexCache オンプレミス
│   ├── demo-guide-04-flexcache-cvo-gcp.md          # FlexCache CVO on GCP
│   ├── demo-guide-05-flexcache-cvo-azure.md        # FlexCache CVO on Azure
│   ├── demo-guide-06-flexcache-gcnv.md             # FlexCache GCNV (Cache only)
│   ├── demo-guide-07-snapmirror-cross-region.md    # SnapMirror クロスリージョン + S3 AP 再アタッチ
│   ├── demo-guide-08-snapmirror-on-premises.md     # SnapMirror オンプレミス DR
│   ├── demo-guide-09-snapmirror-cvo-gcp.md         # SnapMirror CVO on GCP
│   ├── demo-guide-10-snapmirror-cvo-azure.md       # SnapMirror CVO on Azure
│   ├── demo-guide-11-snapmirror-gcnv.md            # SnapMirror GCNV External Replication
│   ├── tc09-lambda-s3ap-flexcache-smb-nfs.md       # TC-09 テストプラン
│   ├── tc09-results.md                             # TC-09 結果テンプレート
│   ├── ja/
│   │   ├── research.md                 # Research Document (41 Findings, ~2300 lines)
│   │   └── validation-plan.md          # Validation Plan (8 Test Cases, ~1400 lines)
│   ├── en/
│   │   └── research.md                 # EN full version (41 Findings, ~630 lines)
│   └── finding-classification-routing.md  # Phase 4: 4-category classification + routing
├── scripts/
│   └── validation/                     # Validation scripts (automated deploy/test/teardown)
│       ├── tc09-deploy-validate-teardown.sh  # TC-09 one-command E2E script
│       ├── params.env.example                # TC-09 parameters template
│       ├── cross-region-deploy.sh            # Cross-region infra creation
│       ├── cross-region-test.sh              # Cross-region FlexCache + SnapMirror test
│       ├── cross-region-teardown.sh          # ⚠️ Safe teardown (SM-VAL-011 order)
│       ├── cross-region-params.env.example   # Cross-region parameters template
│       ├── on-premises-test.sh               # On-premises validation (template)
│       ├── on-premises-params.env.example    # On-premises parameters
│       ├── cvo-gcp-test.sh                   # CVO on GCP validation (template)
│       ├── cvo-gcp-params.env.example        # CVO GCP parameters
│       ├── cvo-azure-test.sh                 # CVO on Azure validation (template)
│       ├── cvo-azure-params.env.example      # CVO Azure parameters
│       ├── gcnv-test.sh                      # GCNV validation (template)
│       ├── gcnv-params.env.example           # GCNV parameters
│       ├── setup-intercluster.sh             # Inter-cluster ONTAP setup
│       └── teardown-intercluster.sh          # Inter-cluster cleanup
├── feature-requests/                   # Phase 4: Feature Request templates
│   ├── aws-fsx-pm/
│   │   └── SM-004-svm-dr-s3-nas-bucket.md
│   └── netapp-bu/
│       ├── XC-007-anf-external-cluster-peering.md
│       └── FC-004-writeback-xld-s3ap-documentation.md
└── stakeholder-briefs/                 # Phase 4: Communication artifacts
    ├── 01-aws-fsx-pm-brief.md
    ├── 02-netapp-bu-engineering-brief.md
    ├── 03-aws-community-public-summary.md
    └── 04-netapp-field-tmc-ctc-brief.md
```

## Key Findings

| Topic | Status | Notes |
|-------|:------:|-------|
| S3 AP volume as SnapMirror Async source | ✅ Validated | S3 NAS bucket mechanism enables volume-level replication |
| S3 AP re-attach after SnapMirror failover | ✅ Validated | break → junction path → ~60s → create S3 AP |
| SVM-DR with S3 AP | ❌ | Volume-level SnapMirror only. Destination SVM config manual |
| FSx for ONTAP → ANF (SnapMirror) | ❌ | ANF has no external Cluster Peering. Use CVO on Azure |
| S3 AP volume as FlexCache Origin | ✅ Validated | Confirmed on ONTAP 9.17.1 (intra-cluster) |
| FlexCache write-back + S3 AP | ⚠️ Caveats | Works, but S3 AP Origin write revokes Cache XLD (data loss risk on same file) |
| Cross-cloud encryption | ✅ | Cluster Peering Encryption (TLS 1.2) default enabled |
| SnapMirror data integrity | ✅ | WAFL atomicity + crash-consistent Snapshot protects all paths |

Legend: ✅ Confirmed/Validated | ❌ Unsupported | ⚠️ Works with caveats

## Demo Guides（デモガイド一覧）

> 📖 Each guide is available in Japanese and English.
> 各ガイドは日本語・英語の両方があります。
>
> ⏱️ Estimated times assume FSx for ONTAP is already deployed. Add ~30 minutes for initial FSx for ONTAP creation if starting from scratch.

### Getting Started

```bash
# 1. Clone the repository
git clone https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns.git
cd FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/integrations/snapmirror-flexcache-multicloud

# 2. Copy and edit parameters
cp scripts/validation/cross-region-params.env.example scripts/validation/cross-region-params.env
# Edit: FS_ID_A, VPC_ID_A, SECRET_ARN_A, SVM_NAME_A, REGION_B, FSX_PASSWORD_B

# 3. Deploy cross-region infrastructure (VPC B + Peering + FSx B)
./scripts/validation/cross-region-deploy.sh deploy    # ~50 min (FSx creation)

# 4. Run cross-region FlexCache + SnapMirror test
./scripts/validation/cross-region-test.sh             # ~15 min

# 5. Safe teardown (CRITICAL: follows SM-VAL-011 order)
./scripts/validation/cross-region-teardown.sh         # ~35 min
```

> ⚠️ **Prerequisites**: `sshpass` must be installed (`brew install sshpass` or `apt install sshpass`) for ONTAP CLI access during teardown. The safe teardown script uses SSH to execute `vserver peer delete` and `snapmirror release` — operations that require CLI access rather than REST API for reliable two-phase cleanup.

### FlexCache Patterns / FlexCache パターン

| # | JA | EN | Pattern | Network | Time |
|:-:|----|----|---------|---------|:----:|
| 00 | [共通前提条件](docs/ja/demo-guide-00-prerequisites.md) | [Prerequisites](docs/en/demo-guide-00-prerequisites.md) | — | — | — |
| 01 | [FlexCache 同一リージョン](docs/ja/demo-guide-01-flexcache-same-region.md) | [Same Region](docs/en/demo-guide-01-flexcache-same-region.md) | FSx → FSx (same region) | VPC | ~45min |
| 02 | [FlexCache クロスリージョン](docs/ja/demo-guide-02-flexcache-cross-region.md) | [Cross-Region](docs/en/demo-guide-02-flexcache-cross-region.md) | FSx → FSx (cross-region) | VPC Peering | ~60min |
| 03 | [FlexCache オンプレミス](docs/ja/demo-guide-03-flexcache-on-premises.md) | [On-Premises](docs/en/demo-guide-03-flexcache-on-premises.md) | FSx → On-prem ONTAP | DX / VPN | ~90min |
| 04 | [FlexCache CVO on GCP](docs/ja/demo-guide-04-flexcache-cvo-gcp.md) | [CVO GCP](docs/en/demo-guide-04-flexcache-cvo-gcp.md) | FSx → CVO on GCP | HA VPN | ~120min |
| 05 | [FlexCache CVO on Azure](docs/ja/demo-guide-05-flexcache-cvo-azure.md) | [CVO Azure](docs/en/demo-guide-05-flexcache-cvo-azure.md) | FSx → CVO on Azure | Azure VPN GW | ~120min |
| 06 | [FlexCache GCNV](docs/ja/demo-guide-06-flexcache-gcnv.md) | [GCNV](docs/en/demo-guide-06-flexcache-gcnv.md) | FSx → GCNV (Cache only) | HA VPN | ~90min |

### SnapMirror Patterns / SnapMirror パターン

| # | JA | EN | Pattern | Network | Time |
|:-:|----|----|---------|---------|:----:|
| 07 | [SnapMirror クロスリージョン](docs/ja/demo-guide-07-snapmirror-cross-region.md) | [Cross-Region DR](docs/en/demo-guide-07-snapmirror-cross-region.md) | FSx → FSx (DR + S3 AP re-attach) | VPC Peering | ~60min |
| 08 | [SnapMirror オンプレミス](docs/ja/demo-guide-08-snapmirror-on-premises.md) | [On-Premises](docs/en/demo-guide-08-snapmirror-on-premises.md) | FSx → On-prem ONTAP | DX / VPN | ~60min |
| 09 | [SnapMirror CVO on GCP](docs/ja/demo-guide-09-snapmirror-cvo-gcp.md) | [CVO GCP](docs/en/demo-guide-09-snapmirror-cvo-gcp.md) | FSx → CVO on GCP | HA VPN | ~120min |
| 10 | [SnapMirror CVO on Azure](docs/ja/demo-guide-10-snapmirror-cvo-azure.md) | [CVO Azure](docs/en/demo-guide-10-snapmirror-cvo-azure.md) | FSx → CVO on Azure | Azure VPN GW | ~120min |
| 11 | [SnapMirror GCNV](docs/ja/demo-guide-11-snapmirror-gcnv.md) | [GCNV](docs/en/demo-guide-11-snapmirror-gcnv.md) | FSx → GCNV (External Repl.) | HA VPN | ~90min |

### Path Selection Guide / パス選択ガイド

```
どのパターンを使うべきか？

├─ 宛先が AWS 内
│   ├─ 同一リージョン → Guide 01 (FlexCache) or Guide 07 (SnapMirror DR)
│   └─ 別リージョン → Guide 02 (FlexCache) or Guide 07 (SnapMirror DR)
│
├─ 宛先がオンプレミス
│   ├─ 読み取り高速化 → Guide 03 (FlexCache, RTT < 200ms)
│   └─ DR/データ移行 → Guide 08 (SnapMirror)
│
├─ 宛先が GCP
│   ├─ フルONTAP機能が必要 → Guide 04 (FlexCache CVO) or Guide 09 (SnapMirror CVO)
│   ├─ マネージドで手軽に → Guide 06 (FlexCache GCNV, read-only)
│   └─ マネージドでDR → Guide 11 (SnapMirror GCNV External Replication)
│
└─ 宛先が Azure
    ├─ CVO 利用可能 → Guide 05 (FlexCache CVO) or Guide 10 (SnapMirror CVO)
    └─ ANF を使いたい → ❌ 直接 SnapMirror 未サポート (XC-007)。CVO 経由で。
```

## Spec

Spec definition: `.kiro/specs/s3ap-snapmirror-flexcache-multicloud/`

## Related

- [FSx for ONTAP S3 AP Networking](../../docs/en/fsx-ontap-s3ap-networking.md)
- [Verification Pack: SnapMirror S3](../../verification-pack/snapmirror-s3/)

# パートナーオファリングガイド

## 対象顧客

| セグメント | プロファイル | 課題 |
|-----------|------------|------|
| エンタープライズ NAS ユーザー | オンプレミス NetApp ONTAP / NAS で 10TB+ のファイルデータを保有 | 分析にデータコピーが必要、S3 ネイティブサービスから NAS にアクセス不可 |
| FSx for ONTAP 利用企業 | NFS/SMB ワークロードで FSx for ONTAP を既に利用中 | Lakehouse/分析プラットフォームが S3 を要求し、データサイロが発生 |
| ハイブリッドクラウド | オンプレミス ONTAP + AWS、SnapMirror で DR/移行中 | ストレージ再設計なしでクラウド分析を活用したい |

## ビジネス課題

NAS/ONTAP 上にファイルベースのデータを持つ組織は、根本的な断絶に直面しています：

1. **データ重複**: 分析プラットフォーム（Databricks、Snowflake、Athena）が S3 上のデータを要求し、NAS から S3 へのコピーパイプラインが必要
2. **ガバナンス分断**: NAS（UNIX/NTFS 権限）と S3（IAM ポリシー）で別々のアクセス制御が存在し、コンプライアンスギャップが発生
3. **運用オーバーヘッド**: 同期パイプラインがレイテンシ、コスト、障害点を追加
4. **投資の無駄**: データを S3 にコピーすると、既存の ONTAP 機能（重複排除、スナップショット、階層化）が活用できない

## ソリューション: FSx for ONTAP + S3 Access Points + Lakehouse 統合

Amazon FSx for ONTAP S3 Access Points により、FSx for ONTAP ボリューム上のファイルデータにデータ移動なしで S3 API アクセスが可能になります。S3 と連携するアプリケーションや AWS サービスが、アクセスポイント経由でファイルデータを直接読み書きできます。

**主要な技術仕様**（[AWS ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)より）：
- サポートされる S3 操作: GetObject, PutObject, DeleteObject, ListObjectsV2, HeadObject, Multipart Upload, CopyObject（同一アクセスポイント内のみ）
- 二層認可: IAM ポリシー評価 + ファイルシステムユーザー権限（UNIX または Windows）
- レイテンシ: 数十ミリ秒（S3 バケットアクセスと同等）
- スループット: FSx for ONTAP ファイルシステムのプロビジョンドスループット容量に依存
- Block Public Access がデフォルトで強制（無効化不可）
- ONTAP バージョン 9.17.1 以降が必要

## ビジネス成果

| 成果 | 指標 |
|------|------|
| データコピーの排除 | N 個のコピー → 1 つの正規ソース |
| 同期パイプラインの廃止 | NAS → S3 ETL ジョブの排除 |
| インサイトまでの時間短縮 | パイプライン構築に数日 → 直接クエリで数時間 |
| NFS/SMB アクセスの維持 | 既存ワークロードは変更不要 |
| ガバナンスの統一 | 単一データ所在地、二層アクセス制御 |
| ファイルデータでの AI/ML 活用 | Bedrock、SageMaker、EMR が S3 AP 経由でアクセス |

## Good / Better / Best 構成

### Good: 単一アカウント・読み取り専用分析

**スコープ**: 単一 AWS アカウント、単一 SVM、読み取り専用分析

| コンポーネント | 構成 |
|--------------|------|
| FSx for ONTAP | Single-AZ、1 SVM、1 ボリューム |
| S3 Access Point | Internet origin、読み取り専用ファイルシステムユーザー |
| 分析 | Athena + Glue Data Catalog |
| セキュリティ | 分析チームごとの IAM ロール、読み取り専用 UNIX ユーザー |
| モニタリング | CloudTrail による API コール記録 |

**ユースケース**: データ移動なしでファイルデータ（CSV、Parquet、JSON）に対するアドホック SQL クエリ

**検証済み AWS 統合**: [Amazon Athena で SQL によるファイルクエリ](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

---

### Better: VPC 制限付きアクセスとカタログ統合

**スコープ**: VPC 制限付きアクセス、Glue Catalog / Unity Catalog 統合、ETL 用読み書き

| コンポーネント | 構成 |
|--------------|------|
| FSx for ONTAP | Single-AZ または Multi-AZ、複数ボリューム |
| S3 Access Point | VPC origin（特定 VPC にバインド）、読み書きファイルシステムユーザー |
| 分析 | Databricks Unity Catalog / Snowflake External Stage / Glue ETL |
| セキュリティ | VPC エンドポイントポリシー + アクセスポイントポリシー + ファイルシステム権限 |
| ネットワーク | Gateway エンドポイント（VPC 内）+ Interface エンドポイント（Direct Connect 経由オンプレミス） |
| モニタリング | CloudTrail + CloudWatch メトリクス |

**ユースケース**: FSx for ONTAP からソースデータを読み取り、Glue/EMR で変換し、加工済み結果を書き戻す ETL パイプライン

**検証済み AWS 統合**:
- [AWS Glue を使用した ETL パイプライン構築](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)
- [Amazon EMR Serverless での Spark ジョブ実行](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-run-spark-with-emr-serverless.html)

---

### Best: マルチアカウントガバナンス + DR + AI

**スコープ**: マルチアカウント、Lake Formation / IAM / S3 AP ポリシー、SnapMirror DR、監査ログ、AI/RAG

| コンポーネント | 構成 |
|--------------|------|
| FSx for ONTAP | Multi-AZ、複数 SVM、DR リージョンへの SnapMirror |
| S3 Access Points | コンシューマーごとのアクセスポイント（スコープ付き IAM ポリシー） |
| 分析 | Databricks + Snowflake + Athena（マルチプラットフォーム） |
| AI/ML | Amazon Bedrock Knowledge Bases による RAG |
| セキュリティ | Lake Formation + S3 AP ポリシー + VPC origin + ファイルシステム ACL |
| ガバナンス | CloudTrail、ONTAP 監査ログ、データ分類タグ |
| DR | SnapMirror クロスリージョンレプリケーション、ONTAP Snapshots |

**ユースケース**: ドメイン固有のアクセスポイントによるエンタープライズデータメッシュ、AI ドキュメント検索、規制データガバナンス

**検証済み AWS 統合**:
- [Amazon Bedrock Knowledge Bases を使用した RAG アプリケーション構築](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)
- Good / Better ティアの全統合

---

## 販売可能なユースケース名

| ユースケース名 | 業界 | パターン | ティア |
|--------------|------|---------|-------|
| Zero-Copy NAS Analytics for Manufacturing | 製造 | 読み取り専用分析 | Good |
| Regulated Data Lakehouse for Healthcare Research | 医療 | マネージドテーブル（読み取り） | Better |
| Financial Data Mesh with FSx for ONTAP and S3 Access Points | 金融 | データ共有 | Best |
| AI-Powered Document Intelligence on Enterprise Files | 全業界 | Bedrock RAG | Best |
| Hybrid Cloud Analytics Bridge | 全業界 | ETL パイプライン | Better |
| Media Asset Analytics without Data Migration | メディア | 読み取り専用分析 | Good |

## ユースケース別導入ステップ

### Zero-Copy NAS Analytics for Manufacturing

| ステップ | アクション | タイムライン |
|---------|----------|------------|
| 1 | FSx for ONTAP + S3 Access Point のデプロイ | Day 1-2 |
| 2 | Glue Crawler の設定 | Day 2 |
| 3 | サンプルデータでの Athena クエリ検証 | Day 3 |
| 4 | BI ツール（QuickSight）接続 | Day 4-5 |
| **成功基準** | 1GB データセットに対するクエリレイテンシ < 10 秒、データコピーゼロ | |

### Regulated Data Lakehouse for Healthcare Research

| ステップ | アクション | タイムライン |
|---------|----------|------------|
| 1 | Multi-AZ FSx for ONTAP + VPC-origin S3 AP のデプロイ | Week 1 |
| 2 | Lake Formation 権限の設定 | Week 1 |
| 3 | 匿名化パイプライン用 Glue ETL のセットアップ | Week 2 |
| 4 | 分析プラットフォームへの外部テーブル登録 | Week 2 |
| 5 | 監査証跡とアクセス制御の検証 | Week 3 |
| **成功基準** | PHI が VPC 外に出ない、監査証跡が完全、クエリ < 30 秒 | |

### Financial Data Mesh with FSx for ONTAP and S3 Access Points

| ステップ | アクション | タイムライン |
|---------|----------|------------|
| 1 | ドメインごとの SVM によるマルチアカウントセットアップ | Week 1-2 |
| 2 | コンシューマーごとの S3 Access Points（スコープ付きポリシー） | Week 2-3 |
| 3 | クロスアカウント IAM ロールと VPC エンドポイント | Week 3 |
| 4 | SnapMirror DR 設定 | Week 4 |
| 5 | Databricks Unity Catalog + Snowflake External Stage | Week 4-5 |
| **成功基準** | ドメイン分離の検証、DR RTO < 1 時間、マルチプラットフォームクエリ | |

---

## パートナーモーション

### 本オファリングの販売主体

| パートナータイプ | 役割 | 価値提案 | 典型的な案件 |
|---------------|------|---------|------------|
| **SIer / コンサルティング** | 設計 + 実装 + 移行 | NAS モダナイゼーション / データプラットフォーム刷新プロジェクト | 既存 ONTAP 顧客のクラウド分析へのアップグレード |
| **MSP (Managed Service Provider)** | 運用 + 監視 + 最適化 | FSx for ONTAP + S3 AP + 監査のマネージドサービス | 規制業界向け継続運用 |
| **Data / AI パートナー** | 分析 + AI ソリューション構築 | Bedrock RAG / Athena / Glue / Databricks 統合 | AI ドキュメントインテリジェンス、データメッシュ |
| **NetApp チャネルパートナー** | ONTAP 投資をクラウド分析に拡張 | 既存 ONTAP 顧客基盤の AWS 分析への拡大 | ハイブリッドクラウド分析ブリッジ |
| **ISV** | FSx for ONTAP S3 AP を製品に組み込み | データコピーなしの S3 互換製品統合 | 顧客ファイルデータ上の SaaS 分析 |

### パートナーエンゲージメントモデル

```
Discovery → Assessment → PoC → Production → Managed Operations
    │            │          │         │              │
    ▼            ▼          ▼         ▼              ▼
  SIer/       SIer/      SIer/     SIer/          MSP
  NetApp      NetApp     Data/AI   Data/AI
  Partner     Partner    Partner   Partner
```

### パートナーイネーブルメントチェックリスト

- [ ] FSx for ONTAP S3 Access Points 技術トレーニングの完了
- [ ] 互換性マトリクスのレビュー（動作するものと動作しないものの理解）
- [ ] Good ティア構成での社内 PoC 構築
- [ ] 顧客向けデモ環境の開発
- [ ] 以下の 1 ページテンプレートを使用した業界別ピッチデッキの作成
- [ ] 既存 NAS/ONTAP フットプリントを持つターゲットアカウント 2-3 件の特定

---

## 1 ページパートナーピッチテンプレート

```
┌─────────────────────────────────────────────────────────────┐
│  FSx for ONTAP Lakehouse Integration: Zero-Copy Analytics on NAS     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. CUSTOMER PAIN                                            │
│     "We copy TB of file data to S3 just to run analytics.   │
│      It costs $X/month, takes Y days to set up, and         │
│      creates governance gaps."                               │
│                                                              │
│  2. WHY NOW                                                  │
│     • FSx for ONTAP S3 Access Points (GA, ONTAP 9.17.1+)   │
│     • AWS validated integrations: Athena, Glue, EMR,        │
│       Bedrock, Lambda, CloudFront, Transfer Family           │
│     • AI/RAG requires access to enterprise file data        │
│                                                              │
│  3. PROPOSED SOLUTION                                        │
│     FSx for ONTAP + S3 Access Point → Direct S3 API access  │
│     to existing file data. No copy. No sync pipeline.        │
│                                                              │
│  4. GOOD / BETTER / BEST                                     │
│     Good:   Athena read-only analytics ($)                   │
│     Better: Glue ETL + VPC-restricted access ($$)            │
│     Best:   Multi-platform + AI/RAG + DR ($$$)               │
│                                                              │
│  5. EXPECTED BUSINESS OUTCOME                                │
│     • Eliminate N data copies → save $X/month storage        │
│     • Remove sync pipelines → save Y hours/week ops         │
│     • Analytics in hours, not days                           │
│     • AI/RAG on existing documents without migration         │
│                                                              │
│  6. PoC PACKAGE                                              │
│     • 2-week PoC with sample data                            │
│     • Deliverable: Working Athena/Glue query on FSx for ONTAP data    │
│     • Success criteria: Query < 30s, zero data copies        │
│     • Cost: < $500 AWS charges                               │
│                                                              │
│  7. PARTNER ROLE                                             │
│     • [Partner name] designs, implements, and operates       │
│     • AWS provides technical validation and co-sell support  │
│     • NetApp provides ONTAP expertise and licensing          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## アンチパターン: 販売してはいけないもの

| アンチパターン | 失敗する理由 | 代わりに提案すべきもの |
|-------------|------------|-------------------|
| FSx for ONTAP S3 AP 上での Delta Lake write / MERGE / compaction | Delta コミットプロトコルは atomic rename を必要とするが、FSx for ONTAP S3 AP ではサポートされていない（[API サポート](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)） | Delta テーブルの読み取り専用分析、または Delta 書き込みパスにはネイティブ S3 を使用 |
| 規制業界でのデフォルトとしての Internet-origin AP | 規制データにはネットワークレベルの分離が必要。VPC-origin は非 VPC トラフィックに対する明示的 Deny を組み込み提供 | 機密/規制データには VPC-origin AP（注: Athena は internet-origin が必要） |
| 「S3 完全互換」と主張すること | FSx for ONTAP S3 AP は S3 操作のサブセットをサポート。Object Versioning なし、条件付き書き込みなし、署名付き URL なし、5GB アップロード制限 | 正確な表現を使用: 「サポートされる操作での S3 API アクセス」+ 互換性マトリクスへのリンク |
| 未検証の Iceberg 書き込みパスを本番対応として販売 | 外部カタログでの Iceberg 書き込みは Experimental であり、Verified ではない | 「読み取り専用は検証済み、書き込みパスは検証中」と位置付け |
| FSx for ONTAP スループットプロビジョニングの無視 | 顧客は S3 のような無制限スループットを期待するが、FSx for ONTAP S3 AP スループットはプロビジョンド容量に制限される | FSx for ONTAP スループットをワークロード要件に合わせてサイジング。PoC 検証に含める |
| 高並行性・小ファイルワークロードへの FSx for ONTAP S3 AP 提案 | 数十ミリ秒のレイテンシ + プロビジョンドスループット制限により、ネイティブ S3 と比較して最適ではない | 大規模シーケンシャルスキャン、バッチ分析、ドキュメント検索に使用。高頻度 API コールには不向き |

### パートナー提案のレッドライン

1. **絶対に** FSx for ONTAP S3 AP が S3 バケットのドロップイン代替であると主張しないこと
2. **絶対に** 制限事項の明示的な顧客承認なしに Delta/Hudi 書き込み操作を提案しないこと
3. **絶対に** PoC 環境で実際の PHI/PII を使用しないこと
4. **絶対に** セキュリティトレードオフを文書化せずに医療/金融向けに internet-origin AP を提案しないこと
5. **必ず** 技術提案書に互換性マトリクスの参照を含めること

---

## アーキテクチャ選定ガイド

### FSx for ONTAP S3 Access Points の適用ガイド

| アプローチ | データコピー? | NAS への影響 | 分析までの時間 | ガバナンス | AI/RAG | 最適な用途 |
|----------|-----------|-----------|-------------|-----------|--------|----------|
| **FSx for ONTAP S3 AP（本ソリューション）** | なし | なし | 数時間 | 統一（二層） | あり（Bedrock） | 既存 NAS データ、読み取り中心の分析、ドキュメント AI |
| **Native S3 + DataSync** | あり（フルコピー） | なし | 数日（初期同期） | 分離（S3 vs NAS） | あり | 書き込み中心の Lakehouse、Delta/Iceberg マネージドテーブル |
| **Native S3 + ETL パイプライン** | あり（変換済み） | なし | 数日〜数週間 | 分離 | あり | 複雑な変換、S3 上のメダリオンアーキテクチャ |
| **Snowflake External Stage on FSx for ONTAP S3 AP** | なし（ゼロコピー読み取り） | なし | 数時間 | Snowflake 管理（Tags, Row Policy, Masking） | あり（Cortex AI, Cortex Search） | NAS データ上のガバナンス付き AI が必要な Snowflake 顧客。COPY INTO → Managed Iceberg でオープン形式共有。 |
| **Databricks on native S3** | あり（先に S3 へ） | なし | 数日 | Unity Catalog on S3 | あり | Databricks 中心、Delta 書き込み中心 |
| **FabricPool tiering** | 部分的（コールドティア） | 最小限 | N/A（分析用途ではない） | ONTAP 管理 | なし | コスト最適化、分析用途ではない |
| **オンプレミス分析** | なし | なし | 数週間（セットアップ） | オンプレミスツール | 限定的 | エアギャップ環境 |

### 判断フレームワーク

```
Q1: Does the customer need to WRITE Lakehouse tables (Delta/Iceberg)?
  → Yes: Use native S3 for write path; FSx for ONTAP S3 AP for read-only source data
  → No: FSx for ONTAP S3 AP is ideal

Q2: Does the customer need sub-millisecond latency or unlimited concurrency?
  → Yes: Use native S3
  → No: FSx for ONTAP S3 AP (tens of ms latency, provisioned throughput)

Q3: Does the customer have existing NAS/ONTAP data they want to analyze?
  → Yes: FSx for ONTAP S3 AP eliminates the copy
  → No: Native S3 is simpler

Q4: Does the customer need NFS/SMB access alongside S3 analytics?
  → Yes: FSx for ONTAP S3 AP (multi-protocol on same data)
  → No: Native S3 may be sufficient

Q5: Does the customer need AI/RAG on existing documents?
  → Yes: FSx for ONTAP S3 AP + Bedrock Knowledge Bases
  → No: Evaluate based on Q1-Q4
```

---

## Co-sell レディパッケージ

AWS + パートナー共同販売のための資料とプロセス。

### ターゲットアカウント基準

| 基準 | 指標 |
|------|------|
| 既存 NAS/ONTAP フットプリント | NetApp ONTAP（オンプレミスまたは FSx for ONTAP）上に 10 TB 以上のファイルデータ |
| 分析イニシアチブ | アクティブまたは計画中のデータレイク / Lakehouse / BI プロジェクト |
| クラウド導入段階 | AWS アカウントがアクティブ、VPC デプロイ済み |
| ペインシグナル | データコピーコスト、同期パイプライン障害、分析アクセス遅延への不満 |
| 規制ドライバー | データガバナンス改善を推進するコンプライアンス要件 |
| AI/ML への関心 | 生成 AI / RAG のエンタープライズドキュメントでの探索またはパイロット中 |

### ディスカバリー質問

1. 「現在、分析のために S3 にコピーしているファイルデータはどのくらいありますか？月額コストはいくらですか？」
2. 「データ作成から分析利用可能になるまでどのくらいかかりますか？」
3. 「NAS と S3 で別々のアクセス制御がありますか？クロスシステムアクセスをどのように監査していますか？」
4. 「ファイル共有上に AI で検索可能にしたいドキュメントはありますか？」
5. 「どの分析プラットフォームを使用中または評価中ですか（Databricks、Snowflake、Athena）？」
6. 「データアーキテクチャの意思決定に影響するコンプライアンス要件は何ですか？」

### 案件適格性チェックリスト

- [ ] 顧客が NAS/ONTAP 上に 10 TB 以上を保有
- [ ] 顧客が VPC 付きのアクティブな AWS アカウントを保有
- [ ] 顧客が分析ユースケースを特定済み
- [ ] 顧客の予算オーナーを特定済み
- [ ] 技術意思決定者がエンゲージ済み
- [ ] ブロッカーなし: 顧客が ONTAP 9.17.1+ を実行可能
- [ ] 同一リージョンデプロイが実現可能

### 顧客オブジェクション対応

| オブジェクション | 回答 |
|---------------|------|
| 「既に S3 にコピーしていて問題ない」 | 「そのパイプラインの月額コストはいくらですか？障害時はどうなりますか？FSx for ONTAP S3 AP ならそれを完全に排除できます。」 |
| 「本当に S3 互換ですか？」 | 「分析に必要なコア S3 操作（Get、Put、List、Delete）をサポートしています。正確な互換性マトリクスはこちらです。読み取り専用分析は完全に検証済みです。」 |
| 「パフォーマンスはどうですか？」 | 「レイテンシは数十ミリ秒で S3 と同等です。スループットは FSx for ONTAP のプロビジョニングに依存します。PoC でワークロードに合わせてサイジングします。」 |
| 「Delta Lake の書き込みが必要です」 | 「Delta 書き込みには atomic rename が必要ですが、これはサポートされていません。ソースデータの読み取りには FSx for ONTAP S3 AP を、Delta 書き込みターゲットにはネイティブ S3 を推奨します。」 |
| 「セキュリティチームがブロックするでしょう」 | 「Block Public Access がデフォルトで強制されます。二層認証（IAM + ファイルシステム）。ネットワーク分離には VPC-origin オプション。ガバナンスドキュメントはこちらです。」 |

### PoC SOW テンプレート概要

```
1. Objective: Validate FSx for ONTAP S3 AP for [use case]
2. Scope: [Good/Better/Best tier]
3. Duration: 2 weeks
4. Deliverables:
   - Working query on FSx for ONTAP data via [Athena/Glue/Bedrock]
   - Performance benchmark results
   - Security validation report
   - Cost comparison (current vs FSx for ONTAP S3 AP)
5. Success criteria: [from kpi-and-validation.md]
6. Resources: Partner SA (X days), Customer admin (Y hours)
7. AWS charges estimate: < $1,000
8. Go/No-go decision: End of Week 2
```

---

## 初回案件プレイブック（パートナータイプ別）

### SIer: NAS モダナイゼーションアセスメント + 分析 PoC

| フェーズ | アクティビティ | 期間 | 成果物 |
|---------|-------------|------|--------|
| 1. アセスメント | NAS データの棚卸し、分析候補の特定 | 1 週間 | アセスメントレポート |
| 2. 設計 | Good/Better ティアのアーキテクチャ | 1 週間 | アーキテクチャドキュメント |
| 3. PoC | FSx for ONTAP + S3 AP + Athena/Glue のデプロイ | 2 週間 | 動作デモ + ベンチマーク |
| 4. 提案 | 本番デプロイメント提案 | 1 週間 | SOW + コスト見積もり |
| **初回案件規模** | アセスメント + PoC: $15K-30K | | |

### MSP: 読み取り専用分析マネージドパッケージ

| フェーズ | アクティビティ | 期間 | 成果物 |
|---------|-------------|------|--------|
| 1. オンボード | FSx for ONTAP + S3 AP + モニタリングのデプロイ | 2 週間 | 本番環境 |
| 2. 運用 | 月次モニタリング、パッチ適用、最適化 | 継続 | 月次レポート |
| 3. 拡張 | Glue ETL、Bedrock RAG の追加 | 要望に応じて | 更新アーキテクチャ |
| **収益モデル** | セットアップ費用 + 月額マネージド費用 | | |
| **初回案件規模** | セットアップ: $10K、月額: $3K-5K | | |

### Data/AI パートナー: Bedrock RAG PoC パッケージ

| フェーズ | アクティビティ | 期間 | 成果物 |
|---------|-------------|------|--------|
| 1. データ準備 | ドキュメント特定、S3 AP 設定 | 1 週間 | データソース準備完了 |
| 2. RAG 構築 | Bedrock Knowledge Base + エージェント | 2 週間 | 動作する RAG アプリケーション |
| 3. 評価 | 精度テスト、ユーザーフィードバック | 1 週間 | 評価レポート |
| 4. 本番化 | ハードニング、モニタリング、ガードレール | 2 週間 | 本番 RAG システム |
| **初回案件規模** | RAG PoC: $20K-40K | | |

### NetApp チャネルパートナー: ONTAP 顧客分析拡張

| フェーズ | アクティビティ | 期間 | 成果物 |
|---------|-------------|------|--------|
| 1. 特定 | 分析ニーズのある既存 ONTAP 顧客 | 継続 | ターゲットリスト |
| 2. ワークショップ | 共同ワークショップ: ONTAP + AWS 分析 | 1 日 | 顧客の関心 |
| 3. PoC | FSx for ONTAP 移行 + S3 AP + 分析 | 3 週間 | 動作するソリューション |
| **初回案件規模** | ワークショップ + PoC: $10K-20K | | |

### ISV: ガバナンス付きファイルアクセス統合

| フェーズ | アクティビティ | 期間 | 成果物 |
|---------|-------------|------|--------|
| 1. 統合 | ISV 製品への S3 AP 統合 | 4-6 週間 | 機能リリース |
| 2. 認定 | AWS 検証、ドキュメント作成 | 2 週間 | 認定済み統合 |
| 3. GTM | 共同マーケティング、顧客パイロット | 継続 | パイプライン |
| **収益モデル** | 製品機能（ライセンスに含む）+ サービス | | |

---

## パートナー収益化モデル

| 収益ストリーム | 説明 | 典型的な範囲 | 継続? |
|-------------|------|------------|------|
| アセスメント / ディスカバリー | NAS 棚卸し、分析レディネス評価 | $10K-25K | いいえ |
| アーキテクチャ設計 | ソリューション設計、セキュリティレビュー | $15K-40K | いいえ |
| PoC 実装 | 2-4 週間の概念実証 | $15K-50K | いいえ |
| 本番デプロイメント | フル実装 + テスト | $50K-200K | いいえ |
| マネージド運用 | モニタリング、パッチ適用、最適化、サポート | $3K-10K/月 | はい |
| セキュリティ/コンプライアンスレビュー | 年次監査、ポリシーレビュー、ペネトレーションテスト | $10K-30K/年 | はい |
| RAG/AI 統合 | Bedrock KB セットアップ、プロンプトエンジニアリング、評価 | $20K-60K | いいえ |
| 最適化サービス | 四半期パフォーマンスレビュー、コスト最適化 | $5K-15K/四半期 | はい |
| トレーニング & イネーブルメント | 顧客チームの運用トレーニング | $5K-15K | いいえ |

### 収益予測（顧客あたり初年度）

```
Conservative (Good tier):
  Assessment:     $15K
  PoC:            $20K
  Deployment:     $50K
  Operations:     $36K (12 × $3K)
  Total Year 1:   $121K

Growth (Better tier + RAG):
  Assessment:     $20K
  PoC:            $30K
  Deployment:     $100K
  RAG integration: $40K
  Operations:     $72K (12 × $6K)
  Total Year 1:   $262K
```

---

## 市場投入パス

```
Phase 1: Internal Validation (Month 1-2)
  └─ Build internal PoC
  └─ Train partner SA/delivery team
  └─ Document offering in partner portal

Phase 2: First Customer (Month 2-4)
  └─ Identify target account (with AWS account team)
  └─ Joint discovery call
  └─ PoC delivery
  └─ Case study (anonymized if needed)

Phase 3: Offering Publication (Month 4-6)
  └─ Reference architecture on partner website
  └─ AWS Partner Solutions Finder listing
  └─ Joint blog post / webinar with AWS
  └─ Conference presentation (AWS Summit, re:Invent)

Phase 4: Scale (Month 6-12)
  └─ Repeatable delivery methodology
  └─ Junior consultant enablement
  └─ AWS Marketplace private offer (if applicable)
  └─ Multi-customer pipeline
  └─ Quarterly business review with AWS partner team
```

---

## パートナー優先度マトリクス

候補パートナーごとに各基準をスコアリング（1-5）し、エンゲージメント優先度を決定します。

| 基準 | ウェイト | 説明 |
|------|---------|------|
| 既存 FSx for ONTAP / NetApp プラクティス | 5 | 既に ONTAP ソリューションを提供 |
| データ & 分析能力 | 4 | Databricks/Snowflake/Athena の専門知識あり |
| 業界フットプリント（医療/金融/製造） | 4 | 規制業界でアクティブ |
| マネージドサービス能力 | 3 | 継続的な環境運用が可能 |
| AWS セールスアラインメント | 5 | AWS アカウントチームとのアクティブな co-sell 関係 |
| NAS ヘビーワークロードの顧客基盤 | 5 | 10TB+ NAS を持つ既存顧客 |
| エグゼクティブスポンサーの可用性 | 3 | パートナーリーダーシップが新オファリングにコミット |
| 初回案件レディネス | 4 | 60 日以内に実行可能 |

### 優先度ティア

| ティア | スコア範囲 | アクション | タイムライン |
|-------|-----------|----------|------------|
| **Tier 1** | 30-40 | 即時 co-sell エンゲージメント | 2 週間以内に開始 |
| **Tier 2** | 20-29 | まずイネーブルメント、その後 co-sell | 60 日以内に開始 |
| **Tier 3** | 10-19 | 将来の候補、レディネスを監視 | 四半期ごとに再評価 |

---

## 初回 3 案件パイプライン計画

### 30 日パイプライン構築スプリント

| 週 | アクティビティ | オーナー | アウトプット |
|----|-------------|---------|-----------|
| 1 | ターゲットアカウント 5-10 件の特定（NAS 10TB+、分析ニーズ） | AWS アカウントチーム + パートナー | ターゲットアカウントリスト |
| 1 | ターゲットアカウントについて AWS アカウントマネージャーとアライン | パートナー SA + アカウントマネージャー | 共同アカウントプラン |
| 2 | パートナーアカウントマッピング（どのパートナーがどのアカウントをカバー） | パートナー SA | アカウント-パートナーマッピング |
| 2 | 共同ディスカバリーワークショップ（2-3 アカウント） | パートナー + AWS SA | ディスカバリーノート |
| 3 | 案件適格性評価（案件適格性チェックリストを使用） | パートナーセールス + AWS | 適格パイプライン |
| 3 | トップ 3 の PoC 提案書作成 | パートナー SA + デリバリー | PoC SOW |
| 4 | 顧客意思決定ミーティング | パートナー + AWS | 3 件の署名済み PoC エンゲージメント |

### 案件ステージ進行

| ステージ | 定義 | 期待される次のアクション | 典型的な期間 |
|---------|------|---------------------|------------|
| 0. 特定 | アカウントがターゲット基準を満たす | ディスカバリーコールのスケジュール | — |
| 1. ディスカバリー | ペイン確認、ステークホルダーエンゲージ | ソリューション概要のプレゼン | 1-2 週間 |
| 2. 適格 | 予算、権限、ニーズ、タイムライン確認 | PoC 提案 | 1 週間 |
| 3. PoC 提案済み | SOW 提示、価格合意 | 顧客が SOW に署名 | 1-2 週間 |
| 4. PoC 実行中 | PoC 実行中 | 結果の提供 | 2-4 週間 |
| 5. 本番提案済み | PoC 成功、本番 SOW 提示 | 顧客承認 | 2-4 週間 |
| 6. 受注 | 本番デプロイメント契約 | デリバリー開始 | — |

---

## パートナーイネーブルメントキット

| 対象者 | 資料 | 目的 |
|--------|------|------|
| **セールス / アカウントマネージャー** | 1 ページピッチ、オブジェクション対応、価格ガイド、ターゲットアカウント基準 | 案件の特定と適格性評価 |
| **プリセールス / SA** | 技術ディープダイブデッキ、デモスクリプト、アーキテクチャ図、互換性マトリクス | 技術検証と顧客ワークショップ |
| **デリバリー / コンサルタント** | PoC SOW テンプレート、デプロイメントチェックリスト、ランブック、ベンチマーク手法 | PoC と本番デプロイメントの実行 |
| **マネージドサービス** | 運用ランブック、モニタリングセットアップガイド、月次レポートテンプレート、エスカレーションマトリクス | 継続運用 |
| **エグゼクティブ / プラクティスリード** | 収益モデル、市場投入パス、ケーススタディテンプレート、QBR テンプレート | ビジネスプランニングとパートナー管理 |

### イネーブルメントセッション計画

| セッション | 時間 | 対象者 | 内容 |
|----------|------|--------|------|
| 1. 概要 & ポジショニング | 1 時間 | 全員 | ビジネス価値、アーキテクチャ選定ガイド、アンチパターン |
| 2. 技術ディープダイブ | 2 時間 | SA / デリバリー | アーキテクチャ、互換性マトリクス、セキュリティモデル |
| 3. ハンズオンラボ | 4 時間 | SA / デリバリー | FSx for ONTAP + S3 AP + Athena/Glue のエンドツーエンドデプロイ |
| 4. セールスプレイワークショップ | 1 時間 | セールス | ディスカバリー質問、オブジェクション対応、価格設定 |
| 5. 初回案件プランニング | 1 時間 | セールス + SA | ターゲットアカウント、パイプラインスプリントキックオフ |

---

## 業界別 GTM メッセージ

| 業界 | ヘッドライン | ペインポイント | 価値提案 | コールトゥアクション |
|------|-----------|------------|---------|-----------------|
| **製造** | 「移行なしでエンジニアリングファイルを AI 対応に」 | 設計ファイル、検査記録、保守マニュアルが NAS に閉じ込められている | Athena/Bedrock で既存ファイルをクエリ・検索 — データコピーゼロ | 「2 週間 PoC: 保守マニュアルの AI 検索」 |
| **医療** | 「PHI を移動せずに研究データを安全に AI 活用」 | ファイル共有上の研究ドキュメントが分析/AI からアクセス不可 | ガバナンス付き S3 AP + Bedrock RAG 経由で匿名化データにアクセス | 「匿名化研究ドキュメントでのセキュア RAG PoC」 |
| **金融** | 「コンプライアンスドキュメント全体のガバナンス付き検索」 | 規制文書、監査証跡、契約書がファイル共有に散在 | 二層認証 + 完全な監査証跡による制御されたアクセス | 「完全な監査証跡付きコンプライアンスドキュメント検索」 |
| **メディア & エンターテインメント** | 「AI でメディアアセットを検索・分析」 | 過去の制作物、脚本、メタデータがファイルストレージに埋もれている | TB のメディアファイルを移行せずに AI アセットディスカバリー | 「アセット分析 PoC: プロダクションアーカイブの検索」 |
| **エンタープライズ IT** | 「ランブックを AI ナレッジベースに変換」 | インシデントレポート、ランブック、アーキテクチャドキュメントが共有ドライブ上 | RAG パワードナレッジ検索でインシデント解決を高速化 | 「IT ナレッジベース PoC: AI 検索で MTTR を削減」 |

---

## 共同ディスカバリーワークショップ

### 目的

パートナー適合性の検証、ターゲットアカウントの特定、最初の共同オファーの定義を、Tier 1 パートナー候補との 120 分のセッションで実施します。

### Tier 1 パートナー最低基準

パートナーは共同ディスカバリーワークショップの資格を得るために、以下の**すべて**を満たす必要があります：

- [ ] 既存の FSx for ONTAP / NetApp / NAS 顧客基盤を保有
- [ ] Data/AI またはマネージドサービス能力を保有（少なくとも 1 つ）
- [ ] ビジネスまたは技術リーダーがワークショップに参加可能
- [ ] 30 日以内に少なくとも 1 件の顧客候補を特定可能

### ワークショップアジェンダ（120 分）

| 時間 | トピック | オーナー | アウトプット |
|------|---------|---------|-----------|
| 0-10 分 | 自己紹介、目的の確認 | AWS パートナー SA | ゴールのアラインメント |
| 10-30 分 | FSx for ONTAP S3 AP 概要 + デモ | AWS SA | パートナーが技術を理解 |
| 30-50 分 | パートナー能力レビュー | パートナー | パートナーの強みを理解 |
| 50-70 分 | ターゲットアカウントブレインストーム | 共同 | 3-5 件の候補アカウント特定 |
| 70-90 分 | 案件仮説の策定 | 共同 | 1-3 件の案件仮説ドラフト |
| 90-110 分 | 初回オファーパッケージ設計 | 共同 | 合意された初回オファー（アセスメント/PoC） |
| 110-120 分 | ネクストステップとオーナー | 共同 | 日付付きアクションアイテム |

### ワークショップ事前準備

| 参加者 | 準備事項 |
|--------|---------|
| AWS パートナー SA | パートナー背景調査、1 ページピッチ準備、デモ環境 |
| AWS アカウントマネージャー | ターゲットアカウントリスト（NAS 10TB+、分析ニーズ） |
| パートナービジネスリード | NAS/ONTAP フットプリントを持つ顧客リスト、収益目標 |
| パートナー技術リード | 互換性マトリクス、アンチパターンのレビュー |

### ワークショップアウトプットテンプレート

```yaml
workshop_date: "YYYY-MM-DD"
partner_name: "<partner>"
participants:
  - name: "<name>"
    role: "<role>"
    org: "AWS | Partner"

partner_fit_score: X/40  # from Prioritization Matrix
tier: "Tier 1 | Tier 2 | Tier 3"

target_accounts:
  - account: "<customer name>"
    industry: "<industry>"
    nas_footprint: "<estimated TB>"
    analytics_need: "<description>"
    partner_relationship: "<existing | new>"

deal_hypotheses:
  - hypothesis: "Manufacturing / NAS inspection data analytics / SIer-led"
    first_offer: "Assessment + Analytics PoC"
    estimated_value: "$25K"
    timeline: "60 days"
    validated: true/false
    
  - hypothesis: "Enterprise IT / Runbook RAG / MSP-led"
    first_offer: "Managed RAG package"
    estimated_value: "$15K setup + $5K/month"
    timeline: "45 days"
    validated: true/false

first_offer_package:
  type: "Assessment | PoC | Managed Package"
  scope: "<description>"
  duration: "<weeks>"
  price_range: "$X-Y"

required_enablement:
  - "<session needed>"

next_steps:
  - action: "<action>"
    owner: "<who>"
    due: "YYYY-MM-DD"
```

### パートナーレディネス認定

イネーブルメント後、パートナーは以下ができる場合に co-sell 認定されます：

- [ ] AWS サポートなしで 15 分ピッチを実施できる
- [ ] トップ 3 アンチパターンとその重要性を説明できる
- [ ] テンプレートから PoC SOW を作成できる
- [ ] セキュリティ FAQ の質問に回答できる（Block Public Access、二層認証、VPC-origin）
- [ ] 標準質問を使用してディスカバリーコールを実施できる
- [ ] AWS アカウントチームと共同ネクストステップを定義できる

### Co-sell RACI

| アクティビティ | パートナー | AWS SA | AWS アカウント Mgr | NetApp | 顧客 |
|-------------|:-------:|:------:|:----------------:|:------:|:--------:|
| アカウント選定 | C | C | **R** | I | — |
| ディスカバリーコール | **R** | C | I | — | **A** |
| 技術検証 | **R** | **R** | I | C | C |
| PoC デリバリー | **R** | C | I | C | **A** |
| セキュリティレビュー | C | **R** | I | — | **A** |
| 本番デプロイメント | **R** | C | I | C | **A** |
| マネージド運用 | **R** | I | I | C | **A** |
| カスタマーサクセスレビュー | C | C | **R** | I | **A** |

R = Responsible、A = Accountable、C = Consulted、I = Informed

### 案件オーナーシップ

アクティブな各案件について、明示的なオーナーを割り当てます：

| 役割 | 責任 |
|------|------|
| **案件オーナー** | 案件進行を推進、CRM エントリを所有、ステージ進行に責任 |
| **技術オーナー** | アーキテクチャ決定、PoC 実行、セキュリティ検証を所有 |
| **パートナーセールスオーナー** | 顧客関係、商務交渉、SOW を所有 |
| **AWS アカウントオーナー** | AWS 関係、社内アラインメント、co-sell サポートを所有 |
| **次回ミーティングオーナー** | 次の顧客インタラクションのスケジューリングとアジェンダを所有 |

---

## 初回オファー: FSx for ONTAP S3 AP アナリティクス準備アセスメント

**期間**: 2〜3 週間  
**対象**: 既存の NAS/ONTAP データを持ち、データ移行なしでアナリティクスや AI を検討したい顧客

**成果物:**
- データセットディスカバリー（ファイルタイプ、サイズ、アクセスパターン）
- エンジン適合性評価（Athena、Databricks、EMR、DuckDB Lambda、Snowflake）
- ガバナンス影響サマリー（IAM、ファイルシステム権限、監査要件）
- 読み取り専用バリデーション（顧客データでの動作確認クエリ）
- ネガティブテスト証跡（未認可アクセスの拒否確認）
- アーキテクチャ推奨（Good / Better / Best ティア）

**価格**: $15K〜25K（アセスメント + PoC）

---

## Marketplace オファー境界

このバリデーションパッケージ（[fsxn-lakehouse-integrations](https://github.com/Yoshiki0705/fsxn-lakehouse-integrations)）はパートナー提供アセスメントの参考資料として使用できますが、**それ自体は Marketplace オファーではありません**。

AWS Marketplace または CPPO 向けのパッケージ化候補:
- FSx for ONTAP S3 AP アナリティクスアセスメント（パートナー提供サービス）
- Lakehouse エンジン適合性ワークショップ（1 日エンゲージメント）
- ガバナンスおよび証跡パッケージ（規制業界向け）

Marketplace リスティングを作成するには、パートナーが別途スコープ、価格、デリバリー方法論を定義してパッケージ化する必要があります。

---

## 参考資料

- [S3 アクセスポイント経由でのデータアクセス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html)
- [アクセスポイントの互換性](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)
- [AWS サービスでのアクセスポイント利用](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-access-points-with-aws-services.html)
- [S3 アクセスポイントのネットワークアクセス設定](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
- [Amazon FSx for NetApp ONTAP のパフォーマンス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)

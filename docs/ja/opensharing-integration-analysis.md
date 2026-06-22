🌐 [English](../en/opensharing-integration-analysis.md) | **日本語**

> 📖 **FAQ**: 「OpenSharing で FSx for ONTAP に直接つなげるのか？」等の疑問は [UC 接続総合ガイド](./fsx-ontap-to-databricks-unity-catalog-guide.md) の FAQ セクション (Q1, Q6) で回答しています。

# OpenSharing × FSx for ONTAP: 統合分析

> **ステータス**: 将来を見据えたアーキテクチャ分析に、公開 OpenSharing 仕様から直接読み取ったプロトコルレベルの事実を追加（2026-06-16）。本リポジトリによる FSx for ONTAP に対するベンダー実装の独立検証はまだ実施していない。検証タスクは将来のアクティビティとして管理する。

> **レビュー注記**: 本分析は複数レンズによるアーキテクチャレビューで作成した。レビュアーのレンズは**役割のみ**で記述する（個人・所属企業の帰属はしない）。各主張には evidence tier を付す: **Public**（公開ソースで検証可能）、**Archetype**（役割ベースの一般的推論）。

## 何が変わったか（Public Evidence）

2026-06-10、Databricks は **OpenSharing**（Delta Sharing プロトコルの進化形、Linux Foundation ホスト）と、オンプレ/ハイブリッドストレージをデータ移動なしで Databricks に接続する **Storage Ecosystem** パートナー群を発表した。

| 事実 | ソース |
|------|--------|
| OpenSharing は構造化データに加え、AI アセット（agent skills、AI models、非構造化データ）を扱う初のオープンプロトコル | [Databricks Press Release](https://www.databricks.com/company/newsroom/press-releases/databricks-announces-opensharing) |
| Apache Iceberg IRC クライアントに対応し、Delta Sharing recipient を超えてリーチを拡大 | 同上 |
| Storage Ecosystem は zero-copy アーキテクチャでハイブリッド/オンプレストレージを Unity Catalog に接続 | [Databricks Blog](https://www.databricks.com/blog/announcing-databricks-storage-ecosystem-governing-enterprise-data-estate-wherever-it-lives) |
| GA/プレビューの launch partner にオブジェクトストレージ/ハイブリッドストレージのベンダーが含まれ、追加のエンタープライズストレージパートナーが "coming soon"（年内）として記載 | 同上 |
| 非構造化データ向け Volumes APIs が次ステップとして明示的に予告 | 同上 |
| Partner Well-Architected Framework が統合ブループリント（Iceberg を提供する2パス: Delta Shallow Clone / Apache XTable メタデータ変換）を文書化 | [Partner Framework](https://databrickslabs.github.io/partner-architecture/data-collaboration/software-defined-storage) |
| **DAIS 2026 キーノート（2026-06-16）**: SecureConnect がクラウド間のセキュア接続 + zero-copy 共有を実現。Global Distribution がクラウド・リージョン間の自動レプリケーションを追加 | [What's new with Unity Catalog](https://www.databricks.com/blog/whats-new-unity-catalog-data-ai-summit-2026) |
| **DAIS 2026 キーノート（2026-06-16）**: Iceberg v3 GA / Managed Iceberg GA / Foreign Iceberg GA / 新フェデレーションコネクタ / cross-engine ABAC が利用可能に | 同上 |
| **DAIS 2026 キーノート（2026-06-16）**: Storage Ecosystem パートナーステータスが精緻化 — MinIO（GA）、Everpure（Private Preview）、Qumulo / VAST Data（Private Preview Soon）。**NetApp、Cohesity、Commvault、Nutanix は年末までに提供確認**。SecureConnect は Databricks マネージドプロキシ（一度設定すれば recipient 追加ごとのファイアウォール変更不要）— **Public Preview** で利用可能、オプションで **NCC Private Link**（プロキシ↔provider ストレージ間の PrivateLink 接続）、mutual TLS、クロスリージョン/クロスクラウド対応。Serverless recipient は設定不要（[SecureConnect blog](https://www.databricks.com/blog/introducing-opensharing-secureconnect)）。外部カタログ（AWS Glue / Hive Metastore / Snowflake Horizon）からのテーブル共有もレプリケーションなしで可能 | [OpenSharing blog](https://www.databricks.com/blog/introducing-opensharing-next-evolution-delta-sharing-agentic-era) |

> FSx for ONTAP は、マルチプロトコルアクセス（NFS/SMB/iSCSI/S3）とデータ保護機能（Snapshot、FlexClone、SnapMirror、FabricPool）を持つ AWS マネージドのエンタープライズストレージサービスである。以下では、OpenSharing パターンが本リポジトリの既存 S3 Access Point 統合パターンをどう補完しうるかを評価する。

## なぜ本リポジトリに重要か

現在の互換性マトリクスでは、Databricks + FSx for ONTAP S3 Access Point のパスは **blocked**（プラットフォームのセッションポリシーが S3 AP ARN 形式を認識しない）と記載している。OpenSharing が重要なのは、その共有モデルが短命の presigned URL に基づき、共有サーバーは**メタデータとアクセス制御のみ**を担い、データ転送は client↔storage 直結だからである。

**Architecture-Lens（Archetype）の所見**: この分離により、消費側プラットフォームがストレージ ARN を直接パースせず共有プロトコルと対話するため、S3 AP ARN 認識問題をアーキテクチャレベルで迂回できる可能性がある。これは検証すべき仮説であり、確定した結果ではない。

## 技術ノート: FSx for ONTAP の presigned URL 挙動

Delta Sharing / OpenSharing は短命の presigned URL に依存するため、FSx for ONTAP の presigned URL 挙動が本分析の中核となる。以下の2つの問いは**分けて**考える必要がある:

1. **ドキュメントが Presign をサポートと記載しているか**（記載上の立場）
2. **クライアントが生成した presigned URL が実際にエンドポイントで動作するか**（実証された挙動）

presigned URL は**純粋にクライアント側の SigV4 query-string 署名**で生成され、生成にサーバー呼び出しは不要。本質的な問いは、エンドポイントが署名付き GET リクエストを honor するかである。

| エンドポイント | ドキュメント上の `Presign` | 観測された挙動 |
|---------------|:------------------------:|---------------|
| FSx for ONTAP S3 Access Point | 非対応と記載（[AWS ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)） | 本リポジトリの過去検証では、クライアント生成の SigV4 presigned URL が S3 Access Point エンドポイントに対して HTTP 200 を返した |
| ONTAP S3（ネイティブオブジェクトサーバー） | ONTAP 9.11+ で対応（SigV4。v2 presign は非対応） | ドキュメント上の対応 |

**要点**: 「S3 Access Point が Presign サポートを記載しているか」と「クライアントの presigned URL がそれに対して動作するか」は別問題。記載上の立場だけでバックエンドを除外すべきではない。ネイティブの ONTAP S3 オブジェクトサーバーは presigned URL サポート（SigV4）を記載しており確実な選択肢。S3 Access Point パスは過去検証でクライアント生成 presigned URL が動作した実績があり、ユースケースごとの実証を要する。SigV4 を使うこと（ONTAP S3 では v2 presign 非対応）。

**もう1つの経路 — 一時クレデンシャル**: OpenSharing プロトコルの credential vending は、asset type / access mode に応じて presigned URL *または* scoped 一時クラウド credential（例: AWS STS）の*いずれか*を発行できる（[OpenSharing spec](https://github.com/OpenSharing-IO/OpenSharing)）。一時クレデンシャル方式では、recipient は presigned URL ではなく標準の `GetObject` で read する。`GetObject` は FSx for ONTAP S3 Access Points で対応しているため、この方式は presign の論点を完全に回避でき、アクセス経路の有力候補となる。

**ガバナンス粒度の注記**: credential vending（presigned URL / 一時クレデンシャル）は**ストレージの格納場所（prefix）単位**でアクセスを付与し、行・列レベルのポリシーは伝播しない。fine-grained で engine 横断のガバナンス（行フィルタ・列マスク）が必要な場合は、サーバーサイド scan planning を持つ Iceberg REST カタログが適切なレイヤーとなる。テーブル単位の zero-copy 配信と fine-grained ガバナンスは別の仕組みとして扱い、発行するクレデンシャルは対象テーブルの場所に最小権限でスコープすること。

> 本ノートは FSx for ONTAP / ONTAP の機能のみを記述する。挙動は各自の環境・ONTAP バージョンで再検証すること。

## プロトコル仕様面（公開仕様より）

OpenSharing 仕様は公開されている（[OpenSharing-IO/OpenSharing](https://github.com/OpenSharing-IO/OpenSharing)、Apache 2.0）。以下は**公開仕様から直接読み取った**プロトコル詳細（evidence tier: **Public**）であり、FSx for ONTAP バックエンドの統合をどう構築するかを規定する。これらはプロトコル上の事実であり、FSx for ONTAP バックエンドに対する独立検証はまだ行っていない。

**Asset 階層**: `Share → Schema → { Table, Volume, AgentSkill, Model, Agent（提案）, Glossary（提案） }`。1 つの bearer token が share 全体へのアクセスを認可し、share がアクセス制御の単位となる。

**Recipient profile**: JSON profile に `endpoint`（Delta テーブル用）、別フィールドの `icebergEndpoint`（Iceberg テーブル用）、`bearerToken`、任意の `expirationTime` を持つ。Iceberg 専用エンドポイントが cross-engine リーチの鍵。

**Table — 2 つの access mode**: 各テーブルは `accessModes`（`url` / `dir` / 両方）と `format`（`delta` / `iceberg`）を提示する:

| access mode | 機構 | FSx for ONTAP への含意 |
|-------------|------|----------------------|
| `url` | presigned URL（クライアント query API） | ネイティブ ONTAP S3 で動作（SigV4）。S3 Access Point は過去検証でクライアント生成 URL が動作 |
| `dir` | 一時 STS credential によるディレクトリアクセス | recipient は標準 `GetObject` で read — S3 Access Points 対応、presign 論点を回避 |

**標準 REST Catalog による Iceberg**: 仕様は標準 [Iceberg REST Catalog API](https://github.com/apache/iceberg/blob/main/open-api/rest-catalog-open-api.yaml)（`getConfig`, `listNamespaces`, `loadNamespaceMetadata`, `listTables`, `loadTable`, `reportMetrics`）を実装。**含意**: 標準 Iceberg REST クライアント（PyIceberg, Spark Iceberg, Athena）が共有テーブルを直接消費可能。Apache XTable / shallow-clone ブリッジは必須ではなく fallback に降格する。

**Credential vending**: AWS では標準 STS 一時クレデンシャル（`accessKeyId` + `secretAccessKey` + `sessionToken`）を `expirationTime` 付きで発行。Azure（SAS）、GCP（OAuth）、Cloudflare R2 も定義済み。AWS パスは本リポジトリの過去検証済み `GetObject` アクセスと整合する。

**Volumes（非構造化）— proposal 段階**: `Volume` asset はディレクトリの `storageLocation`（例 `s3://bucket/path/`）を共有し、**STS credential のみ**を発行（presigned URL モードなし）。これは FSx for ONTAP の非構造化ペイロード（画像・動画・ドキュメント）の自然な接続点であり、本リポジトリのメタデータカタログの取り組みと接続する。現行の connector はテーブルが先行対応で、volumes は進行中。

> これらは仕様レベルの事実である。FSx for ONTAP バックエンド（S3 Access Point またはネイティブ ONTAP S3）に対して仕様どおり動作するかは、段階的検証アクティビティで確認する。

## 検証済み: FSx for ONTAP S3 Access Point での STS Credential Vending（2026-06-17）

以下は実稼働中の FSx for ONTAP S3 Access Point に対して**独立に検証**した結果である（evidence tier: **Project-context**）。

### 動作確認済み

| テスト | 結果 | 含意 |
|--------|------|------|
| prefix 限定の scoped STS credentials 生成 | ✅ | OpenSharing server が特定テーブルパスにスコープした一時認証を発行可能 |
| 許可 prefix での `ListObjects`（scoped STS） | ✅（5 objects） | recipient が共有テーブル内のファイルを発見可能 |
| `GetObject`（scoped STS）: Parquet, CSV, JSON, PNG, TXT, Delta log, Iceberg metadata | ✅ 全形式 | アクセス機構はフォーマット非依存。Table asset と Volume asset の両方に適用 |
| 拒否 prefix での `GetObject`（同一 credentials） | ✅ AccessDenied | 最小権限が機能。credentials はスコープ外にエスケープしない |
| Credential 有効期限（15 分） | ✅ | プロトコル仕様通りの時限アクセス |

### OpenSharing にとっての意味

OpenSharing プロトコルの `dir` access mode（サーバーが presigned URL ではなく一時 AWS credentials を発行するモード）は **FSx for ONTAP S3 Access Points で動作する**。vended credentials を持つ recipient は:
- スコープ内の任意ファイルを list / read 可能
- Parquet データファイル（Delta/Iceberg Table asset 用）を読み取り可能
- 非構造化ファイル（Volume asset: 画像、PDF、動画）を読み取り可能
- vended scope 外のデータにはアクセス不可

### 解決されない問題（重要な区別）

| 制限 | 状態 | 理由 |
|------|------|------|
| **FSx for ONTAP S3 AP への Delta/Iceberg トランザクショナル write** | ❌ 依然ブロック | Conditional writes（`If-None-Match`）が 501 を返す。atomic rename 非対応。FSx for ONTAP S3 AP の製品レベル制限であり、OpenSharing とは無関係 |
| **Databricks から S3 Tables の Foreign Iceberg 読み取り** | ❌ 依然ブロック | External Location 検証が S3 Tables 内部バケットを拒否（HeadBucket 失敗）。本 credential vending テストとは無関係 |
| **Databricks UC による FSx for ONTAP S3 AP の read** | ✅ 解決済み（2026-05） | UC External Location の `access_point` field で動作。本日の STS テストは *OpenSharing recipient* パスの検証であり、これと補完関係 |

### アーキテクチャの明確化

```
FSx for ONTAP（raw data の source of truth: 画像、CSV、センサーログ、ドキュメント）
    │
    │ READ パス（検証済み ✅）:
    │   • UC External Location（Databricks 内部、2026-05）
    │   • OpenSharing STS credential vending（任意 recipient、2026-06）← NEW
    │   • Direct IAM（Athena, Glue, EMR — 既存）
    │
    │ WRITE パス（FSx for ONTAP S3 AP 上ではない）:
    │   • Delta/Iceberg managed tables は標準 S3 または S3 Tables に配置
    │   • FSx for ONTAP S3 AP はトランザクショナルなテーブルメタデータをホストできない
    │
    ▼
分析エンジンが FSx for ONTAP から raw data を read し、governed tables は別ストレージに write
```

**FSx for ONTAP はデータソース。テーブルフォーマット管理は別ストレージで行う。** OpenSharing はそのソースデータのガバナンス付き zero-copy read 配信を任意の recipient に対して実現する。

### 再現スクリプト

これらの結果を自身の FSx for ONTAP S3 Access Point に対して再現するための検証スクリプトを提供する:

```bash
cd integrations/iceberg-metadata-catalog/scripts/
python verify-opensharing-credential-vending.py \
  --ap-alias <your-ap-alias-ext-s3alias> \
  --allowed-prefix media/ \
  --denied-prefix benchmark/
```

両モード（STS + presigned URL）をテストし、フォーマットごとの pass/fail を出力し、JSON エビデンスファイルを保存する。前提: `boto3`, `requests`, AWS 認証情報（`s3:GetObject`, `s3:ListBucket`, `sts:GetFederationToken`）。

### Presigned URL モード（補足的発見）

STS モード（primary）に加え、presigned URL も実証的に動作する:

| 条件 | 結果 |
|------|------|
| リージョナルエンドポイント（`s3.REGION.amazonaws.com`）+ SigV4 | ✅ 全フォーマットで HTTP 200 |
| グローバルエンドポイント（`s3.amazonaws.com`） | ❌ HTTP 301（リダイレクト、署名不一致） |
| AWS ドキュメント上の記載 | 「Not supported」 |

**推奨**: STS credential vending を primary mode として使用（公式対応、prefix スコープ）。Presigned URL は現時点で動作するが公式サポート保証がなく、リージョナルエンドポイントのワークアラウンドが必要。

> **ONTAP S3 ネイティブに関する注記**: 上記の presigned URL テストは FSx for ONTAP **S3 Access Points** に対して実施。ONTAP S3 ネイティブ（直接オブジェクトサーバー、9.11+）は presigned URL サポート（SigV4）を公式ドキュメントで記載しているが、本リポジトリでは**独立検証していない**。STS credential vending モードは S3 Access Point パス（AWS マネージド、AWS STS 対応）にのみ適用される。

## スコープと原則

- **補完であって置換ではない**: OpenSharing パスは、本リポジトリで既に文書化した AWS ネイティブ S3 Access Point パターン（Athena, Glue, EMR, Redshift, SageMaker）を**置き換えるものではなく補完**する。
- **正本はエンタープライズストレージに残る**: 正本データは FSx for ONTAP 上の Iceberg/Parquet。presigned URL 参照やブリッジメタデータは派生物。
- **全量ではなく curated subset を共有**: 目的は curated で AI-ready なデータプロダクトの公開であり、volume 全体の無差別共有ではない。権限不明データは deny-by-default。
- **単一 governance boundary**: 1つのカタログを governance boundary とし、複数カタログへの policy 分散を避ける。
- **native までの interim**: 本リポジトリの独立検証は、native ベンダー実装に先んじて OSS Delta Sharing 参照実装（同系譜プロトコル）で行う。

## 複数レンズレビュー

### Principal Cloud Data Architect lens（Archetype）
- **機会**: presigned URL 共有モデルが消費側プラットフォームをストレージ固有 ARN 形式から切り離し、zero-copy 原則を維持。
- **懸念**: OpenSharing server はカタログと同等の blast radius を持つ Tier-1 依存になる（停止時は依存する read が停止）。可用性・スケール・P99 レイテンシ設計が必要。
- **要検証**: read-only か read-write か / Delta か Iceberg か / カタログガバナンスが共有テーブルに適用されるか。

### Manufacturing Edge Data Architect lens（Archetype）
- **機会**: エンタープライズストレージ上のセンサーデータ・品質検査画像・設計ドキュメントが ML/AI ワークロードから直接利用可能に。予告された Volumes APIs で非構造化ペイロードにも拡張。
- **懸念**: エッジ固有の論点（時刻同期、イベント順序、重複排除）は共有プロトコルの範囲外。メタデータ↔ペイロードのリンクは自前設計の責務として残る。

### Lakehouse Governance Architect lens（Archetype）
- **核心的変化**: 共有データがコピーなしで一元ガバナンス（リネージ、アクセス制御、監査）の対象になりうる。
- **トレンド（Public）**: Iceberg REST **scan planning**（Iceberg 1.11）により、カタログがプラン時に行フィルタ・列マスクを適用し cross-engine ABAC が可能。OpenSharing の Iceberg IRC 対応がこの恩恵を受ける可能性。([カタログ動向分析](https://amdatalakehouse.substack.com/p/the-state-of-apache-iceberg-catalogs))
- **要検証**: write-back 対応 / column-level security・row filter・tag が共有テーブルに travel するか。

### Enterprise Storage Data Services Architect lens（Archetype）
- **戦略的枠組み**: OpenSharing エンドポイントは NFS/SMB/iSCSI/S3 に続くデータ公開面となり、エンタープライズファイルストレージをサイロからガバナンド・ノードへ転換。
- **検証すべき差別化**: テーブルのタイムトラベルを補完する point-in-time recovery（Snapshot）/ 共有 sandbox 向けの即時論理コピー（FlexClone）/ DR 対応共有エンドポイント向けクロスリージョンレプリケーション（SnapMirror）/ 同一データがファイルワークロードと AI を同時に支えるマルチプロトコル。
- **オープンクエスチョン**: native 実装が ONTAP S3 上か S3 Access Points 上か独立データパス上か / AWS マネージドとオンプレの提供タイミング。

### Open Catalog Strategist lens（Public）
- 2026 年半ば時点で、オープンテーブルフォーマットの議論は概ね Apache Iceberg に収束し、差別化は**カタログレイヤー**に移行。カタログが AI control plane 化しつつある。([ソース](https://amdatalakehouse.substack.com/p/the-state-of-apache-iceberg-catalogs))
- **重要な区別**: OpenSharing は*共有*プロトコル、Iceberg REST は*カタログ*プロトコル。両者はレイヤーが異なり、競合ではなく補完。
- **業界の未解決問題**: ガバナンスポリシーはカタログ間でポータブルでない。現実解は**単一カタログを governance boundary** に定め、全エンジンをそこ経由にすること。

### SDS Launch Partner SA lens（Public）
- launch partner ストレージベンダーの公開発言には共通テーマがある: **動かせない**データ（sovereignty、gravity、コスト）を移行せずクラウド AI に接続する。
- 実装パターン: ストレージパートナーが OpenSharing エンドポイントを立て、カタログに接続、サーバーレスコンピュートがその場でクエリ。

## 合意点

1. OpenSharing は**現行 Databricks ブロッカーを迂回する**有力なパス候補（要検証）。
2. 単一の共有プロトコルに賭けるのではなく、**Iceberg を共通データ面とする多面戦略**がベンダー中立性と cross-engine 共存に最も資する。
3. native ベンダー実装に先んじて、**OSS Delta Sharing サーバー + FSx for ONTAP バックエンドで先行検証**する価値がある。
4. **ガバナンスは単一 boundary に集約**すべき。複数カタログへの policy 分散は避ける。
5. 既存の非構造化データメタデータカタログの取り組みは、予告された **Volumes APIs** の方向性と強く接続する。

## 技術的決定

| ID | 決定 | 根拠 |
|----|------|------|
| D-1 | 2トラック並行 PoC: (1) OSS Delta Sharing サーバー + FSx for ONTAP の OpenSharing パス、(2) 中立カタログ経由の Iceberg IRC パス | Databricks 最適化と engine 中立の両方をカバー |
| D-2 | 単一カタログを governance boundary とし、cross-engine ABAC の travel をプラットフォームネイティブと中立カタログの両方で評価 | カタログ間の policy ポータビリティは業界的に未解決 |
| D-3 | 将来を見据えた分析および将来のブログ回として公開し、非構造化データカタログの取り組みと接続 | シリーズ連続性の維持、AWS コミュニティ視点 |
| D-4 | native ベンダー実装はトラッキングし、待たない。GA 時期は公開発言以上を予測しない | エビデンス規律 |

## リスクレジスタ（サマリー）

| リスク | 重大度 | 緩和策 |
|--------|--------|--------|
| 共有サーバーが新たな Tier-1 単一障害点 | 高 | HA 設計、レイテンシ監視、マネージド選択肢の検討 |
| presigned URL の再利用・無認可アクセス | 高 | 短命 URL、remote signing 優先、deny-by-default |
| Iceberg/Delta ブリッジの運用複雑性 | 中 | メタデータのみ変換、idempotent 設計、失敗時 dead-letter |
| ガバナンス policy の複数カタログ分散 | 高 | 単一 governance boundary の強制 |
| 権限変更・削除が共有メタデータに非反映 | 高 | 再同期/イベント駆動の無効化、deny-by-default |

## 提案アーキテクチャパターン

```
Pattern E: OpenSharing（Zero-Copy Governed Access）— 分析段階

FSx for ONTAP → OpenSharing Server（共有 + アクセス制御）
                      → Catalog（governance boundary）
                      → Lakehouse Serverless Compute（その場クエリ）
                      → Iceberg IRC クライアント（cross-engine）
```

## オープンクエスチョン

公開仕様から解決した項目（FSx for ONTAP に対する検証は引き続き必要）:
- **Iceberg / Delta の配信** — 両方が仕様化済み。Iceberg は標準 REST Catalog エンドポイント、Delta は Delta Sharing エンドポイントを使う。
- **アクセス機構** — テーブルは `url`（presigned）/ `dir`（STS credential）に対応。volume は STS credential のみ。
- **read / write** — 仕様の API は read 中心（list / get / loadTable / temporary-credentials）。明示的な write-back エンドポイントはなく、write-back は実証が必要。

未解決:
- native 実装は ONTAP S3 / S3 Access Points / 独立パスのどれか？
- AWS マネージドとオンプレの提供タイミングは？
- column/row ガバナンスポリシーは共有テーブルに travel するか（Iceberg REST scan planning 依存）？

## 次のアクティビティ

段階的な検証アクティビティを定義済み（read → Iceberg IRC → ガバナンス travel → write-back → 非構造化設計 → 公開）。ステータスはリポジトリの Supported Integrations テーブルおよび今後のブログシリーズで更新する。


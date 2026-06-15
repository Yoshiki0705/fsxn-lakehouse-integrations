🌐 [English](../en/opensharing-integration-analysis.md) | **日本語**

# OpenSharing × FSx for ONTAP: 統合分析

> **ステータス**: 将来を見据えたアーキテクチャ分析。公開発表（2026-06-10）に基づく。本リポジトリによるベンダー実装の独立検証はまだ実施していない。検証タスクは将来のアクティビティとして管理する。

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

- native 実装は ONTAP S3 / S3 Access Points / 独立パスのどれか？
- AWS マネージドとオンプレの提供タイミングは？
- 共有サーバーは read-only か read-write か？
- column/row ガバナンスポリシーは共有テーブルに travel するか？

## 次のアクティビティ

段階的な検証アクティビティを定義済み（read → Iceberg IRC → ガバナンス travel → write-back → 非構造化設計 → 公開）。ステータスはリポジトリの Supported Integrations テーブルおよび今後のブログシリーズで更新する。

---

*本ドキュメントは GA 時期の予測を避け、検証済み結果と将来分析を区別する。「レンズ」に帰属する記述は役割ベースのレビュー視点であり、特定個人・特定企業の発言ではない。*

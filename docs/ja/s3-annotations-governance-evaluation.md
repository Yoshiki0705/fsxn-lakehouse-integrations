🌐 [English](../en/s3-annotations-governance-evaluation.md) | **日本語**

# S3 Annotations / Metadata 評価: Databricks UC × FSx for ONTAP S3 AP ガバナンス課題への提案

> **ステータス**: 評価初版（2026-06-18）。live 検証済み（ネイティブ S3）+ 公式ドキュメント確定。
> **Evidence tier**: 各主張に明記（**Public** = 公開情報で検証可能 / **Verified** = 本環境で実証 / **Project-context** = 内部前提 / **Hypothesis** = 仮説）。
> **検証環境**: AWS ap-northeast-1、boto3 1.43.32（AWS CLI 2.35.4 には新コマンド未搭載、2.35.7+ 必要）。
> **フレーミング**: vendor-versus ではなく right-tool-for-the-job。各オプションのトレードオフを対称に記載。

---

## 1. 背景: 記録済みのガバナンス課題

本リポジトリには、Databricks Unity Catalog（UC）と FSx for ONTAP の S3 Access Point（S3 AP）連携に関する制約が記録済みです（出典: [`integrations/databricks/README.md`](../../integrations/databricks/README.md) の "Support Confirmation, 2026-05"。**ロールベース表記**で、ケース番号・担当者名はステアリング方針どおり伏せています）。

- **UC External Locations は S3 AP をストレージターゲットとしてサポートしない**（Databricks Support 2026-05 確認、evidence tier: **Project-context→Public 記録**）
- **根本原因**: AssumeRole 時に Databricks が生成する **session policy が S3 AP ARN を正しく扱えない** → External Location / External Table / External Volume 作成がブロック
- `access_point` フィールドは **GA リリースされず**、ドキュメントから削除。部分的成功は「サポートされたコードパスではない」
- Instance Profile + boto3 で読めるが **UC ガバナンスを完全にバイパス**（PoC のみ）

> 「Databricks Product Manager の発言」という人物・肩書での記録は存在しません。技術的な核心は上記 Support 確認ベースで記録済みです。本評価はその課題に対し、新発表の S3 Annotations / S3 Metadata で何が提案できるかを検討します。

---

## 2. S3 Annotations / S3 Metadata とは（evidence tier: Public）

- [S3 Annotations](https://aws.amazon.com/about-aws/whats-new/2026/06/amazon-s3-annotations-business-context/)（AWS Summit NY 2026, 2026-06）: S3 オブジェクトに大規模にカスタムメタデータを付与。1オブジェクト最大 1GB（最大1000個の名前付き annotation × 各1MB）。JSON/XML/YAML/テキスト。ミュータブル（オブジェクト書き換え不要で変更・削除）。copy/replication で追従、削除で消える（[AWS News Blog](https://aws.amazon.com/blogs/aws/amazon-s3-annotations-attach-rich-queryable-context-directly-to-your-objects/)）。
- [S3 Metadata](https://aws.amazon.com/s3/features/metadata/): オブジェクトメタデータを read-only な Apache Iceberg テーブル（journal / inventory / annotation テーブル）として自動提供。Athena・Iceberg 互換ツール・S3 Tables MCP server から検索可能。ap-northeast-1 を含む複数リージョンで GA。

> 出典の記述はライセンス遵守のため要約・言い換えしています。

---

## 3. 適用範囲の確定（本評価の最重要ポイント）

| 確認事項 | 結果 | 根拠 |
|---|---|---|
| S3 Metadata の対象バケット種別 | **汎用 Amazon S3 バケットのみ**（directory/table/vector 不可） | 公式: [Metadata table limitations](https://docs.aws.amazon.com/AmazonS3/latest/userguide/metadata-tables-restrictions.html)（**Public**） |
| S3 Metadata テーブルに ACL は含まれるか | **含まれない**（Lifecycle/Object Lock/ACL/replication status は対象外） | 同上（**Public**） |
| FSx for ONTAP S3（ONTAP S3 + S3 AP）に S3 Metadata 構成可能か | **不可** | 構造的理由: ONTAP S3 バケットは Amazon S3 コントロールプレーン外（`aws s3 ls` に現れない）。S3 Metadata API は Amazon S3 バケットを対象とする（**Verified**: 本環境で ONTAP S3 バケットは S3 名前空間に非存在を確認） |
| 注釈そのもの（PutObjectAnnotation）はネイティブ S3 で動作するか | **動作する** | **Verified**（§4） |

**結論**: S3 Annotations / Metadata は **直接 FSx S3 AP のデータには適用できません**。有効なのは **staged-to-S3 パターン**（FSx → FPolicy/DataSync/Glue/EMR → ネイティブ Amazon S3）に限られます。これは制約であると同時に、提案の前提条件です。

---

## 4. 検証結果（2026-06-18, ap-northeast-1, evidence tier: Verified）

再現スクリプト: [`integrations/iceberg-metadata-catalog/scripts/verify-s3-annotations.py`](../../integrations/iceberg-metadata-catalog/scripts/verify-s3-annotations.py)（使い捨てバケットを作成し、検証後に全リソースを削除）。

| ステップ | 結果 |
|---|---|
| ネイティブ S3 バケット作成 | ✅ |
| オブジェクト put | ✅ |
| `put_object_annotation`（`business-context`: AI 分類 JSON） | ✅ Case 1 実証 |
| `put_object_annotation`（`ontap-acl-hint`: owner/group/acl_hash/svm/volume/snapshot_id/allowed_principals JSON） | ✅ Case 2 実証 |
| `list_object_annotations` | ✅ count=2 |
| `get_object_annotation` 往復（owner=svc_quality 確認） | ✅ |
| クリーンアップ（注釈→オブジェクト→バケット削除） | ✅ 残存課金リソースなし |

補足: AWS CLI 2.35.4 には S3 Metadata/Annotations コマンドが未搭載（2.35.7+ 必要）。boto3 1.43.32 は全 API 搭載。

> **Round 2 検証スコープ（annotation テーブル / クエリパス）**: §7 #3 の「annotation テーブル有効化 + クエリ」は、AWS 公式で以下が確定したため**本セッションでの live クエリは実施していません**（到達不能な実行で課金リソースを残すより公式根拠で確定する方が適切と判断）:
> - **有効化は backfill を伴い完了まで分〜時間**（[公式: Enabling annotation tables](https://docs.aws.amazon.com/AmazonS3/latest/userguide/metadata-tables-enable-disable-annotation-tables.html)）→ in-session で「クエリ可能」に到達できない + backfill 課金。
> - annotation/metadata テーブルは **AWS マネージドの S3 Tables（table bucket）** に作成される。**AWS ネイティブ/オープンエンジン（Athena/EMR/Trino/Spark/ClickHouse）からは `s3tablescatalog` 経由でクエリ可能（公式サポート、§6 EXT-1）**。Databricks UC からの参照（`iceberg_rest`）のみブロック。
> - `CreateBucketMetadataConfiguration` は **journal テーブル必須**（annotation だけでも journal を作成）+ S3 metadata サービスが assume する **IAM ロール**が必要（API 内省で確認）。

---

## 5. 提案の深掘り（3案）

### 案1: `iceberg-metadata-catalog` の Annotations 強化（最も自然・低リスク）

既存の [iceberg-metadata-catalog](../../integrations/iceberg-metadata-catalog/) は Bedrock Vision で非構造化ファイルを分類し、Iceberg メタデータカタログ + OpenSearch ベクトル検索を提供しています。S3 Annotations は**それを置き換えるのではなく補完**します（分類結果を**オブジェクト自身に付与**し、コピー/レプリケーションで追従させる自己記述レイヤー）。

> **2 段階であることに注意（R1-F）**: (1) 注釈の付与（`PutObjectAnnotation`）は S3 Metadata 構成なしで**単体動作**（§4 で実証）。(2) **大規模クエリには annotation テーブルの有効化が必須**（`CreateBucketMetadataConfiguration` V2 + annotation テーブル設定）。これは S3 metadata サービスが assume する **IAM ロール**を要し、テーブルは **AWS マネージドの table bucket（S3 Tables）** に作成される。有効化は **backfill（分〜時間）** を伴い、クエリには **S3 Tables カタログ連携（`s3tablescatalog`）** が必要（§6 の共有依存を参照）。

```
FSx for ONTAP (画像/文書)
  │ ① Snapshot / FlexClone で一貫した時点を取得（FSxN steering 準拠）
  ▼
staged 取り込み: FPolicy→Lambda→S3 / DataSync / Glue / EMR
  │  ※ SnapMirror-to-S3 は FSx for ONTAP では非対応（本リポジトリ記録）
  ▼
Amazon S3 (汎用バケット)
  │ ② put_object_annotation: business-context = {分類, 信頼度, モデル, 言語, schema_version}
  │ ③ annotation テーブル有効化（S3 Metadata V2 + IAM ロール）
  ▼
S3 Metadata (annotation テーブル, Iceberg, S3 Tables 上)
  ├── Athena でクエリ
  └── S3 Tables MCP server でエージェント検索
```

| 観点 | 評価 |
|---|---|
| メリット | 分類コンテキストがオブジェクトに追従（copy/replication）。既存 Iceberg カタログ（OpenSearch 検索）を**補完**し、オブジェクト単位の自己記述性を付与。AWS ネイティブ |
| トレードオフ | staged S3 が前提（FSx 直アクセス不可）。annotation は最大1MB/個・1000個/オブジェクト。S3 Metadata は汎用バケットのみ。**クエリには annotation テーブル有効化（IAM ロール + table bucket）が追加で必要** |
| 既存カタログとの使い分け（R1-E） | 横断ベクトル/全文検索・大規模集計は既存 iceberg-metadata-catalog（OpenSearch/Iceberg）。オブジェクトに付随し copy で追従する自己記述コンテキストは annotation。両者は**補完関係** |
| 検証ステータス | annotation 付与/往復: **Verified**（§4）。annotation テーブル有効化 + Athena クエリ: §7 #3（**Round 2 で実施**） |

### 案2: permission-aware の「発見シグナル」（重要な但し書きあり）

`owner` / `group` / `acl_hash` / `classification` / `snapshot_id` / `allowed_principals` を annotation 化し、S3 Metadata 経由で検索可能にします。

> ⚠️ **非交渉の前提（FSxN AI/RAG steering 準拠）**: **これは「発見シグナル」であって「アクセス制御の強制」ではありません。** annotation はオブジェクトに付随する記述メタデータであり、読み取り認可を強制しません。permission-aware RAG では以下を必須とします:
> - ベクトル検索/メタデータフィルタの後、**LLM へ渡す直前に認可を再チェック**
> - 引用元リンク表示時にユーザーが実際にアクセス可能か再確認
> - **権限不明は deny by default**
> - 強制境界は引き続き **ONTAP ファイルレベル ACL + FPolicy + S3 AP access point policy + IAM**（補償コントロール）

> **ACL ヒントの導出（R1-A, FSx ONTAP Architect findings）**: ONTAP はマルチプロトコルのため、ヒントには **security style** を必須に含める:
> - `security_style`: `ntfs` / `unix` / `mixed`
> - **NTFS スタイル**: NTFS Security Descriptor（SDDL に正規化）から `acl_hash` を算出。`owner`=所有者 SID/名、`group`=プライマリグループ
> - **UNIX/NFSv4 スタイル**: NFSv4 ACE リスト（順序正規化）または mode bits から算出
> - `acl_hash` は**正規化後**の SHA-256（ACE 順序・表記揺れを吸収）。**ACL の実体ではなく変更検知用フィンガープリント**
> - 取得元は ONTAP REST API（FPolicy イベントで差分トリガ）。権限変更を検知し staged 側を再同期する

| 観点 | 評価 |
|---|---|
| メリット | 認可済みデータの**発見性**向上。ACL ハッシュで「権限変更検知」のトリガに利用可能 |
| トレードオフ | 強制力なし（二重チェック必須）。ACL の実体ではなくヒント。同期遅延で陳腐化リスク → acl_hash で検知し再同期 |
| 検証ステータス | annotation への ACL ヒント格納: **Verified**。認可チェーン統合: **未検証**（設計のみ） |

### 案3: ガバナンスを「効く層（Iceberg）」へ寄せる（Databricks 課題への直接アプローチ）

「S3 AP を UC に無理に載せる」のではなく、staged S3 の S3 Metadata Iceberg テーブル（+ 業務データの Iceberg テーブル）を **UC が参照**し、ガバナンスが機能する層で適用します。これにより S3 AP × session policy 問題を**構造的に回避**します。

```
staged S3 ──▶ S3 Metadata (Iceberg) / 業務 Iceberg テーブル
                     │
                     ├── Databricks UC（ネイティブ参照）── row/column ガバナンス（UC 内エンジン）
                     └── Athena / 他エンジン（Iceberg REST 経由）
```

> ⚠️ **既知制約（本リポジトリ記録、Databricks Governance Architect findings）**:
> - **重要な区別（R1-C）**: S3 Metadata の **system テーブル**（journal/inventory/annotation）は **AWS マネージドの S3 Tables（table bucket）** 上にあり、UC からの参照には S3 Tables カタログ連携（`s3tablescatalog` / `iceberg_rest`）が必要 → 本パスは**ブロック中**（二重ブロッカー）。**現実的な UC 参照ターゲットは「業務用にユーザーが作成する通常 Iceberg テーブル（汎用 S3 上）」**であり、Case 3 はまず後者を対象とする。
> - **annotation は UC の tags/ABAC とは統合されない並行メカニズム（R1-C）**。annotation が UC ガバナンスに自動で寄与することはない（UC 側は別途 tag/ABAC を設定する必要がある）。
> - **UC の Row Filters / Column Masks は外部エンジン（Athena/EMR が Iceberg REST 経由）では適用されない**（出典: [`docs/ja/governance-and-compliance.md`](./governance-and-compliance.md)）。UC ガバナンスは「UC 内エンジン」では効くが、クロスエンジンでは強制されない。
> - iceberg-metadata-catalog の **Phase 4（Databricks 連携）はブロック中**（`iceberg_rest` connection 作成不可、AWS/Databricks サポート対応中）。案3 の UC 参照は本ブロッカー解消が前提。

| 観点 | 評価 |
|---|---|
| メリット | session policy / S3 AP 制約を回避。UC 内では row/column ガバナンス + lineage が機能 |
| トレードオフ | staged S3 が前提（ゼロコピー喪失）。クロスエンジン強制は不可。`iceberg_rest` ブロッカー依存 |
| 検証ステータス | **未検証**（Phase 4 ブロッカー解消待ち、§7） |

---

## 5.5 外部専門家アーキタイプ・レビューによる精緻化（EXT-1〜5）

> ドメイン専門家のロールアーキタイプ（自動車・製造データ基盤 / コネクテッドカー・ストリーミング / Open Table Format・カタログ連携 / ガバナンス / リアルタイム OLAP）による精緻化。**個人名・社名は記載しない**（provenance は内部記録）。

- **EXT-1（Open Table Format / カタログ連携、Public で訂正）**: S3 Metadata テーブルは Athena / EMR / Redshift / Trino / Spark から `s3tablescatalog`（Glue + Lake Formation）経由でクエリ可能。前回 Round 2 の「案1 query と案3 UC が同一ブロッカーに収束」を訂正し、§4 / §6 / §7 / §9 を「**AWS ネイティブ query はサポート済、ブロックは Databricks UC のみ**」に統一。
- **EXT-2（コネクテッドカー・ストリーミング）**: annotation + S3 Metadata は **backfill 分〜時間でリアルタイムのホットパス外**。本評価は **cold path（発見・コンテキスト）** に位置づけ、リアルタイム（コネクテッドカー telemetry 等）は引き続きストリーミング基盤（Structured Streaming / Lakeflow / RT OLAP）が担う。annotation を hot path に置かない。
- **EXT-3（リアルタイム OLAP / オープンエンジン）**: annotation テーブルは Iceberg のため **Trino / Spark / ClickHouse 等のオープンエンジンからも読める**（Iceberg 互換エンドポイント）。Databricks UC ブロックを迂回する**代替クエリエンジン**として選択可能（優劣ではなく適材適所）。**ただし ClickHouse/Trino の Iceberg・S3 Tables 読み取りはバージョン/設定依存のため要検証（§7 #13、EXT-B3）。**
- **EXT-4（自動車・製造スケール）**: 大規模（車両 / 部品 / 画像が大量）では annotation 上限（1MB/個・1000個）+ backfill + staged S3 二重化のコストが顕在 → **保持 / ライフサイクル方針**を設計に含める。製造トレーサビリティ（genealogy: `lot_id` / `serial` / `process_step` / `inspection_result`）は annotation の好適ユースケース。例:
  ```json
  { "schema": "mfg.traceability.v1", "lot_id": "L-2026-0042", "serial": "SN-000123",
    "process_step": "weld-03", "inspection_result": "pass", "ts": "2026-06-18T00:00:00Z" }
  ```
- **EXT-5（ガバナンス、2 平面の分離）**: staged S3 / Iceberg のガバナンスは 2 平面に分離する — (a) **AWS 側 Lake Formation**（S3 Tables に列/行レベル制御 + credential vending、Athena/EMR 等に適用）、(b) **Databricks UC**（`iceberg_rest` ブロック中）。annotation は発見シグナルであり、強制が必要な箇所は **ガバナンス tag（LF LF-Tags / UC tags）へマッピング**する（annotation 単体では govern しない）。**さらに annotation はミュータブルなため、`s3:PutObjectAnnotation` / `DeleteObjectAnnotation` の書き込み権限を最小権限で統制する必要がある（EXT-B5）。統制しないと ACL ヒント等の発見シグナルが改ざん/なりすまし可能 → 発見の信頼性が損なわれる。Case 2 は「読み取り認可の二重チェック」に加え「書き込み権限の統制」も前提とする。**

---

## 6. 解決しないこと（honest assessment）

- S3 Annotations / Metadata は **UC が S3 AP を直接 govern できない問題そのものを解決しません**。これらは「発見・コンテキスト」であり「アクセス制御の強制」ではなく、かつ FSx S3 AP には適用されません。
- ゼロコピーは維持されません（staged-to-S3 が前提）。FSx 直アクセスの価値（ONTAP 機能の保持、マルチプロトコル）とはトレードオフ。
- annotation は ACL の実体ではないため、permission-aware の強制境界は引き続き ONTAP/IAM 側が担います。
- **クエリパスの共有基盤と分岐（Round 2 → 外部レビューで精緻化、F2-2 / EXT-1）**: annotation/metadata テーブルは AWS マネージドの S3 Tables 上にあり、`s3tablescatalog`（Glue Data Catalog + Lake Formation 連携）を**共有基盤**とします。ただしサポート状況は**分岐**します:
>   - **AWS ネイティブ / オープンエンジン（Athena / EMR / Redshift / Trino / Spark / ClickHouse 等）からのクエリはサポート済み**（`s3tablescatalog` 経由。[公式: Querying metadata tables with AWS analytics services](https://docs.aws.amazon.com/AmazonS3/latest/userguide/metadata-tables-bucket-integration.html)）。Lake Formation で列/行レベル制御も可能。
>   - **Databricks UC からの参照（`iceberg_rest` connection）はブロック中**（Case 3）。
>   → よって**案1 のクエリパス（AWS ネイティブ）はブロックされておらず**、ブロックは案3（Databricks UC）のみ。両者は同一基盤（`s3tablescatalog` / Iceberg）を共有するが**サポートは分岐**する。**（Round 2 の「同一ブロッカーに収束」という表現は本訂正で精緻化）**。attach 自体は単体動作、スケールクエリは上記基盤に乗る（backfill 分〜時間 + LF/IAM 設定が前提）。
- **annotation の鮮度（source 変更時、R1-D）**: annotation はコピー/レプリケーションで追従しますが、staged S3 オブジェクトは FSx ソースの**派生コピー**です。FSx 側でファイルが更新/削除された場合、staged コピーと annotation の**再同期/無効化**が必要（source update → 再 stage + 再 annotate、source delete → staged + annotation 削除）。FPolicy 変更イベントを再同期トリガに利用します。

---

## 7. 検証項目 / オープンクエスチョン

| # | 項目 | 状態 |
|---|---|---|
| 1 | FSx ONTAP S3 への S3 Metadata 構成不可の確定 | ✅ Public + Verified（§3） |
| 2 | ネイティブ S3 での annotation 往復 | ✅ Verified（§4） |
| 3 | annotation テーブル有効化 + クエリ（attach とは別段階）。**AWS ネイティブ/オープンエンジン（Athena/EMR/Trino/Spark/ClickHouse）からは `s3tablescatalog` 経由でクエリ可能（公式サポート）**。有効化は backfill 分〜時間 + LF/IAM 設定が前提。Databricks UC 参照のみブロック（§6 EXT-1） | ⚠️ 公式で経路確定（§4/§6）。live クエリは backfill 遅延のため本セッション未実施→runbook 化 |
| 4 | staged 取り込み時の annotation 付与パイプライン（FPolicy/Glue/Lambda のどこで付与） | 🔲 設計待ち |
| 5 | UC が S3 Metadata Iceberg テーブルを安定参照できるか（`iceberg_rest` ブロッカー） | 🔲 Phase 4 依存 |
| 6 | annotation の ACL ヒントと permission-aware RAG 認可チェーンの統合 | 🔲 設計待ち（強制ではないため二重チェック必須） |
| 7 | annotation 上限（1MB/個・1000個）と製造メタデータ量の適合 | 🔲 要見積もり |
| 8 | source 変更/削除時の annotation 再同期・無効化パイプライン（FPolicy トリガ、R1-D） | 🔲 設計待ち |
| 9 | annotation schema のバージョン管理・進化（取り込み順序/dedup で権威版を確定、R1-G） | 🔲 設計待ち |
| 10 | コスト次元の見積もり（annotation ストレージ / S3 Metadata テーブル(S3 Tables) / Athena scan / 取り込み compute / staged S3 二重化、R1-H） | 🔲 要見積もり |
| 11 | 製造トレーサビリティ annotation schema（lot/serial/process/inspection）の設計・検証（EXT-4） | 🔲 設計待ち |
| 12 | annotation → ガバナンス tag（LF LF-Tags / UC tags）マッピング設計（EXT-5） | 🔲 設計待ち |
| 13 | オープンエンジン（Trino / ClickHouse）での annotation テーブル読み取り検証（EXT-3） | 🔲 未検証 |
| 14 | annotation 書き込み権限の統制（`s3:PutObjectAnnotation`/`Delete` の最小権限）— 発見シグナル改ざん防止（EXT-B5） | 🔲 設計待ち |
| 15 | 製造 genealogy が 1000 イベント超の場合の構造化（配列）ペイロード設計（1MB/個上限考慮、EXT-B4） | 🔲 設計待ち |

---

## 8. AWS / Databricks へのフィードバック

サポート提出用の草案は**非公開**（`.private/support-feedback/`、gitignore 対象、ケース番号は提出者が追記）に格納:

- **AWS 向け**: FSx for ONTAP S3 / ONTAP S3 バケットでの S3 Metadata・Annotations 対応（または ONTAP S3 メタデータの Iceberg 互換公開）の feature request。本評価の「汎用バケットのみ」制約が FSx ユースケースのギャップである旨。
- **Databricks 向け**: UC External Location の S3 AP session policy 対応、`iceberg_rest` connection 制約、S3 Metadata Iceberg テーブルの UC 参照可否。staged-to-Iceberg パスでの row/column ガバナンスのクロスエンジン強制。

公開リポジトリには **ケース番号・担当者名を含めません**（ロールベース表記のみ）。

---

## 9. 選定ガイド（用途に応じて / right-tool-for-the-job）

| 要件 | 推奨 | 補足 |
|---|---|---|
| FSx データの**発見性・AI コンテキスト**を AWS ネイティブで付与 | 案1（staged S3 + Annotations） | ゼロコピーは犠牲。スケールクエリは Athena/Trino/Spark/ClickHouse（`s3tablescatalog`）で可能・backfill/LF 設定要（§6 EXT-1） |
| permission-aware RAG の**発見補助** | 案2（ACL ヒント annotation） | 強制は ONTAP/IAM、二重チェック必須 |
| Databricks で**ガバナンス付き分析** | 案3（Iceberg 層へ寄せる） | `iceberg_rest` 解消が前提、クロスエンジン非強制に注意 |
| FSx 直アクセス + 強制ガバナンス（現時点） | Snowflake External Table / Athena + ONTAP ACL/FPolicy | S3 Annotations とは独立 |

---

## 参考

- [Amazon S3 Annotations (What's New, 2026-06)](https://aws.amazon.com/about-aws/whats-new/2026/06/amazon-s3-annotations-business-context/)
- [Amazon S3 annotations (AWS News Blog)](https://aws.amazon.com/blogs/aws/amazon-s3-annotations-attach-rich-queryable-context-directly-to-your-objects/)
- [S3 Metadata table limitations and restrictions](https://docs.aws.amazon.com/AmazonS3/latest/userguide/metadata-tables-restrictions.html)
- [Amazon S3 Metadata (feature page)](https://aws.amazon.com/s3/features/metadata/)
- 本リポジトリ: [Databricks integration README](../../integrations/databricks/README.md) / [governance-and-compliance](./governance-and-compliance.md) / [cross-repo-integration-strategy](./cross-repo-integration-strategy.md)
- 接続性視点（ストレージとは別: Kafka/ClickHouse の UC 接続・通信経路・ポート）: [Kafka/ClickHouse → Unity Catalog 接続](./kafka-clickhouse-unity-catalog-connectivity.md)

---

## Persona Review Summary（改善ループ: Round 1–3）

### Review Metadata
- Review Date: 2026-06-18
- Reviewed Documents: `docs/{ja,en}/s3-annotations-governance-evaluation.md` + 再現スクリプト + サポート草案（非公開）
- Review Scope: S3 Annotations/Metadata の Databricks UC × FSx S3 AP 課題への適用評価
- Review Method: ドメイン専門ペルソナ重点の複数ラウンド批判レビュー → 対応 → 再レビュー

### Round 1 所見と対応（8 件）
| ID | ペルソナ | 所見 | 対応 |
|----|---------|------|------|
| R1-A | FSx ONTAP Architect | ACL ヒント導出が曖昧（マルチプロトコル） | §5 案2 に security_style / NTFS SD / NFSv4 ACE / 正規化 SHA-256 を明記 |
| R1-B | FSx ONTAP Architect | staging 一貫性未規定 / SnapMirror-to-S3 非対応 | §5 案1 に Snapshot/FlexClone 必須 + staging 手段を正確化 |
| R1-C | Databricks Governance | 案3 不正確（system テーブル二重ブロッカー / UC tags 非統合） | §5 案3 に区別と非統合を明記 |
| R1-D | Cloud Data Architect | source 変更時の staleness 未記載 | §6 + §7 #8 に再同期パイプライン追加 |
| R1-E | Cloud Data Architect | 「別カタログ不要」過大 | §5 案1 を「補完」に修正 |
| R1-F | Governance / Cloud Data | attach と query の段階混同 | §5 案1 / §4 / §7 #3 に段階を明記 |
| R1-G | Mfg Edge | schema バージョン管理未記載 | §7 #9 追加 |
| R1-H | Cloud Data Architect | コスト次元未記載 | §7 #10 追加 |

### Round 2 所見と対応（4 件、追加検証で判明）
| ID | ペルソナ | 所見 / 知見 | 対応 |
|----|---------|------------|------|
| F2-1 | Cloud Data / Governance | annotation テーブル有効化は backfill 分〜時間 | §4 / §7 #3 に明記、AWS feedback に反映 |
| F2-2 | Databricks Governance | **クエリパスが S3 Tables federation 依存 = Databricks `iceberg_rest` と同族ブロッカー**（案1 と案3 が同一ブロッカーに収束） | §6 に共有依存を追記、両 feedback に反映 |
| F2-3 | accuracy | 3 段階（attach→有効化→query）の明確化 | §5 案1 / §4 に反映 |
| F2-4 | API | journal テーブル必須 + IAM ロール必須 | §4 に明記 |

### Round 3 最終サインオフ（各ペルソナ）
- **Principal Cloud Data Architect**: 補完関係・staleness・コスト次元が明確化。**APPROVE**。残: §7 #4/#8/#10 を Phase 化。
- **Manufacturing Edge Data Architect**: schema 版管理・取り込み順序の論点を反映。**APPROVE**。残: 大量時スループット見積もり（§7 #7）。
- **Databricks Governance Architect**: 案3 の二重ブロッカーと共有依存（F2-2）が明確化し設計の現実性が向上。**APPROVE WITH COMMENTS**（`iceberg_rest`/`s3tablescatalog` 解消が案1 query / 案3 双方の前提）。
- **NetApp FSx for ONTAP Architect**: ACL ヒント導出・Snapshot/FlexClone staging・FSx 非対応制約が明確化。**APPROVE**。残: AWS feature request の実現性。
- **Public Repository Confidentiality Reviewer**: Round 1–2 の追記後も公開対象に機密 ID / ケース番号なしを再確認。**Pass**（サポート草案は `.private/` gitignore に分離）。

### 外部専門家アーキタイプ・レビュー（Round A–B, EXT-1〜5 / EXT-B3〜B5）

> ドメイン専門家のロールアーキタイプによる追加レビュー。**個人名・社名は非記載**（provenance は内部記録）。

- **Open Table Format / カタログ連携 archetype**: 【EXT-1 訂正】S3 Metadata テーブルは Athena/EMR/Trino/Spark から `s3tablescatalog` 経由でクエリ可能 → Round 2 の「同一ブロッカー収束」を訂正。AWS ネイティブ query はサポート済、ブロックは Databricks UC のみ。**最重要の精度向上**。
- **コネクテッドカー・ストリーミング archetype**: 【EXT-2】annotation は cold path（発見）。リアルタイムは streaming/RT OLAP が担い、hot path に置かない。
- **リアルタイム OLAP archetype**: 【EXT-3/B3】Iceberg ゆえ Trino/Spark/ClickHouse でも読める（UC ブロック迂回の代替）。読み取りはバージョン/設定依存で要検証。
- **自動車・製造データ基盤 archetype**: 【EXT-4/B4】スケール時のコスト/保持方針。製造トレーサビリティ schema。genealogy>1000 は構造化ペイロードで1個に。
- **ガバナンス archetype**: 【EXT-5/B5】ガバナンス2平面（LF vs UC）。annotation→tag マッピング。**annotation はミュータブル → 書き込み権限の最小権限統制が必須（改ざん防止）**。

### Final Recommendation（収束後・EXT 反映）
- **APPROVE WITH COMMENTS（収束）** — 案1 は attach まで実証済みで着手可能。**案1 の scale-query は AWS ネイティブ（Athena/Trino/Spark/ClickHouse）でサポート済**（backfill/LF 設定が前提）、**ブロックは案3（Databricks UC `iceberg_rest`）のみ**（EXT-1 で Round 2 の誤りを訂正）。案2 は「発見シグナル（非強制・読み取り二重チェック + 書き込み統制）」を厳守。
- Required Next Actions: §7 の未検証/設計待ち項目（#3 AWS ネイティブ query 実機検証、#5 UC 参照、#11–15 トレーサビリティ/tag マッピング/オープンエンジン/書き込み統制）を Phase 化。AWS / Databricks へ §8 のフィードバック提出。
- Public Repository Readiness: Ready（機密区分遵守。個人名・社名は非記載、provenance は `.private/` に分離。Round 1–3 + 外部レビュー後も確認済み）。

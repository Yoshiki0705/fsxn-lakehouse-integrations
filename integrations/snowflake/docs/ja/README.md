# Snowflake 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: ✅ 検証済み（`AWS_ACCESS_POINT_ARN` 使用）**
>
> Snowflake は `AWS_ACCESS_POINT_ARN` ステージパラメータを使用して FSx for ONTAP S3 Access Point のデータをクエリできます。
> このパラメータを設定すると、SELECT、External Table 作成、LIST が全て動作します。
> 設定しない場合、LIST は動作しますが SELECT は "access denied" で失敗します。

## 検証結果

| 操作 | `AWS_ACCESS_POINT_ARN` なし | `AWS_ACCESS_POINT_ARN` あり |
|---|:---:|:---:|
| Storage Integration | ✅ | ✅ |
| ステージ作成 | ✅ | ✅ |
| LIST @stage | ✅ | ✅ |
| SELECT @stage (Parquet) | ❌ Access Denied | ✅ |
| SELECT @stage (CSV) | ❌ | ✅ |
| External Table | ❌ | ✅ |
| COPY INTO (ロード) | ❌ | ✅ |
| ガバナンスタグ | N/A | ✅ |
| Snowpipe (自動取り込み) | ❌ | ❌ (S3 Event Notifications 非サポート) |
| Iceberg Table 書き込み | ❌ | ❌ (conditional writes 非サポート) |
| GET_PRESIGNED_URL | ✅ (動作確認済み) | ✅ |

## 概要

Amazon FSx for NetApp ONTAP（FSx for ONTAP）の S3 Access Point を Snowflake の External Stage として統合し、External Table / Iceberg Table のストレージレイヤーとして使用するパターンです。

## アーキテクチャ

```
┌───────────────────────────────────────────────────────────────────────┐
│                              AWS アカウント                             │
│                                                                       │
│  ┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐  │
│  │ FSx for ONTAP   │     │ FSx for ONTAP    │     │ IAM ロール     │  │
│  │ (NFS ボリューム)  │◀───▶│ S3 Access Point  │◀────│ (Snowflake    │  │
│  │                 │     │ (Internet origin) │     │  AssumeRole)  │  │
│  └─────────────────┘     └────────┬─────────┘     └───────┬───────┘  │
│                                    │                        │         │
└────────────────────────────────────┼────────────────────────┼─────────┘
                                     │ S3 API                 │ STS
                                     ▼                        ▼
                          ┌────────────────────────────────────────────┐
                          │  Snowflake (SaaS — ap-northeast-1)         │
                          │                                            │
                          │  Storage Integration → External Stage      │
                          │       → External Table / Iceberg Table     │
                          │       → Snowpipe (FPolicy + SNS 経由)       │
                          └────────────────────────────────────────────┘
```

## データフォーマット対応

| フォーマット | 読み取り | 書き込み | テーブルタイプ |
|------------|---------|---------|-------------|
| Parquet | ✅ | ✅ | External Table / Iceberg |
| CSV | ✅ | ✅ | External Table |
| JSON | ✅ | ✅ | External Table |
| ORC | ✅ | ❌ | External Table |
| Avro | ✅ | ❌ | External Table |

## 内部テーブル vs 外部テーブル — 設計ガイド

FSx for ONTAP と Snowflake を統合する際、内部（マネージド）テーブルと外部テーブルの違いを理解することがアーキテクチャ判断に不可欠です。

> **主要概念**: [外部ステージ](https://docs.snowflake.com/en/user-guide/data-load-s3-create-stage)（S3/クラウドストレージ）| [内部ステージ](https://docs.snowflake.com/en/user-guide/data-load-local-file-system-create-stage)（Snowflake マネージド）| [外部テーブル](https://docs.snowflake.com/en/user-guide/tables-external)（ステージから読み取り）| [COPY INTO](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)（内部テーブルにロード）
>
> AI/ML 固有の影響（各パターンでどの Cortex 関数が動作するか）については [AI/ML デモガイド](ai-demo-guide.md) の互換性マトリクスを参照。

### 比較マトリクス

| 観点 | 外部テーブル（FSx S3 AP 上） | 内部テーブル（COPY INTO） |
|---|---|---|
| **データ所在** | FSx for ONTAP に残る（ゼロコピー） | Snowflake マネージドストレージにコピー |
| **データ所有権** | 顧客がデータライフサイクルを管理 | Snowflake がストレージライフサイクルを管理 |
| **DROP TABLE 動作** | データは削除されない（メタデータのみ削除） | Snowflake ストレージからデータが削除される |
| **マルチプロトコルアクセス** | 同一データに NFS/SMB/S3 AP で同時アクセス可能 | Snowflake 経由のみアクセス可能 |
| **データ鮮度** | リアルタイム（現在のファイル状態を読み取り） | 次の COPY INTO / Snowpipe まで古い |
| **クエリ性能** | 遅い（S3 API レイテンシ、マイクロパーティションなし） | 速い（最適化マイクロパーティション、プルーニング） |
| **ガバナンス（タグ、マスキング）** | ✅ 完全サポート（Enterprise Edition） | ✅ 完全サポート |
| **Time Travel** | ❌ 利用不可 | ✅ 利用可能（最大90日） |
| **クラスタリング / 最適化** | ❌ 利用不可 | ✅ AUTO_CLUSTERING, OPTIMIZE |
| **Cortex AI（テキスト関数）** | ✅ 直接（SUMMARIZE, TRANSLATE 等） | ✅ 直接 |
| **Cortex AI（Vision/TO_FILE）** | ❌ FSx S3 AP で TO_FILE ブロック | ✅ 内部ステージで動作 |
| **ONTAP 機能の保持** | ✅ Snapshot, FlexClone, Dedup, FPolicy | ❌ データは ONTAP 外 |
| **ストレージコスト** | FSx for ONTAP のみ（Snowflake ストレージなし） | FSx + Snowflake ストレージ（重複） |
| **コンプライアンス（データレジデンシー）** | ✅ データは FSx に残る（管理された場所） | ⚠️ Snowflake マネージドストレージにデータ |

### 外部テーブルを選ぶべき場合（ゼロコピーパターン）

```
FSx for ONTAP ──S3 AP──▶ Snowflake External Table ──▶ クエリ / ガバナンス / AI
     │
     └── 同一データに NFS/SMB でアクセス可能（コピーなし）
```

**外部テーブルを選択する条件:**
- データが FSx for ONTAP に残る必要がある（コンプライアンス、データレジデンシー、マルチプロトコル）
- 現在のファイル状態へのリアルタイムアクセスが必要
- ONTAP 機能（Snapshot, FlexClone, FPolicy, SnapLock）を保持する必要がある
- ストレージコスト最適化が優先（重複ストレージを回避）
- 読み取り中心で更新頻度が低いデータ
- 複数のコンシューマー（NFS ユーザー、Snowflake、Athena 等）が同じデータを必要とする

**制限事項:**
- Time Travel、クラスタリング、マイクロパーティション最適化なし
- クエリ性能は FSx S3 AP レイテンシとファイルレイアウトに依存
- TO_FILE（Vision AI）が直接動作しない — COPY FILES 回避策が必要
- AUTO_REFRESH 利用不可（手動 REFRESH またはスケジュール Task が必要）

### 内部テーブルを選ぶべき場合（COPY INTO パターン）

```
FSx for ONTAP ──S3 AP──▶ COPY INTO ──▶ Snowflake 内部テーブル ──▶ クエリ / AI / Time Travel
                                              │
                                              └── 最適化マイクロパーティション、全 Snowflake 機能
```

**内部テーブルを選択する条件:**
- 最大クエリ性能が必要（マイクロパーティション、プルーニング、クラスタリング）
- Time Travel（ポイントインタイムクエリ、UNDROP）が必要
- Vision AI / TO_FILE を回避策なしで使用したい
- データ変換（ELT）がパイプラインの一部
- Snowflake ネイティブ機能（Streams, Tasks, Dynamic Tables）が必要
- COPY INTO 実行間のデータ鮮度の遅延を許容できる

**制限事項:**
- データが重複（FSx + Snowflake ストレージコスト）
- データ鮮度は COPY INTO 頻度に依存
- ONTAP 機能（Snapshot, FlexClone）はコピーに適用されない
- データレジデンシーが Snowflake マネージドストレージに移行

### ハイブリッドパターン（AI/ML ワークロード推奨）

```
FSx for ONTAP
     │
     ├── External Table（構造化データ）──▶ テキスト AI（SUMMARIZE, TRANSLATE, SENTIMENT）
     │                                     ガバナンス（タグ、マスキング、Row Policy）
     │
     └── COPY FILES → 内部ステージ ──▶ Vision AI（COMPLETE multimodal）
                                        Document AI（TO_FILE が必要な場合）
```

**ベストプラクティス**: ガバナンス付き読み取りアクセスとテキストベース AI には External Table を使用。Vision AI（TO_FILE）が必要な場合のみ COPY FILES で内部ステージにコピー。

### 判断フローチャート

```
Q: データは FSx for ONTAP に残す必要がある？
├── YES → External Table
│         Q: 画像に対する Vision AI が必要？
│         ├── YES → Vision AI 用のみ COPY FILES で内部ステージへ
│         └── NO → External Table で十分（テキスト AI は直接動作）
│
└── NO → COPY INTO で内部テーブル
          Q: リアルタイムの鮮度が必要？
          ├── YES → Snowpipe（S3 バケットの場合）またはスケジュール COPY INTO（FSx S3 AP の場合）
          └── NO → バッチ COPY INTO をスケジュール実行
```

### コスト比較

| パターン | FSx ストレージ | Snowflake ストレージ | Snowflake コンピュート | 合計 |
|---|---|---|---|---|
| External Table のみ | ✅（既存） | なし | クエリ時間のみ | 最低 |
| COPY INTO（全量） | ✅（既存） | + 全量コピー | クエリ + COPY 時間 | 最高 |
| ハイブリッド（External + 選択的 COPY） | ✅（既存） | + 画像のみ | クエリ + 選択的 COPY | 中間 |

### AI レディネススコア

| パターン | ガバナンス | 性能 | AI 機能 | コスト | 運用容易性 | 総合 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **External Table のみ** | ★★★★☆ | ★★☆☆☆ | ★★★★☆ (テキスト AI 直接) | ★★★★★ | ★★★★☆ | **4.0** |
| **COPY INTO（全量）** | ★★★★★ | ★★★★★ | ★★★★★ (全 AI) | ★★☆☆☆ | ★★★☆☆ | **3.8** |
| **ハイブリッド（External + Vision 用 COPY）** | ★★★★☆ | ★★★☆☆ | ★★★★★ (全 AI) | ★★★★☆ | ★★★☆☆ | **3.8** |

- **ガバナンス**: Tag-based masking、Row Policy、監査証跡
- **性能**: クエリレイテンシ、最適化機能
- **AI 機能**: 回避策なしで動作する Cortex 関数の数
- **コスト**: ストレージ効率（重複回避）
- **運用容易性**: セットアップとメンテナンスの手間

### リファレンス

- [Snowflake External Tables](https://docs.snowflake.com/en/user-guide/tables-external)
- [COPY INTO table](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)
- [COPY FILES](https://docs.snowflake.com/en/sql-reference/sql/copy-files)
- [Directory Tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables)
- [Time Travel](https://docs.snowflake.com/en/user-guide/data-time-travel)

## 非構造化データ対応

| フォーマット | アクセス方法 | ユースケース |
|------------|------------|------------|
| 画像 (JPEG, PNG, TIFF) | GET_PRESIGNED_URL / BUILD_SCOPED_FILE_URL | サムネイル生成、ML 推論、品質検査 |
| 動画 (MP4, MOV) | GET_PRESIGNED_URL | ストリーミング、フレーム抽出 |
| ドキュメント (PDF, DOCX) | GET_PRESIGNED_URL / Snowpark File Access | テキスト抽出、RAG、文書処理 |
| 音声 (WAV, MP3) | GET_PRESIGNED_URL | 文字起こし、音声分析 |
| バイナリ / アーカイブ | GET_PRESIGNED_URL | ダウンロード、転送 |

**非構造化データへのアクセス方法:**
1. **Directory Table** — ファイルのメタデータ（パス、サイズ、更新日時）をカタログとして管理
2. **GET_PRESIGNED_URL()** — アプリケーション向けの期限付きダウンロード URL を生成
3. **BUILD_SCOPED_FILE_URL()** — Snowflake 経由のセキュアな URL を生成
4. **Snowpark File Access** — UDF/UDTF 内でファイルを直接処理（要検証）

```sql
-- Directory Table を有効化してファイルカタログとして使用
ALTER STAGE fsxn_stage SET DIRECTORY = (ENABLE = TRUE);
ALTER STAGE fsxn_stage REFRESH;

-- ファイルカタログをクエリ
SELECT RELATIVE_PATH, SIZE, LAST_MODIFIED FROM DIRECTORY(@fsxn_stage);

-- ダウンロード URL を生成（1時間有効）
SELECT GET_PRESIGNED_URL(@fsxn_stage, 'images/photo001.jpg', 3600);
```

> **注意**: FSx S3 AP は S3 Event Notifications をサポートしていないため、AUTO_REFRESH は使用できません。`ALTER STAGE REFRESH` を手動または Snowflake Task でスケジュール実行してください。

## ONTAP の価値

| ONTAP 機能 | Snowflake へのメリット | リファレンス |
|---|---|---|
| **FlexCache** | リージョン/拠点間でデータをキャッシュし低遅延の Snowflake アクセスを実現。WAN 帯域を削減 | [FlexCache ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html) |
| **SnapLock / Tamperproof Snapshot** | コンプライアンス向け不変データ保護 — 管理者権限でも保持期間中は削除不可 | [SnapLock on FSx](https://netapp.com/blog/snaplock-on-amazon-fsx-ontap/) |
| **ARP/AI** | AI によるランサムウェア検知。分析データへの被害拡大前に自動スナップショット | [ARP on FSx](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/ARP.html) |
| **FlexClone** | 本番データを使った即時ステージング環境（ゼロコピー） | [FlexClone ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| **Snapshot** | Snowflake Time Travel 保持期間を超えたデータ復旧。データパイプラインのバージョン管理 | [Snapshot ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapshots-ontap.html) |
| **FabricPool** | 過去パーティションの S3 自動階層化（Snowflake クエリに透過的） | [FabricPool ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/fabricpool.html) |
| **ストレージ効率化** | 重複排除 + 圧縮 + コンパクションでファイルデータを最大 65% 削減 | [ストレージ効率](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/storage-efficiency.html) |
| **SnapMirror** | Snowflake レプリケーションと DR 向けクロスリージョンデータ可用性 | [SnapMirror ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html) |
| **マルチプロトコル** | NFS（取り込み）+ SMB（Windows ユーザー）+ S3 AP（Snowflake）— 同一データ、コピー不要 | [マルチプロトコル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html) |
| **FPolicy** | Lambda 経由のイベント駆動 Snowpipe 取り込み（<30秒レイテンシ） | [FPolicy ドキュメント](https://docs.netapp.com/us-en/ontap/nas-audit/fpolicy-config-types-concept.html) |

## ガバナンス & AI/ML ガイド

| ガイド | 説明 |
|---|---|
| [AI/ML デモガイド](ai-demo-guide.md) | Cortex AI デモ（OCR、SUMMARIZE、Vision）、業界別ユースケース、AI 向け ONTAP 価値 |
| [ガバナンス: タグとデータ保護](ai-demo-guide.md#ガバナンスタグとデータ保護) | Tag-based masking、Row Access Policy、エディション要件 |
| [ガバナンス: ファイルレベルアクセス制御](ai-demo-guide.md#ファイルレベルのアクセス制御-ontap-ネイティブレイヤー) | ONTAP デュアルレイヤー認可、FPolicy、コンシューマーごとの S3 AP 分離 |
| [統合: ONTAP × Snowflake タグ](ai-demo-guide.md#統合-ontap-ファイルレベル制御--snowflake-タグガバナンス) | 組み合わせガバナンスマトリクス、設計パターン、フロー図 |

## クイックスタート

```bash
# 1. FSx for ONTAP S3 Access Point を作成（前提条件）
aws fsx create-and-attach-s3-access-point \
  --name snowflake-ap --type ONTAP \
  --ontap-configuration 'VolumeId=fsvol-xxx,FileSystemIdentity={Type=UNIX,UnixUser={Name=root}}'

# 2. CloudFormation で IAM ロールをデプロイ
cp params.example.json params.json  # 編集: S3AccessPointArn を設定
./deploy.sh

# 3. Snowflake で SQL スクリプトを実行 (01 → 09)
```

## 既知の制限事項

1. **FSx for ONTAP S3 AP レイテンシ**: ListObjects に数十秒〜数分かかる場合がある
2. **Pre-signed URL**: AWS ドキュメントでは「非サポート」だが、実際には `GET_PRESIGNED_URL()` で動作確認済み
3. **S3 Event Notifications 非サポート**: Snowpipe の直接トリガー不可（FPolicy で代替）
4. **最大アップロードサイズ**: 5GB（Multipart Upload 対応）
5. **AUTO_REFRESH 不可**: 手動 REFRESH または Snowflake Task でスケジュール実行が必要
6. **TO_FILE / FILE データ型**: FSx S3 AP 外部ステージでは "Remote file not found" — Vision AI に直接使用不可。回避策: `COPY FILES` で暗号化なし内部ステージ（SNOWFLAKE_SSE）にコピー後、`TO_FILE(BUILD_SCOPED_FILE_URL(@internal_stage, path))` を使用

## 顧客適格化質問

アーキテクチャパターンを決定するための質問:

1. **データレジデンシー**: データは FSx for ONTAP に残す必要がある？ Snowflake マネージドストレージにコピー可能？
   - FSx に残す → External Table パターン
   - コピー可 → COPY INTO で最大性能

2. **AI/ML 要件**: テキスト AI（要約、翻訳、OCR）が必要？ Vision AI（画像分析）が必要？
   - テキスト AI のみ → External Table（直接、コピー不要）
   - Vision AI 必要 → ハイブリッドパターン（External Table + 画像のみ COPY FILES）

3. **クエリ性能**: サブ秒のレスポンスが必要？ 秒レベルで許容可能？
   - サブ秒 → COPY INTO 内部テーブル（マイクロパーティション、クラスタリング）
   - 秒レベル → External Table（S3 AP レイテンシ）

4. **コンプライアンス制約**: データ移動を制限する規制要件（HIPAA, SOX, GDPR）がある？
   - あり → External Table + SnapLock + FPolicy 監査（データは FSx から出ない）
   - なし → 性能/コストのトレードオフで選択

5. **マルチプロトコルアクセス**: NFS/SMB ユーザーが Snowflake と同じデータにアクセスする必要がある？
   - あり → External Table（ゼロコピー、マルチプロトコル）
   - なし → どちらのパターンでも可

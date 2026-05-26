🌐 [English](../en/internal-table-ingestion-guide.md) | **日本語**

# 内部テーブル取り込みガイド — COPY INTO が必要なケース

> **ステータス**: アーキテクチャリファレンス — 検証結果に基づく（2026年5月）
>
> **コンテキスト**: FSx for ONTAP S3 Access Points は Snowflake External Table でのゼロコピー読み取りアクセスに対応しています。しかし、多くの Snowflake 機能は**内部（マネージド）テーブル**にデータが存在することを要求します。このガイドでは、どの機能が COPY INTO を必要とし、推奨される取り込みパターンを文書化しています。

## エグゼクティブサマリー

FSx for ONTAP S3 AP 上の Snowflake External Table は**ガバナンス付きゼロコピー読み取りアクセス**を提供しますが、設計上読み取り専用です。多くの高度な Snowflake 機能（Cortex Search、Dynamic Tables、Time Travel、DML、クラスタリング）はデータが内部テーブルに存在することを要求します。

これにより**二重管理の課題**が生じます：データは FSx for ONTAP（Source of Truth）に存在し、プラットフォームの全機能を利用するには Snowflake 内部テーブルにコピーする必要があります。

### 基本原則

1. **External Table = ゼロコピーのガバナンス付き読み取り** — データ移動なし、ただし機能制限あり
2. **Internal Table = Snowflake の全機能** — COPY INTO が必要（データ重複）
3. **ブリッジは COPY INTO** — 外部ステージファイルをクエリ可能な内部テーブルに変換
4. **同期が課題** — FSx for ONTAP S3 AP は S3 Event Notifications をサポートしないため、変更検知にはポーリングまたは FPolicy が必要

---

## 機能利用可否: External Table vs Internal Table

### Cortex AI 関数

| 関数 | External Table | Internal Table | COPY INTO 必要 | 参照 |
|------|:---:|:---:|:---:|---|
| [CORTEX.SUMMARIZE](https://docs.snowflake.com/en/sql-reference/functions/summarize-snowflake-cortex) | ✅ | ✅ | 不要 | 任意のテキストカラムで動作 |
| [CORTEX.TRANSLATE](https://docs.snowflake.com/en/sql-reference/functions/translate-snowflake-cortex) | ✅ | ✅ | 不要 | 任意のテキストカラムで動作 |
| [CORTEX.SENTIMENT](https://docs.snowflake.com/en/sql-reference/functions/sentiment-snowflake-cortex) | ✅ | ✅ | 不要 | 任意のテキストカラムで動作 |
| [CORTEX.EXTRACT_ANSWER](https://docs.snowflake.com/en/sql-reference/functions/extract_answer-snowflake-cortex) | ✅ | ✅ | 不要 | 任意のテキストカラムで動作 |
| [CORTEX.COMPLETE](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex) (テキスト) | ✅ | ✅ | 不要 | 任意のテキストカラムで動作 |
| [CORTEX.COMPLETE](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal) (マルチモーダル/Vision) | ❌ | ✅ | **必要** | 内部/マネージドステージの TO_FILE が必要 |
| [PARSE_DOCUMENT](https://docs.snowflake.com/en/sql-reference/functions/parse_document) | ✅ | ✅ | 不要 | 外部ステージの BUILD_SCOPED_FILE_URL で動作 |
| [Cortex Search Service](https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search) | ❌ | ✅ | **必要** | ソースクエリは内部テーブルまたは内部テーブル上のビューを参照する必要あり |

### データ管理機能

| 機能 | External Table | Internal Table | COPY INTO 必要 | 参照 |
|------|:---:|:---:|:---:|---|
| SELECT / クエリ | ✅ | ✅ | 不要 | |
| DML (INSERT/UPDATE/DELETE/MERGE) | ❌ | ✅ | **必要** | External Table は読み取り専用 |
| [Time Travel](https://docs.snowflake.com/en/user-guide/data-time-travel) | ❌ | ✅ | **必要** | DATA_RETENTION_TIME_IN_DAYS 付き内部テーブルが必要 |
| [Fail-safe](https://docs.snowflake.com/en/user-guide/data-failsafe) | ❌ | ✅ | **必要** | Time Travel 期限後の7日間リカバリ |
| [クラスタリング](https://docs.snowflake.com/en/user-guide/tables-clustering-micropartitions) | ❌ | ✅ | **必要** | マイクロパーティションは内部テーブルのみ |
| [Search Optimization](https://docs.snowflake.com/en/user-guide/search-optimization-service) | ❌ | ✅ | **必要** | 内部テーブルが必要 |
| [Dynamic Tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-intro) | ⚠️ ソースのみ | ✅ | 部分的 | External Table をソースとして読み取り可能、出力は内部 |
| [Streams](https://docs.snowflake.com/en/user-guide/streams-intro) (CDC) | ❌ | ✅ | **必要** | External Table では非サポート |
| [Tasks](https://docs.snowflake.com/en/user-guide/tasks-intro) | ✅ | ✅ | 不要 | COPY INTO や REFRESH のスケジュールに使用可能 |
| [Materialized Views](https://docs.snowflake.com/en/user-guide/views-materialized) | ✅ | ✅ | 不要 | External Table 上に作成可能（パフォーマンス向上） |

### ガバナンス機能

| 機能 | External Table | Internal Table | COPY INTO 必要 | 参照 |
|------|:---:|:---:|:---:|---|
| [オブジェクトタグ](https://docs.snowflake.com/en/user-guide/object-tagging) | ✅ | ✅ | 不要 | 両方で動作 |
| [Row Access Policy](https://docs.snowflake.com/en/user-guide/security-row-intro) | ✅ | ✅ | 不要 | 両方で動作 |
| [カラムマスキング](https://docs.snowflake.com/en/user-guide/security-column-intro) | ✅ | ✅ | 不要 | 両方で動作 |
| [データ共有](https://docs.snowflake.com/en/user-guide/data-sharing-intro) | ✅ | ✅ | 不要 | External Table も共有可能 |
| [アクセス履歴](https://docs.snowflake.com/en/user-guide/access-history) | ✅ | ✅ | 不要 | 両方で追跡 |

### ファイル & 非構造化データ機能

| 機能 | External Stage (FSx for ONTAP S3 AP) | Internal Stage | COPY INTO 必要 | 参照 |
|------|:---:|:---:|:---:|---|
| [LIST @stage](https://docs.snowflake.com/en/sql-reference/sql/list) | ✅ | ✅ | 不要 | |
| [GET_PRESIGNED_URL](https://docs.snowflake.com/en/sql-reference/functions/get_presigned_url) | ✅ | ✅ | 不要 | AWS ドキュメントでは「非サポート」と記載されているが動作 |
| [BUILD_SCOPED_FILE_URL](https://docs.snowflake.com/en/sql-reference/functions/build_scoped_file_url) | ✅ | ✅ | 不要 | |
| [Directory Table](https://docs.snowflake.com/en/user-guide/data-load-dirtables) | ✅ | ✅ | 不要 | ENABLE + REFRESH が外部ステージで動作 |
| AUTO_REFRESH (Directory Table) | ❌ | ✅ | N/A | S3 Event Notifications が必要（FSx for ONTAP S3 AP 非サポート） |
| [Snowpipe](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-intro) (auto-ingest) | ❌ | N/A | N/A | S3 Event Notifications が必要 |
| [TO_FILE](https://docs.snowflake.com/en/sql-reference/functions/to_file) (マルチモーダル AI 用) | ❌ | ✅ | **必要** | 内部/マネージドステージパスのみで動作 |

---

## 二重管理問題

```
FSx for ONTAP (NFS/SMB)          Snowflake 内部テーブル
   ┌─────────────────┐              ┌─────────────────┐
   │ Source of Truth │──COPY INTO──▶│ 分析用コピー      │
   │ (マルチプロトコル) │              │ (全機能利用可.)   │
   └─────────────────┘              └─────────────────┘
         │                                   │
    NFS/SMB で更新                      同期が必要
         │                                   │
     ▼ 課題 ▼                             ▼ 課題 ▼
  - S3 Event Notifications なし       - データ鮮度リスク
  - 変更検知はポーリング              - ストレージコスト
  - 削除が自動伝播されない            - コンピュートコスト
                                      - スキーマドリフト管理
```

### 具体的な課題

| 課題 | 説明 | 軽減策 |
|------|------|--------|
| **変更検知** | FSx for ONTAP S3 AP は S3 Event Notifications 非サポート → Snowpipe トリガー不可 | FPolicy → Lambda → SNS → Snowpipe REST API、またはスケジュール Task + COPY INTO |
| **削除の伝播** | COPY INTO は追記型; FSx for ONTAP 上で削除されたファイルは内部テーブルから削除されない | 定期的な全量リフレッシュ、またはメタデータ比較による MERGE |
| **スキーマ進化** | ソースファイルの新カラムが自動反映されない | INFER_SCHEMA + ALTER TABLE、またはテーブル再作成 |
| **データ鮮度** | ポーリング間隔がラグを決定 | FPolicy で準リアルタイム、Task でスケジュール |
| **コスト** | Snowflake ストレージ + COPY INTO 実行のコンピュート | 非重要データには transient テーブル使用; ソースファイル圧縮 |

---

## 推奨取り込みパターン

### パターン 1: スケジュール COPY INTO（最もシンプル）

最適用途: バッチ分析、日次/時間単位のリフレッシュが許容される場合。

```sql
-- ターゲット内部テーブル作成
CREATE OR REPLACE TABLE sensor_data (
  device_id STRING,
  timestamp TIMESTAMP,
  temperature FLOAT,
  humidity FLOAT
) DATA_RETENTION_TIME_IN_DAYS = 7;

-- スケジュール Task: 1時間ごとに COPY INTO
CREATE OR REPLACE TASK copy_sensor_data
  WAREHOUSE = COMPUTE_WH
  SCHEDULE = '60 MINUTE'
AS
  COPY INTO sensor_data
  FROM @fsxn_stage/bronze/sensor/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE
  ON_ERROR = CONTINUE;
```

参照: [COPY INTO](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table), [Tasks](https://docs.snowflake.com/en/user-guide/tasks-intro)

### パターン 2: FPolicy → Lambda → Snowpipe REST API（準リアルタイム）

最適用途: イベント駆動取り込み、分単位のレイテンシ。

```
FSx for ONTAP (ファイル作成/変更)
  ↓ FPolicy 通知
AWS Lambda (イベントプロセッサ)
  ↓ Snowpipe REST API 呼び出し (insertFiles)
Snowflake Snowpipe (COPY INTO 内部テーブル)
  ↓
内部テーブル (Cortex Search, DML 等で利用可能)
```

```sql
-- Snowpipe 作成（REST API 経由でトリガー、auto-ingest ではない）
CREATE OR REPLACE PIPE fsxn_sensor_pipe
AS
  COPY INTO sensor_data
  FROM @fsxn_stage/bronze/sensor/
  FILE_FORMAT = (TYPE = PARQUET)
  MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE;
```

参照: [Snowpipe REST API](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-rest-apis), [FPolicy](https://docs.netapp.com/us-en/ontap/nas-audit/fpolicy-config-types-concept.html)

### パターン 3: Dynamic Table（自動変換） — 推奨

最適用途: External Table ソースからの継続的変換パイプライン。**最も Snowflake ネイティブなアプローチ** — 宣言的、自動管理、SELECT 句で Cortex AI 関数をサポート（2025年9月 GA）。

```sql
-- Dynamic Table: External Table から読み取り、内部として実体化
CREATE OR REPLACE DYNAMIC TABLE sensor_enriched
  TARGET_LAG = '1 hour'
  WAREHOUSE = COMPUTE_WH
AS
  SELECT
    device_id,
    timestamp,
    temperature,
    humidity,
    SNOWFLAKE.CORTEX.SENTIMENT(notes) AS sentiment_score,
    CURRENT_TIMESTAMP() AS enriched_at
  FROM sensor_external_table
  WHERE timestamp > DATEADD(day, -30, CURRENT_TIMESTAMP());
```

参照: [Dynamic Tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-intro)

> **注意**: Dynamic Table は External Table をソースとして使用可能（全量リフレッシュモード）。増分リフレッシュには変更追跡が必要で、External Table では利用不可。

> **Dynamic Table が COPY INTO + Task より推奨される理由**:
> - **宣言的**: TARGET_LAG（例: '1 hour'）を定義すれば Snowflake がリフレッシュスケジュールを自動管理
> - **Cortex AI 統合**: Dynamic Table の SELECT 句で CORTEX.SUMMARIZE、CORTEX.SENTIMENT 等を直接使用可能（[2025年9月 GA](https://docs.snowflake.com/en/release-notes/2025/other/2025-09-11-dynamic-tables-cortex-aisql-support)）
> - **運用オーバーヘッドなし**: Task スケジューリング、COPY INTO 重複排除ロジック、手動エラーハンドリングが不要
> - **チェーニング**: Dynamic Table は他の Dynamic Table を参照可能（Bronze → Silver → Gold のマルチステージパイプライン）

### パターン 4: COPY INTO + Cortex Search（RAG パイプライン）

最適用途: FSx for ONTAP ドキュメントに対するセマンティック検索。

```sql
-- ステップ 1: 外部ステージから内部テーブルに COPY INTO
CREATE OR REPLACE TABLE documents (
  file_path STRING,
  content STRING,
  file_type STRING,
  ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

COPY INTO documents (file_path, content, file_type)
FROM (
  SELECT
    METADATA$FILENAME,
    $1::STRING,
    SPLIT_PART(METADATA$FILENAME, '.', -1)
  FROM @fsxn_stage/bronze/documents/
)
FILE_FORMAT = (TYPE = CSV FIELD_DELIMITER = NONE RECORD_DELIMITER = NONE)
ON_ERROR = CONTINUE;

-- ステップ 2: 内部テーブル上に Cortex Search Service 作成
CREATE OR REPLACE CORTEX SEARCH SERVICE document_search
  ON content
  ATTRIBUTES file_type
  WAREHOUSE = COMPUTE_WH
  TARGET_LAG = '1 day'
AS (
  SELECT content, file_path, file_type
  FROM documents
);
```

参照: [CREATE CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search), [COPY INTO](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table)

### パターン 5: マルチモーダル AI (Vision) — 内部ステージ使用

最適用途: LLM Vision モデルによる画像/ドキュメント分析。

```sql
-- ステップ 1: ファイルを内部ステージにコピー（TO_FILE に必要）
COPY FILES
  INTO @internal_media_stage
  FROM @fsxn_stage/media/images/;

-- ステップ 2: TO_FILE で COMPLETE (マルチモーダル) を使用
SELECT
  RELATIVE_PATH AS file_name,
  SNOWFLAKE.CORTEX.COMPLETE(
    'claude-3-5-sonnet',
    'Describe this image in detail',
    TO_FILE(@internal_media_stage, RELATIVE_PATH)
  ) AS description
FROM DIRECTORY(@internal_media_stage)
WHERE RELATIVE_PATH LIKE '%.png' OR RELATIVE_PATH LIKE '%.jpg';
```

参照: [COMPLETE (マルチモーダル)](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal), [TO_FILE](https://docs.snowflake.com/en/sql-reference/functions/to_file)

---

## COPY INTO なしで動作するもの（External Table 上のゼロコピー）

以下の操作は FSx for ONTAP S3 AP External Table 上で直接動作します — データ移動不要:

| 操作 | 例 | パフォーマンス |
|------|---|---|
| アドホック SQL クエリ | `SELECT * FROM ext_table WHERE date > '2026-01-01'` | 中程度（マイクロパーティションなし） |
| テキスト AI 関数 | `SELECT CORTEX.SUMMARIZE(text_col) FROM ext_table` | 良好 |
| ガバナンスタグ | `ALTER TABLE ext_table SET TAG sensitivity = 'internal'` | 即時 |
| Row Access Policy | `ALTER TABLE ext_table ADD ROW ACCESS POLICY ...` | 即時 |
| カラムマスキング | `ALTER TABLE ext_table MODIFY COLUMN ssn SET MASKING POLICY ...` | 即時 |
| Materialized View | `CREATE MATERIALIZED VIEW mv AS SELECT ... FROM ext_table` | クエリ性能向上 |
| データ共有 | `GRANT SELECT ON ext_table TO SHARE ...` | 即時 |
| Presigned URL | `SELECT GET_PRESIGNED_URL(@stage, path) FROM dir_table` | 高速 |
| ドキュメントパース | `SELECT PARSE_DOCUMENT(BUILD_SCOPED_FILE_URL(@stage, path))` | 約8秒/ドキュメント |

---

## 判断フレームワーク

```
                    ┌─────────────────────────┐
                    │ 何が必要ですか？         │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
    ┌─────────▼─────────┐ ┌─────▼─────┐ ┌─────────▼─────────┐
    │ 読み取り専用 SQL + │ │ RAG /     │ │ DML / Time Travel │
    │ 基本 AI + ガバナンス│ │ Cortex    │ │ / クラスタリング / │
    │                   │ │ Search    │ │ マルチモーダル AI  │
    └─────────┬─────────┘ └─────┬─────┘ └─────────┬─────────┘
              │                  │                  │
    ┌─────────▼─────────┐ ┌─────▼─────┐ ┌─────────▼─────────┐
    │ External Table    │ │ COPY INTO │ │ COPY INTO         │
    │ (ゼロコピー)      │ │ + Cortex  │ │ 内部テーブル      │
    │                   │ │ Search    │ │                   │
    └───────────────────┘ └───────────┘ └───────────────────┘
```

| 要件 | 推奨パス | データ移動 |
|------|----------|-----------|
| アドホック分析、レポーティング | External Table | なし（ゼロコピー） |
| タグ/マスキング付きガバナンス読み取り | External Table | なし |
| テキスト要約、翻訳、感情分析 | External Table | なし |
| ドキュメントパース (OCR) | External Stage + PARSE_DOCUMENT | なし |
| セマンティック検索 (RAG) | COPY INTO → Cortex Search Service | 全量コピー |
| 画像/動画分析 (マルチモーダル) | COPY FILES → 内部ステージ → COMPLETE | 全量コピー |
| DML (INSERT/UPDATE/DELETE/MERGE) | COPY INTO 内部テーブル | 全量コピー |
| Time Travel / ポイントインタイムリカバリ | COPY INTO 内部テーブル | 全量コピー |
| 高性能クエリ (クラスタリング) | COPY INTO 内部テーブル | 全量コピー |
| CDC / Streams | COPY INTO 内部テーブル | 全量コピー |

---

## コスト考慮事項

| コンポーネント | External Table パス | COPY INTO パス |
|------------|---|---|
| FSx for ONTAP ストレージ | ✅（Source of Truth） | ✅（Source of Truth） |
| Snowflake ストレージ | なし | 追加（内部テーブル） |
| Snowflake コンピュート（クエリ） | クエリごと | クエリごと |
| Snowflake コンピュート（COPY INTO） | なし | 定期的な取り込みコスト |
| データ鮮度 | リアルタイム（直接読み取り） | ポーリング間隔のラグ |
| 運用複雑度 | 低 | 中（同期ロジック必要） |

**コスト最適化のヒント:**
- 非重要データには [transient テーブル](https://docs.snowflake.com/en/user-guide/tables-temp-transient) を使用（Fail-safe コストなし）
- 適切な `DATA_RETENTION_TIME_IN_DAYS` を設定（1日 vs 90日）
- COPY INTO で `MATCH_BY_COLUMN_NAME` を使用してスキーマ進化に対応
- ソースファイルを圧縮（CSV より Parquet 推奨）
- ソースファイルをクリーンアップ可能な場合は COPY INTO で `PURGE = TRUE` を使用

---

## 参考資料

- [COPY INTO <table>](https://docs.snowflake.com/en/sql-reference/sql/copy-into-table) — ステージからテーブルへのデータロード
- [External Tables](https://docs.snowflake.com/en/user-guide/tables-external-intro) — 外部ストレージ上の読み取り専用テーブル
- [Cortex AI Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) — LLM 関数概要
- [CREATE CORTEX SEARCH SERVICE](https://docs.snowflake.com/en/sql-reference/sql/create-cortex-search) — セマンティック検索
- [COMPLETE (マルチモーダル)](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal) — Vision/画像 AI
- [Dynamic Tables](https://docs.snowflake.com/en/user-guide/dynamic-tables-intro) — 自動変換
- [Snowpipe REST API](https://docs.snowflake.com/en/user-guide/data-load-snowpipe-rest-apis) — プログラマティック取り込みトリガー
- [FSx for ONTAP S3 Access Points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-access-points.html) — AWS ドキュメント

---

## 関連ドキュメント

- [Snowflake README](../../README.md) — 統合ステータス全体
- [Analytics & AI デモガイド](ai-demo-guide.md) — AI/ML 機能と検証結果
- [サポートケースサマリー](../../.private/support-case-01357726-summary-ja.md) — S3 AP 解決の詳細（プライベート）

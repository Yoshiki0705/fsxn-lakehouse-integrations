🌐 [English](../en/ai-demo-guide.md) | **日本語**

# Snowflake Cortex AI デモガイド — FSx for ONTAP S3 AP

本ガイドでは、`AWS_ACCESS_POINT_ARN` を使用した Snowflake External Stage 経由で FSx for ONTAP データに対する AI/ML 機能を実演します。

## 前提条件

- Cortex AI が有効な Snowflake アカウント
- FSx for ONTAP S3 Access Point の設定完了
- `AWS_ACCESS_POINT_ARN` を使用した External Stage（[README](../../README.md) 参照）

## デモ 1: OCR テキスト抽出 (PARSE_DOCUMENT)

**ユースケース**: NAS に保存された検査報告書、請求書、品質文書からテキストを抽出。

```sql
-- OCR: FSx for ONTAP 上の画像からテキスト抽出
SELECT SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
  @fsxn_stage,
  'media/documents/invoice_sample.png',
  {'mode': 'OCR'}
) AS ocr_result;
```

**結果**: 画像から構造化テキストを抽出（約8秒）。

![PARSE_DOCUMENT OCR が FSx S3 AP 上の画像からテキストを抽出](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/snowflake-08-parse-document-ocr.png)

*PARSE_DOCUMENT が FSx for ONTAP S3 Access Point 経由で保存された請求書画像からテキストを抽出。請求書番号、顧客名、金額などの構造化フィールドを含む結果を返却。*

**製造業ユースケース**: NFS に保存された紙ベースの検査報告書をデジタル化し、手動データ入力なしで検索・分析可能に。

## デモ 2: AI テキスト要約 (CORTEX.SUMMARIZE)

**ユースケース**: センサーデータ、ログファイル、ドキュメント内容を要約し、迅速なインサイトを取得。

```sql
-- External Table からセンサーデータを要約
SELECT SNOWFLAKE.CORTEX.SUMMARIZE(VALUE::VARCHAR) AS ai_summary
FROM fsxn_sensor_ext_table
LIMIT 1;
```

**結果**: "The text is a JSON object containing data on humidity, pressure, temperature, sensor ID, status, and timestamp."（3.3秒）

![Cortex SUMMARIZE が External Table 経由で FSx S3 AP データの AI 要約を生成](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/snowflake-07-cortex-llm-summary.png)

*Cortex SUMMARIZE が FSx for ONTAP に保存されたセンサーデータの AI 要約を生成（External Table 経由、3.3秒）。*

**製造業ユースケース**: FSx for ONTAP に保存された IoT センサーデータからシフトサマリーを自動生成。

## デモ 3: ファイルカタログ + ダウンロード URL

**ユースケース**: 非構造化データ（画像、動画、ドキュメント）を検索可能なライブラリとして管理。

```sql
-- ファイルカタログを有効化
ALTER STAGE fsxn_stage SET DIRECTORY = (ENABLE = TRUE);
ALTER STAGE fsxn_stage REFRESH;

-- 検査画像を検索
SELECT RELATIVE_PATH, SIZE, LAST_MODIFIED,
  GET_PRESIGNED_URL(@fsxn_stage, RELATIVE_PATH, 3600) AS DOWNLOAD_URL
FROM DIRECTORY(@fsxn_stage)
WHERE RELATIVE_PATH LIKE 'media/images/%'
ORDER BY LAST_MODIFIED DESC;
```

**結果**: 各画像のダウンロード URL 付きファイルカタログ。

![Directory Table が FSx S3 AP 上の非構造化データをカタログ化し presigned URL を生成](https://raw.githubusercontent.com/Yoshiki0705/fsxn-lakehouse-integrations/main/docs/images/snowflake-06-directory-table-presigned-url.png)

*Directory Table が FSx for ONTAP 上の画像ファイルをメタデータ付きでカタログ化し、各ファイルのダウンロード URL を生成。*

**製造業ユースケース**: 品質エンジニアが日付/場所で検査写真を検索し、レビュー用にダウンロード。

## デモ 4: Vision AI による欠陥検出（検証中）

**ユースケース**: 製品品質検査に対する自然言語指示。

```sql
-- Vision AI: 製品検査画像を分析（構文要検証）
SELECT SNOWFLAKE.CORTEX.AI_COMPLETE(
  'claude-3-5-sonnet',
  'Analyze this product inspection image and identify any defects or quality issues.',
  {'image': BUILD_SCOPED_FILE_URL(@fsxn_stage, 'media/images/product_inspection.png')}
) AS defect_analysis;
```

**ステータス**: ⚠️ External Stage ファイルに対するマルチモーダル AI_COMPLETE の構文は追加検証が必要です。Snowflake で機能はサポートされていますが、ステージファイル URL をビジョンモデルに渡す正確な SQL 構文の確認が必要です。

**製造業ユースケース**: 自動視覚品質検査 — 「このコンポーネントの傷を特定」「このアセンブリのアライメントを確認」などの自然言語指示。

## 検証結果サマリー

| 機能 | ステータス | 所要時間 | ユースケース |
|---|:---:|---|---|
| PARSE_DOCUMENT (OCR) | ✅ 検証済み | 約8秒 | 請求書/報告書テキスト抽出 |
| CORTEX.SUMMARIZE | ✅ 検証済み | 3.3秒 | センサーデータ/ドキュメント要約 |
| Directory Table + URLs | ✅ 検証済み | 1.3秒 | 非構造化データカタログ |
| AI_COMPLETE (Vision) | ⚠️ 検証中 | — | 画像欠陥検出、歩留まり分析 |

## スクリーンショット

- OCR + クエリ履歴: `docs/images/snowflake-08-parse-document-ocr.png`
- Cortex SUMMARIZE: `docs/images/snowflake-07-cortex-llm-summary.png`
- Directory Table: `docs/images/snowflake-06-directory-table-presigned-url.png`

---

## 業界別ユースケース: Snowflake Cortex AI + FSx for ONTAP

### 製造業 / 品質検査

| ユースケース | Cortex 関数 | FSx 上のデータ | リファレンス |
|---|---|---|---|
| 検査報告書 OCR | PARSE_DOCUMENT (OCR モード) | スキャン報告書 (PNG/PDF) | [Snowflake PARSE_DOCUMENT ドキュメント](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document) |
| センサー異常要約 | CORTEX.SUMMARIZE | IoT センサー Parquet/CSV | [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |
| 外観欠陥検出 | AI_COMPLETE (vision) | 製品画像 | [AI_COMPLETE マルチモーダル](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal) |
| ダッシュボードからの歩留まり分析 | AI_COMPLETE (vision) | ダッシュボードスクリーンショット | [Image Analysis Quickstart](https://www.snowflake.com/en/developers/guides/build-image-analysis-app-with-streamlit-and-snowflake-cortex/) |

### 金融 / 保険

| ユースケース | Cortex 関数 | FSx 上のデータ | リファレンス |
|---|---|---|---|
| 請求書データ抽出 | PARSE_DOCUMENT (LAYOUT モード) | 請求書 PDF/画像 | [Document AI](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document) |
| 契約条項要約 | CORTEX.SUMMARIZE | 契約書ドキュメント | [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |
| 保険金請求書類処理 | PARSE_DOCUMENT + SUMMARIZE | 請求フォーム | [OCR + RAG Quickstart](https://quickstarts.snowflake.com/guide/getting_started_with_ocr_and_rag_with_snowflake_notebooks/) |
| 規制文書検索 | Cortex Search (COPY INTO 経由) | コンプライアンス文書 | [Cortex Search](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview) |

### 医療 / ライフサイエンス

| ユースケース | Cortex 関数 | FSx 上のデータ | リファレンス |
|---|---|---|---|
| 医療記録デジタル化 | PARSE_DOCUMENT (OCR) | スキャン記録 | [PARSE_DOCUMENT](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document) |
| 研究論文要約 | CORTEX.SUMMARIZE | PDF 論文 | [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |
| 検査報告テキスト抽出 | PARSE_DOCUMENT | 検査画像/PDF | [Document AI](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document) |
| 臨床試験データカタログ | Directory Table | 試験ドキュメント | [Directory Tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables) |

### メディア / コンテンツ管理

| ユースケース | Cortex 関数 | FSx 上のデータ | リファレンス |
|---|---|---|---|
| 画像メタデータ抽出 | AI_COMPLETE (vision) | メディアアセット | [AI_COMPLETE](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal) |
| 動画フレーム説明 | AI_COMPLETE (vision) | 抽出フレーム | [Image Analysis](https://www.snowflake.com/en/developers/guides/build-image-analysis-app-with-streamlit-and-snowflake-cortex/) |
| アセットカタログ管理 | Directory Table + Tags | 全メディアファイル | [Directory Tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables) |
| コンテンツ翻訳 | CORTEX.TRANSLATE | テキストドキュメント | [Cortex TRANSLATE](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions#label-cortex-llm-translate) |

### 業界横断: データエンジニアリング

| ユースケース | Cortex 関数 | FSx 上のデータ | リファレンス |
|---|---|---|---|
| ファイルからのスキーマ推論 | PARSE_DOCUMENT + LLM | 混合フォーマットファイル | [Cortex LLM](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |
| データ品質評価 | CORTEX.SUMMARIZE | データサンプル | [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |
| ファイル分類/タグ付け | AI_COMPLETE + Tags | 非構造化ファイル | [Governance Tags](https://docs.snowflake.com/en/user-guide/object-tagging/introduction) |
| 自動ドキュメント生成 | CORTEX.SUMMARIZE | コード/設定ファイル | [Cortex LLM Functions](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions) |

---

## AI/ML ワークロードにおける ONTAP の価値

| ONTAP 機能 | AI/ML メリット | リファレンス |
|---|---|---|
| **FlexCache** | リージョン/拠点間で学習データをキャッシュし低遅延アクセスを実現。分散 ML ワークロードの WAN 帯域を削減 | [FlexCache 概要](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html) |
| **SnapLock / Tamperproof Snapshot** | 不変のデータ保護 — 管理者権限でも保持期間中はロックされたスナップショットを削除不可。SEC 17a-4(f)、HIPAA、FINRA コンプライアンスに対応 | [SnapLock on FSx for ONTAP](https://netapp.com/blog/snaplock-on-amazon-fsx-ontap/) |
| **ARP/AI（自律型ランサムウェア防御）** | AI によるランサムウェア暗号化パターンのリアルタイム検知。被害拡大前に自動スナップショットを作成 | [ARP on FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/ARP.html) |
| **FlexClone** | ML 実験用のゼロコピー即時クローン — データを複製せずに異なる前処理をテスト | [FlexClone ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-volumes.html) |
| **Snapshot** | 学習データセットのポイントインタイムリカバリ。特徴量エンジニアリングパイプラインのバージョン管理 | [Snapshot ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapshots-ontap.html) |
| **FabricPool** | コールドな学習データや古いモデルアーティファクトを S3 に自動階層化 — Snowflake クエリに対して透過的 | [FabricPool ドキュメント](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/fabricpool.html) |
| **マルチプロトコル** | 同一データに NFS（データサイエンティスト）、SMB（Windows ユーザー）、S3 AP（Snowflake/分析）から同時アクセス可能 | [マルチプロトコルアクセス](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-fsx-clients.html) |

### AI/ML 固有のシナリオ

- **FlexCache による分散学習**: オンプレミス NAS からクラウド FSx for ONTAP に学習データセットをキャッシュ — ML クラスターが WAN を経由せずローカルキャッシュからサブミリ秒のレイテンシでデータを読み取り
- **SnapLock によるモデルガバナンス**: 学習データのスナップショットをロックし再現性を保証 — 監査人がモデル学習に使用された正確なデータセットが変更されていないことを検証可能
- **ARP/AI によるデータパイプライン保護**: 学習データやモデルアーティファクトを標的とするランサムウェアを検知・ブロック — 自動スナップショットがリカバリ用のクリーンな状態を保持

---

## はじめに

1. **FSx S3 AP ステージの設定** — [設定ガイド](../../README.md) に従う
2. **サンプルデータのアップロード** — NFS 経由で FSx for ONTAP に画像/ドキュメントを配置
3. **Directory Table の更新** — `ALTER STAGE REFRESH` で新規ファイルを検出
4. **Cortex 関数の実行** — 上記の SQL サンプルを使用
5. **Streamlit アプリの構築** — 画像サムネイル付きインタラクティブダッシュボード用

## Snowflake Cortex AI ドキュメント

- [Cortex AI 概要](https://docs.snowflake.com/en/user-guide/snowflake-cortex)
- [LLM Functions (SUMMARIZE, COMPLETE, TRANSLATE)](https://docs.snowflake.com/en/user-guide/snowflake-cortex/llm-functions)
- [PARSE_DOCUMENT (OCR / Document AI)](https://docs.snowflake.com/en/user-guide/snowflake-cortex/parse-document)
- [AI_COMPLETE (マルチモーダル/Vision)](https://docs.snowflake.com/en/sql-reference/functions/complete-snowflake-cortex-multimodal)
- [Cortex Search (RAG)](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)
- [Directory Tables](https://docs.snowflake.com/en/user-guide/data-load-dirtables)
- [OCR + RAG Quickstart](https://quickstarts.snowflake.com/guide/getting_started_with_ocr_and_rag_with_snowflake_notebooks/)
- [Image Analysis with Streamlit](https://www.snowflake.com/en/developers/guides/build-image-analysis-app-with-streamlit-and-snowflake-cortex/)

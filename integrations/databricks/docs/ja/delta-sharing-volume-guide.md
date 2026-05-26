# Delta Sharing & Volume Sharing 統合ガイド

> **ステータス**: アーキテクチャリファレンス — Pattern A/B は PoC 実施可能、Pattern C は Databricks UC 機能開発待ち（ブロック中）
>
> **コンテキスト**: このガイドは、FSx for ONTAP S3 Access Points との直接的な UC External Location 統合が[現在サポートされていない](../../README.md#support-confirmation-2026-05-26)状況において、Delta Sharing を使って FSx for ONTAP データを Databricks Unity Catalog ガバナンス下で利用する方法を文書化しています。

## エグゼクティブサマリー

Delta Sharing は**共有プロトコル**であり、変換エンジンではありません。任意の NAS ファイル（画像、動画、PDF）をその場でクエリ可能なテーブルに変換するものではありません。Delta Sharing が公開するのは、**準備済みの表形式データセット**です。

FSx for ONTAP と Databricks の統合において、Delta Sharing は以下の場合に実用的な共有レイヤーを提供します：
- Databricks がストレージの直接所有者ではなく**受信者（Recipient）**として機能する場合
- データが先に Delta または Parquet テーブルに変換されている場合
- Unity Catalog Volumes がガバナンス付き非表形式ファイルアクセスに使用される場合

### 基本原則

1. **Delta Sharing = 共有プロトコル**（変換エンジンではない）
2. **FSx for ONTAP S3 Access Points はオブジェクトアクセスを提供** — Delta Sharing にはテーブルセマンティクスが必要
3. **非構造化データの場合**: 共有可能な資産は派生した構造化表現（メタデータ、抽出テキスト、キャプション、embedding）
4. **真のゼロコピー Raw ファイルアクセスには**: Unity Catalog が FSx for ONTAP S3 AP をファーストクラスのストレージロケーションとしてサポートする必要あり（機能ギャップ — [Databricks エンジニアリングに報告済み](../../README.md#support-confirmation-2026-05-26)）

---

## 3つの統合パターン

### Pattern A: メタデータテーブル共有（推奨初回 PoC）

Raw ファイルそのものではなく、**ファイルカタログ**を Delta Sharing で共有する。

```
FSx for ONTAP
  ↓ S3 Access Point (ListObjectsV2)
AWS Lambda / Glue / Step Functions
  ↓ ファイルインベントリ抽出
Parquet or Delta メタデータテーブル (S3上)
  ↓
Delta Sharing (UC Share or OSS Server)
  ↓
Databricks 受信者
```

**共有テーブルスキーマ例:**

| カラム | 型 | 説明 |
|--------|------|-------------|
| `file_id` | STRING | 一意識別子 |
| `path` | STRING | S3 AP パス |
| `s3_ap_key` | STRING | アクセスポイント内のオブジェクトキー |
| `size_bytes` | BIGINT | ファイルサイズ |
| `last_modified` | TIMESTAMP | 最終更新日時 |
| `etag` | STRING | S3 ETag |
| `file_extension` | STRING | 例: `.pdf`, `.jpg`, `.parquet` |
| `mime_type` | STRING | MIME タイプ |
| `classification` | STRING | データ分類ラベル |
| `scan_timestamp` | TIMESTAMP | インベントリ取得日時 |

**使用 AWS サービス:**
- FSx for ONTAP S3 Access Points — S3 API によるファイルアクセス
- AWS Lambda — 小規模 PoC（ListObjectsV2 → メタデータ抽出）
- AWS Step Functions — バッチ処理のワークフロー制御
- AWS Glue — Parquet/Delta への ETL、カタログ管理
- Amazon S3 — メタデータテーブル保存先（Delta Sharing との互換性のため推奨）

**PoC 成功基準:** Databricks が FSx for ONTAP ファイルメタデータを表す Delta Sharing テーブルをクエリできること。

---

### Pattern B: AI 処理済みテーブル共有（RAG / 検索 / 分析）

非構造化データを AI サービスで処理し、**派生した構造化出力**を Delta Sharing で共有する。

```
FSx for ONTAP (Raw ファイル: PDF, 画像, 音声, 動画)
  ↓ S3 Access Point (GetObject)
AWS AI サービス (Textract, Rekognition, Transcribe, Bedrock)
  ↓ 抽出テキスト / キャプション / 文字起こし / embedding
Parquet or Delta テーブル (S3上)
  ↓
Delta Sharing
  ↓
Databricks 受信者 (Mosaic AI, Vector Search, MLflow)
```

**データタイプ別共有テーブルスキーマ:**

#### ドキュメント (PDF/DOCX) — RAG パイプライン

| カラム | 型 | 説明 |
|--------|------|-------------|
| `document_id` | STRING | ドキュメント ID |
| `source_path` | STRING | FSx for ONTAP S3 AP パス |
| `page_number` | INT | ページ番号 |
| `chunk_id` | STRING | テキストチャンク ID |
| `text` | STRING | 抽出テキスト |
| `summary` | STRING | AI 生成要約 |
| `embedding` | ARRAY<FLOAT> | ベクトル embedding |
| `classification` | STRING | ドキュメント分類 |
| `created_at` | TIMESTAMP | 処理日時 |

#### 画像 — ビジュアル検索

| カラム | 型 | 説明 |
|--------|------|-------------|
| `image_id` | STRING | 画像 ID |
| `source_path` | STRING | FSx for ONTAP S3 AP パス |
| `mime_type` | STRING | image/jpeg, image/png 等 |
| `width` | INT | 画像幅 (px) |
| `height` | INT | 画像高さ (px) |
| `detected_labels` | ARRAY<STRING> | 物体検出結果 |
| `caption` | STRING | AI 生成キャプション |
| `embedding` | ARRAY<FLOAT> | ビジュアル embedding |
| `created_at` | TIMESTAMP | 処理日時 |

#### 動画/音声 — 文字起こし & 分析

| カラム | 型 | 説明 |
|--------|------|-------------|
| `video_id` | STRING | 動画/音声 ID |
| `source_path` | STRING | FSx for ONTAP S3 AP パス |
| `start_time_sec` | FLOAT | セグメント開始時間 |
| `end_time_sec` | FLOAT | セグメント終了時間 |
| `transcript` | STRING | 文字起こしテキスト |
| `detected_objects` | ARRAY<STRING> | フレーム内検出オブジェクト |
| `scene_summary` | STRING | AI シーン説明 |
| `embedding` | ARRAY<FLOAT> | セグメント embedding |
| `created_at` | TIMESTAMP | 処理日時 |

**データタイプ別 AWS AI サービス:**

| データタイプ | 主要サービス | 補助 | 出力 |
|-----------|----------------|-----------|--------|
| PDF/ドキュメント | Amazon Textract | Amazon Bedrock (要約, embed) | テキスト, 表, フォーム, 要約 |
| 画像 | Amazon Rekognition | Bedrock マルチモーダル (キャプション) | ラベル, オブジェクト, 顔, キャプション |
| 音声 | Amazon Transcribe | Bedrock (要約) | 文字起こし, 話者 ID |
| 動画 | Rekognition Video | Transcribe + Bedrock | ラベル, シーン, 文字起こし |

**PoC 成功基準:** Databricks が AI 処理済みメタデータ（抽出テキスト、ラベル、要約、embedding）を Delta Sharing 経由でクエリできること。

---

### Pattern C: UC Volume による Raw ファイル共有（Databricks 機能拡張が必要）

理想的なゼロコピーアーキテクチャ — ただし現在は UC セッションポリシーの制限によりブロック。

**理想的なアーキテクチャ:**
```
FSx for ONTAP
  ↓ S3 Access Point
Databricks UC External Location (直接)
  ↓
UC External Volume
  ↓
Delta Sharing (Volume Sharing)
  ↓
Databricks 受信者 (read_files, ai_query, ai_parse_document)
```

**現在の現実（S3 コピーが必要）:**
```
FSx for ONTAP
  ↓ DataSync / SnapMirror
Amazon S3 バケット (標準)
  ↓
Databricks UC External Location
  ↓
UC External Volume
  ↓
Delta Sharing (Volume Sharing)
  ↓
Databricks 受信者
```

**現在動作するもの（S3 コピーあり）:**

```sql
-- Provider 側: S3 上に External Volume 作成（FSx for ONTAP から同期済み）
CREATE EXTERNAL VOLUME media_files
  LOCATION 's3://fsxn-synced-bucket/unstructured-data/'
  COMMENT 'FSx for ONTAP から同期された画像、動画、PDF';

-- Volume を Share に追加
CREATE SHARE IF NOT EXISTS unstructured_data_share
  COMMENT 'パートナー向けドキュメント・メディアファイル';

ALTER SHARE unstructured_data_share
  ADD VOLUME catalog.schema.media_files;

-- Recipient に付与
GRANT SELECT ON SHARE unstructured_data_share
  TO RECIPIENT <partner_org>;
```

```sql
-- Recipient 側: 共有ファイルにアクセス
CREATE CATALOG IF NOT EXISTS shared_media
  FROM SHARE <provider_name>.unstructured_data_share;

-- ファイルメタデータクエリ
SELECT * EXCEPT (content), _metadata
FROM read_files(
  '/Volumes/shared_media/schema/media_files/',
  format => 'binaryFile'
) LIMIT 10;

-- 共有画像の AI 分析
SELECT path,
  ai_query('databricks-llama-4-maverick',
    'Describe this image:', files => content)
FROM read_files(
  '/Volumes/shared_media/schema/media_files/',
  format => 'binaryFile',
  fileNamePattern => '*.{jpg,png}')
WHERE _metadata.file_size < 5000000;

-- 共有 PDF のパース
SELECT path,
  ai_parse_document(content, map('version', '2.0'))
FROM read_files(
  '/Volumes/shared_media/schema/media_files/',
  format => 'binaryFile',
  fileNamePattern => '*.pdf');
```

**Databricks への機能リクエスト（2026年5月報告済み）:**

1. UC External Location で S3 Access Point ARN をファーストクラスのストレージロケーションとしてサポート
2. FSx for ONTAP S3 AP ARN パターンに対応した UC セッションポリシー生成の更新
3. UC Volume が FSx for ONTAP S3 AP をバックエンドストレージとして使用可能にする
4. UC ストレージ抽象化を標準 S3 バケット以外（S3 Access Points、FSx for ONTAP アタッチドアクセスポイント）に一般化
5. Databricks-to-Databricks Volume Sharing が非バケット S3 AP バックエンドで動作するか明確化

**PoC 成功基準:** Databricks が必要な UC 機能拡張を確認するか、ゼロコピー FSx for ONTAP アクセスの代替サポート設計を提供すること。

---

## パターン比較

| 観点 | Pattern A | Pattern B | Pattern C |
|-----------|-----------|-----------|-----------|
| **共有資産** | ファイルメタデータテーブル | AI 処理済みテーブル | Raw ファイル (UC Volume 経由) |
| **FSx for ONTAP 上のデータ** | 残存（直接共有しない） | 残存（派生物を共有） | 残存（直接アクセス） |
| **S3 コピー必要量** | メタデータのみ (~KB) | 派生テーブル (~MB-GB) | 全ファイル同期 (~GB-TB) |
| **PoC 複雑度** | 低 | 中 | ブロック中（Databricks UC 機能開発が必要） |
| **ガバナンス** | Delta Sharing + UC | Delta Sharing + UC | UC Volume ACL |
| **AI/ML 対応度** | カタログのみ | 完全（embedding, RAG） | 完全（read_files + ai_query） |
| **リアルタイム鮮度** | ポーリングベース | パイプライン依存 | ほぼリアルタイム（サポート時） |
| **最適用途** | ファイル発見、監査 | RAG、検索、分析 | 直接ファイル処理 |

---

## Provider vs Recipient: 役割の明確化

| 役割 | Databricks が Provider | Databricks が Recipient |
|------|---|---|
| **データ所在** | UC 内にデータが必要（S3 バケット） | どこでも可（FSx for ONTAP → 処理 → 共有） |
| **ガバナンス** | UC がアクセスを統制 | Provider が統制; UC はローカルポリシー適用 |
| **アーキテクチャ** | FSx for ONTAP → S3 → UC → Share | FSx for ONTAP → Lambda/Glue → Delta table → OSS Delta Sharing Server → Databricks |
| **複雑度** | シンプル（UC が全て処理） | 柔軟（顧客管理の共有サーバー） |
| **推奨対象** | Databricks 中心の組織 | マルチプラットフォーム環境 |

**重要な洞察**: Databricks が**受信者**の場合、顧客管理の [OSS Delta Sharing サーバー](https://github.com/delta-io/delta-sharing)が FSx for ONTAP ベースのデータセットを UC にデータを置くことなく公開できます。

---

## ガバナンスレイヤー

| レイヤー | スコープ | 適用ポイント |
|-------|-------|-------------------|
| FSx ファイル権限 | NFS/SMB ACL, UNIX ユーザー | FSx for ONTAP |
| S3 AP ポリシー | IAM ベース、アクセスポイント単位 | AWS IAM |
| FPolicy | ファイル操作の監査/ブロック | ONTAP |
| Delta Sharing | Share レベル、Recipient レベル | 共有サーバーまたは UC |
| Unity Catalog | テーブル/Volume/カラム/行レベル | Databricks |

本番デプロイでは、組織要件に基づいて**主要ガバナンスポイント**を定義してください。

---

## データ鮮度の考慮事項

| 鮮度要件 | 推奨パターン | メカニズム |
|---|---|---|
| 日次 | Pattern A or B | スケジュール Glue/Lambda ジョブ |
| 時間単位 | Pattern A or B | Step Functions + CloudWatch Events |
| 準リアルタイム（分） | Pattern A + FPolicy | FPolicy → Lambda → 差分更新 |
| リアルタイム（秒） | Pattern C（将来） | 直接 FSx for ONTAP S3 AP アクセス（UC サポート必要） |

---

## 推奨 PoC ロードマップ

```
Phase 1: Pattern A — ファイルメタデータ共有
├── Lambda 関数: FSx for ONTAP S3 AP で ListObjectsV2 → Parquet テーブル
├── Delta Sharing: メタデータテーブルを Databricks に公開
├── Databricks: ファイルカタログをクエリ、タイプ/日付/サイズでフィルタ
└── 成功: Databricks がガバナンス付き FSx for ONTAP ファイルインベントリを参照可能

Phase 2: Pattern B — AI 処理済み共有
├── Textract: FSx for ONTAP 上の PDF からテキスト抽出
├── Bedrock: embedding と要約を生成
├── Delta テーブル: チャンク + embedding を保存
├── Delta Sharing: Databricks に公開
└── 成功: Databricks Vector Search で FSx for ONTAP 由来コンテンツを検索可能

Phase 3: Pattern C — ブロック中（Databricks UC 機能開発が必要）
├── 機能ギャップを Databricks UC エンジニアリングに報告済み（2026年5月）
├── UC エンジニアリングの回答とタイムラインを追跡
├── サポートされた場合: 直接 FSx for ONTAP S3 AP → UC Volume → Volume Sharing
└── それまで: Pattern A/B + Raw ファイルは S3 同期を継続（唯一の本番対応パス）
```

---

## FAQ: なぜ「EC2 で Delta Table を作るだけ」では ETL 不要にならないのか？

よくある誤解として、Delta Sharing は純粋にメタデータの問題であり、FSx for ONTAP 上のファイルに Delta Table を向けるだけで ETL やデータ移動なしに共有できる、というものがあります。このセクションでは、なぜそれが成立しないかを Databricks ドキュメントの参照付きで説明します。

### 誤解: 「Delta Sharing はメタデータだけの問題なので、EC2 で Delta Table を作って共有すればよい」

**前提の想定**: FSx for ONTAP にファイルがある → EC2 インスタンスがそのファイルを指す Delta Table を作成 → Delta Sharing でテーブルを公開 → Databricks が読む。ETL なし、コピーなし。

**FSx for ONTAP S3 Access Points でこれが動作しない理由:**

#### 1. Delta Table ≠ 任意のファイルへのポインタ

Delta Table は既存ファイルを指すだけのメタデータではありません。以下で構成される**特定のストレージフォーマット**です：
- Parquet データファイル（実データ）
- `_delta_log/` ディレクトリ内の JSON コミットファイル（トランザクションログ）

トランザクションログはテーブルへの全変更を記録し、ACID 保証を提供するものです。Delta Table の作成には、Parquet ファイルとコミットログの**両方をストレージロケーションに書き込む**必要があります。

参照: [What are ACID guarantees on Databricks?](https://docs.databricks.com/aws/lakehouse/acid) — "Databricks uses Delta Lake by default for all reads and writes and builds upon the ACID guarantees provided by the open source Delta Lake protocol."

#### 2. Delta Lake コミットプロトコルには条件付き書き込みが必要

Delta Lake の S3 上でのコミットプロトコルには以下のいずれかが必要です：
- **put-if-absent**（条件付き書き込み）セマンティクス、または
- **DynamoDB ベースのコミットコーディネーター**（マルチクラスター書き込み用）

FSx for ONTAP S3 Access Points は**条件付き書き込みをサポートしていません**（`If-None-Match` ヘッダーは "not supported" を返す）。これは：
- FSx for ONTAP S3 AP に Delta コミットログを安全に書き込めない
- 並行ライターがトランザクションログを破損する
- 単一ライターでもアトミックなコミットを保証できない

ことを意味します。

参照: [Multi-cluster writes to Delta Lake on S3](https://delta.io/blog/2022-05-18-multi-cluster-writes-to-delta-lake-storage-in-s3/) — "S3 currently lacks 'put-If-Absent' consistency guarantees. Thus, to guarantee ACID transactions on S3, one would need to have concurrent writes originating from the same Apache Spark driver."

参照: [Delta Lake storage configuration](http://docs.delta.io/latest/delta-storage.html) — "Delta Lake uses the scheme of the path to dynamically identify the storage system and use the corresponding LogStore implementation that provides the transactional guarantees."

#### 3. S3 上の Delta Lake には `_delta_log` 用の特定 IAM 権限が必要

標準 S3 上でも、Delta Lake は基本的な読み書き以上の特定権限を要求します：
- `s3:PutObject` — データファイルとコミットログファイル用
- `s3:GetObject` — 最新コミットバージョンの読み取り用
- `s3:ListBucket` — コミットログエントリの発見用
- `s3:DeleteObject` — VACUUM 操作用

FSx for ONTAP S3 AP では、UC セッションポリシーが `PutObject` とサブディレクトリの `ListBucket` をブロックするため、UC ガバナンス下での Delta Table 作成は不可能です。

参照: [Access denied when writing Delta Lake tables to S3](https://kb.databricks.com/en_US/delta/s3-permissions-delta) — "Delta Lake requires creation of a _delta_log directory. The write operation also needs to check the latest version of the commit logs."

#### 4. Delta Sharing にはテーブルの Unity Catalog 登録が必要

Delta Sharing（Databricks-to-Databricks プロトコル）は **Unity Catalog に登録されたテーブル**を共有します。UC に登録されたテーブルは以下のいずれかに存在する必要があります：
- **UC Managed Storage** ロケーション（Databricks 管理の S3 バケット）、または
- **UC External Location**（Storage Credential で登録された顧客 S3 バケット）

FSx for ONTAP S3 AP は UC External Location として登録できません（Databricks サポートにより 2026 年 5 月確認済み）。したがって、仮に FSx for ONTAP S3 AP 上に Delta Table を作成できたとしても、共有のために UC に登録することはできません。

参照: [Create and manage shares for Delta Sharing](https://docs.databricks.com/en/delta-sharing/create-share.html) — Share は "only one Unity Catalog metastore" のアセットのみ含むことができる。

参照: [What is the Delta Sharing Databricks-to-Databricks protocol?](https://docs.databricks.com/aws/en/delta-sharing/share-data-databricks) — UC 対応ワークスペースと UC 登録アセットが必要。

#### 5. OSS Delta Sharing Server でも有効な Delta Table が必要

[OSS Delta Sharing サーバー](https://github.com/delta-io/delta-sharing)を使用する場合（UC をバイパス）でも、サーバーは一貫した `_delta_log` を持つ有効な Delta Table を指す必要があります。同じストレージ要件が適用されます — Delta コミットプロトコルをサポートするストレージバックエンドが必要です。

### 「EC2 で Delta Table を作成する」とは実際に何を意味するか

EC2 上で Spark ジョブを実行し、FSx for ONTAP S3 AP からファイルを読み取って Delta Table を書き込む場合、それは ETL を実行しています：

```
FSx for ONTAP S3 AP (ソースファイル: CSV, Parquet, JSON, 画像)
  ↓ GetObject (読み取り)
EC2 / EMR / Glue (Spark ジョブ)
  ↓ spark.read → 変換 → spark.write.format("delta")
S3 バケット (Delta Table: Parquet ファイル + _delta_log/)
  ↓ UC に登録
Delta Sharing
```

これは「メタデータだけ」ではありません。以下を行っています：
1. FSx for ONTAP S3 AP からソースファイルを**読み取り** (GetObject)
2. Delta スキーマの Parquet フォーマットに**変換**
3. Parquet データファイル + コミットログを別のストレージロケーション（S3 バケット）に**書き込み**
4. テーブルを Unity Catalog に**登録**

これは定義上 ETL です。"E" (Extract) は FSx for ONTAP からの読み取り。"T" (Transform) は Delta フォーマットへの変換。"L" (Load) は S3 への書き込みです。

### まとめ: なぜ S3 バケットが必要か

| ステップ | FSx for ONTAP S3 AP 単独では不十分な理由 |
|---------|---|
| Delta コミットログの書き込み | FSx for ONTAP S3 AP で条件付き書き込みが非サポート |
| UC への登録 | UC External Location が S3 AP ARN を非サポート |
| マルチクラスター安全性 | FSx for ONTAP S3 AP 用の DynamoDB LogStore 相当がない |
| Delta Sharing | UC 登録テーブルまたはサポートされたストレージ上の有効な Delta Table が必要 |

### 唯一の真の「Zero Copy」パス

データコピーが発生しない唯一のシナリオは **Pattern C**（UC Volume Sharing）です — ただし Databricks が FSx for ONTAP S3 AP をファーストクラスの UC ストレージロケーションとしてサポートする必要があります。Volume Sharing はテーブルデータではなくファイル参照を共有するため、Delta コミットログは不要です。

**現在のステータス**: ブロック中 — Databricks UC 機能開発待ち（2026 年 5 月報告済み、タイムラインなし）。

---

## 参考資料

- [Work with unstructured data in volumes](https://docs.databricks.com/aws/en/volumes/unstructured-data-tutorial) — Volume Sharing を含む完全チュートリアル
- [What are Unity Catalog volumes?](https://docs.databricks.com/aws/en/volumes/managed-vs-external) — Managed vs External volumes
- [Volume Sharing with Delta Sharing (Video)](https://www.databricks.com/resources/demos/videos/data-sharing/volume-sharing-delta-sharing) — デモ動画
- [Create and manage shares](https://docs.databricks.com/en/delta-sharing/create-share.html) — Share に Volume を追加する手順
- [Delta Sharing OSS](https://github.com/delta-io/delta-sharing) — オープンソース Delta Sharing サーバー
- [FSx for ONTAP S3 Access Points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/s3-access-points.html) — AWS ドキュメント

---

## 関連ドキュメント

- [Databricks README](../../README.md) — 統合ステータスとアーキテクチャ全体
- [Analytics & AI デモガイド](ai-demo-guide.md) — AI/ML 機能と現在のステータス
- [サポートケースサマリー](../../.private/support-case-00921422-summary-ja.md) — UC + S3 AP 制限の詳細（プライベート）

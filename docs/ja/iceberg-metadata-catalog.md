# 非構造化データ向け Iceberg メタデータカタログ: FSx for ONTAP とモダンデータ基盤の架け橋

🌐 日本語 | [English](../en/iceberg-metadata-catalog.md)

## エグゼクティブサマリー

本ドキュメントは、FSx for ONTAP に格納された非構造化データに対して **Apache Iceberg をメタデータカタログとして活用する**アーキテクチャパターンを定義する。生ファイルをデータ基盤に移動するのではなく、実データは ONTAP 上に残し（重複排除・マルチプロトコルアクセス・Snapshot の恩恵を維持）、メタデータ（ファイルパス、タグ、AI 分類結果、ベクトル embedding）をマネージド Iceberg テーブルで管理し、あらゆる分析エンジンからアクセス可能にする。

**主要テクノロジー**:
- **Amazon S3 Tables** — フルマネージド Apache Iceberg テーブル。自動コンパクション、3x クエリ性能、Iceberg REST endpoint 提供
- **FSx for ONTAP S3 Access Points** — ONTAP ボリュームへの S3 互換アクセス（AI/分析の読み取りパス）
- **S3 Metadata** — S3 オブジェクトメタデータの自動 Iceberg テーブル化（DataSync 経由の代替パス）
- **Iceberg REST Catalog** — Databricks、Snowflake、Spark 等からのクロスプラットフォームアクセス

## コアコンセプト: ホットメタデータ × コールド実データ分離

```
┌─────────────────────────────────────────────────────────────────────┐
│  HOT: メタデータ層 (Apache Iceberg on S3 Tables)                     │
│  - ファイルパス、タグ、分類、embedding                               │
│  - 高速 SQL クエリ (Athena, Redshift, EMR)                           │
│  - ベクトル類似検索 (OpenSearch)                                      │
│  - Iceberg REST endpoint 経由のクロスプラットフォームアクセス         │
│  - Lake Formation / Horizon Catalog によるガバナンス                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ file_path 参照
┌──────────────────────────────▼──────────────────────────────────────┐
│  COLD: データ層 (FSx for ONTAP)                                      │
│  - 実ファイル: PDF、画像、CAD、動画、音声、ログ                      │
│  - 重複排除 (50-70% ストレージ削減)                                  │
│  - マルチプロトコル: NFS/SMB (既存ワークフロー) + S3 AP (AI/分析)    │
│  - Snapshot: バッチ AI 処理の一貫性あるポイントインタイム             │
│  - FabricPool: 低コストストレージへの自動階層化                       │
└─────────────────────────────────────────────────────────────────────┘
```

**なぜこの分離が有効か？**

| 観点 | メタデータ層 (S3 Tables) | データ層 (FSx for ONTAP) |
|------|--------------------------|--------------------------|
| クエリ速度 | サブ秒 (Iceberg 最適化) | N/A (クエリ不可) |
| ストレージ効率 | 最小 (~1GB / 10万ファイル) | 重複排除 + 圧縮 (50-70% 削減) |
| マルチエンジンアクセス | ✅ Iceberg REST endpoint | ✅ S3 AP + NFS/SMB |
| ガバナンス | Lake Formation / Horizon | S3 AP ポリシー + ONTAP ACL |
| AI 処理 | embedding をここに格納 | 生ファイルをここから読み取り |
| コスト | ~$5-15/月 (メタデータのみ) | データ量に依存 |

---

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ガバナンス層                                       │
│                                                                      │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────────┐  │
│  │Lake Formation│  │Snowflake Horizon │  │Databricks Unity      │  │
│  │LF-Tags       │  │Row Access Policy │  │Catalog (External)    │  │
│  │列/行制御     │  │動的マスキング    │  │                      │  │
│  └──────────────┘  └──────────────────┘  └──────────────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              メタデータ層 (Apache Iceberg)                            │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ S3 Tables (table bucket) — プライマリメタデータストア          │   │
│  │                                                               │   │
│  │ スキーマ:                                                     │   │
│  │   file_id, file_path, file_name, file_type, file_size         │   │
│  │   created_at, modified_at, source_volume, access_point_arn    │   │
│  │   tags (map), classification, confidence_score                │   │
│  │   embedding_vector (binary), summary                          │   │
│  │   sensitivity_level, has_pii, anonymized_path                 │   │
│  │                                                               │   │
│  │ アクセス: Iceberg REST endpoint → Databricks, Snowflake, Spark│   │
│  │ ガバナンス: SageMaker Lakehouse + Lake Formation              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              イベント & 処理層                                        │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ リアルタイムパス: FPolicy → Fargate → SQS → Lambda           │    │
│  │   (ファイル作成/変更/削除 → 5分以内にメタデータ同期)          │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ AI エンリッチメント: Step Functions → Bedrock/Cortex/Mosaic   │    │
│  │   (分類、embedding、要約、PII 検出)                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ バッチパス (代替): DataSync → S3 → S3 Metadata               │    │
│  │   (S3 オブジェクトメタデータから自動 Iceberg テーブル生成)    │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│              ストレージ層                                             │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ FSx for ONTAP                                                │    │
│  │   • S3 Access Point → AI/分析の読み取りアクセス              │    │
│  │   • NFS/SMB → 既存ワークフロー (CAD ツール、エディタ)       │    │
│  │   • 重複排除 + 圧縮 (50-70% 削減)                           │    │
│  │   • Snapshot → バッチ処理の一貫性あるポイントインタイム      │    │
│  │   • FPolicy → リアルタイムファイルイベント検知               │    │
│  │   • FabricPool → コールドデータの自動階層化                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ オンプレミス ONTAP (オプション)                               │    │
│  │   • SnapMirror → FSx for ONTAP (ブロックレベルレプリケーション)│   │
│  │   • FlexCache S3 AP (将来: ONTAP 9.18.1 オンプレ対応済み)   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## プラットフォーム別実装パス

### AWS ネイティブパス (Athena + Lake Formation + Bedrock)

**最適な対象**: AWS ネイティブ分析スタックに既に投資している組織。

```
FSx for ONTAP ──S3 AP──→ Bedrock KB (RAG, Vision)
                    │
                    └──→ Lambda (メタデータ抽出)
                              ↓
                    S3 Tables (Iceberg メタデータ)
                              ↓
                    Glue Catalog (SageMaker Lakehouse)
                              ↓
                    Lake Formation (LF-Tags ガバナンス)
                              ↓
                    Athena / EMR / Redshift Spectrum (クエリ)
```

**主な利点**:
- FSx S3 AP から Athena と Bedrock への直接アクセス（読み取りに S3 コピー不要）
- Lake Formation が全 AWS 分析エンジンにガバナンスを適用
- S3 Tables の自動コンパクションでテーブルメンテナンス不要
- Bedrock Knowledge Base がメタデータをインデックスし自然言語検索を実現

**ガバナンスモデル**: Lake Formation LF-Tags をメタデータテーブルの列/行に適用。タグ例: `department=engineering`, `sensitivity=confidential`, `classification=medical_image`

> **リージョン対応に関する注記**: デプロイ前にターゲットリージョンでの S3 Tables の利用可否を確認すること。ap-northeast-1 で S3 Tables が未対応の場合は、Glue Catalog + セルフマネージド Iceberg テーブルをフォールバックとして使用（同一スキーマ、手動コンパクション必要）。S3 Tables が利用可能になった時点での移行は容易。

### Databricks パス (Unity Catalog + Mosaic AI)

**最適な対象**: Databricks への既存投資がある組織（UC、Delta Lake、MLflow）。

```
S3 Tables ──Iceberg REST endpoint──→ Databricks External Catalog
                                              ↓
                                    Unity Catalog ガバナンス
                                              ↓
                                    Spark SQL / Mosaic AI クエリ
                                              ↓
                                    Vector Search (類似ファイル発見)
```

**主な利点**:
- Iceberg REST endpoint により S3 Tables メタデータに Databricks から直接アクセス
- Mosaic AI による画像/ドキュメントの自動分類パイプライン
- Vector Search による embedding ベースの類似ファイル発見
- Delta Sharing による組織横断メタデータ共有

**現在の制約**: Unity Catalog session policy が S3 AP ARN フォーマットを認識しない（直接ファイルアクセス不可）。回避策: メタデータクエリは Iceberg REST 経由 + ファイルアクセスは Bedrock/Lambda 経由。

**Vector Search 統合**: Databricks ファーストの組織では、S3 Tables から Mosaic AI Vector Search Index に embedding を同期することで、Databricks ネイティブの類似検索が可能。OpenSearch Serverless と比較して、Databricks ノートブックや Model Serving とのより緊密な統合を提供。

**ガバナンスモデル**: Unity Catalog External Catalog + Lake Formation 補完（クロスエンジン適用）。

### Snowflake パス (Horizon Catalog + Cortex AI)

**最適な対象**: Snowflake への既存投資がある組織（Cortex AI、Data Sharing、Horizon）。

```
FSx for ONTAP ──S3 AP Stage──→ COPY INTO → Managed Iceberg Table
                                                    ↓
                                          Cortex AI (PARSE_DOCUMENT, Vision)
                                                    ↓
                                          Horizon Iceberg REST Catalog
                                                    ↓
                                          外部エンジン (Spark, Databricks)
                                          Row Access Policy 適用済み
```

**主な利点**:
- Cortex AI が非構造化データを直接処理（PARSE_DOCUMENT、COMPLETE、Vision）
- Horizon Catalog が外部エンジンアクセスにもガバナンスを適用（Row Access Policy、Masking）
- STORAGE_REQUEST_HISTORY で外部エンジンアクセスを監査
- Secure Data Sharing によるゼロコピー組織横断メタデータ共有

**現在の制約**: TO_FILE が S3 AP ステージで失敗（エンジニアリング調査中）。回避策: COPY FILES で内部ステージに転送後 Vision AI 処理。

**ガバナンスモデル**: Horizon Catalog Row Access Policy + Dynamic Masking。Snowflake 内部と外部エンジンの両方に適用。

---

## 意思決定マトリクス: メタデータ層の選択

| 基準 | S3 Tables | Snowflake Managed Iceberg | Glue Catalog (セルフマネージド Iceberg) |
|------|-----------|--------------------------|----------------------------------------|
| **運用負荷** | なし (フルマネージド) | なし (フルマネージド) | 中 (手動コンパクション、スナップショット期限) |
| **クエリ性能** | セルフマネージド比 3x | 同等 | ベースライン |
| **クロスプラットフォーム** | ✅ Iceberg REST endpoint | ✅ Horizon REST Catalog | ✅ Glue Catalog + Iceberg |
| **ガバナンス** | Lake Formation + SageMaker Lakehouse | Horizon (Row Access Policy, Masking) | Lake Formation |
| **外部エンジン適用** | ✅ (Lake Formation 経由) | ✅ (Horizon 経由) | ✅ (Lake Formation 経由) |
| **自動コンパクション** | ✅ 組み込み | ✅ 組み込み | ❌ 手動 or Glue ジョブ |
| **コスト (10万レコード)** | ~$5-15/月 | Snowflake コンピュートに含む | ~$5/月 + メンテナンスコンピュート |
| **リージョン対応** | 拡大中 (要確認) | 全 Snowflake リージョン | 全 AWS リージョン |
| **最適な用途** | AWS ネイティブ + マルチエンジン | Snowflake ファースト + 外部共有 | 最大の柔軟性 |

**推奨**: AWS ネイティブパスでは S3 Tables から開始。外部エンジンへの Horizon ガバナンスが必要な場合は Snowflake Managed Iceberg を追加。S3 Tables が未対応のリージョンでは Glue Catalog をフォールバックとして使用。

---

## イベント検知: FPolicy パイプライン vs DataSync + S3 Metadata

| 観点 | FPolicy パイプライン | DataSync + S3 Metadata |
|------|---------------------|----------------------|
| **レイテンシ** | ~5 秒 (リアルタイム) | 分〜時間 (バッチ) |
| **データコピー** | 不要 (メタデータのみ) | 必要 (全ファイルを S3 にコピー) |
| **ストレージコスト** | 最小 (S3 Tables のメタデータのみ) | 大 (S3 に全ファイルのコピー) |
| **構築複雑度** | 中 (FPolicy Server + Lambda) | 低 (DataSync タスク + S3 Metadata 有効化) |
| **メタデータの豊富さ** | カスタム (任意のフィールド抽出可) | 標準 S3 オブジェクトメタデータ + カスタムタグ |
| **AI エンリッチメント** | 別パイプライン (Step Functions) | 別パイプライン (同様) |
| **最適な用途** | リアルタイムカタログ、S3 コピー予算なし | バッチ処理、S3 コピーが他の理由で必要 |

**推奨**: FPolicy パイプラインをプライマリパスとして使用（S3 コピーコストを排除）。DataSync + S3 Metadata は S3 コピーが他の理由で既に必要な場合（例: Bedrock KB データソース、クロスリージョンアクセス）の補完パスとして使用。

---

## AI エンリッチメントパイプライン

### ファイルタイプ別処理モード

| ファイルタイプ | AI サービス | 出力 | レイテンシ | コスト (1ファイル) |
|--------------|-----------|------|---------|-----------------|
| PDF/ドキュメント | Bedrock Claude (要約、抽出) | 要約、エンティティ、分類 | 5-30秒 | $0.01-0.05 |
| 画像 | Bedrock Claude Vision (分類、説明) | 説明、分類、オブジェクト | 3-10秒 | $0.01-0.03 |
| 音声 | Transcribe → Bedrock (要約) | 文字起こし、要約、感情 | 30-120秒 | $0.02-0.10 |
| 動画 | フレーム抽出 → Vision (サンプリング) | シーン説明、分類 | 60-300秒 | $0.05-0.50 |
| CAD/3D | メタデータ抽出のみ | 寸法、レイヤー、コンポーネント | 1-5秒 | $0.001 |
| ログ/センサー | パターン検出 (Bedrock) | 異常、パターン、統計 | 5-15秒 | $0.01-0.03 |

### Embedding 生成

全ファイルタイプに対して 1536 次元ベクトル embedding（Amazon Titan Embeddings V2）を生成:
- ドキュメント: 本文テキストから
- 画像: AI 生成説明文から
- 音声: 文字起こしテキストから
- 動画: 連結シーン説明から

Embedding により**類似検索**が可能: 「このファイルに似たファイルを探す」— OpenSearch Serverless の kNN 検索、または Iceberg embedding カラムのブルートフォーススキャン。

### PII 検出と匿名化

```
ファイル → PII 検出 (Comprehend / Bedrock)
              │
              ├─ PII なし → has_pii=false, anonymization_status="not_required"
              │
              └─ PII 検出 → has_pii=true
                               ↓
                     匿名化パイプライン
                     (顔ぼかし、PII 墨消し、DICOM 匿名化)
                               ↓
                     anonymized_path = クリーンバージョンのパス
                     anonymization_status = "completed"
```

**データクリーンルームパターン**: オリジナルメタデータテーブル（制限アクセス）+ クリーンメタデータテーブル（広範囲アクセス、匿名化ファイルのみ）。Lake Formation で分離を適用。

---

## コスト見積もり

### シナリオ: 10TB 非構造化データ、10万ファイル、1000変更/日

| コンポーネント | 月額コスト | 備考 |
|-------------|-----------|------|
| **S3 Tables (メタデータストレージ)** | ~$5 | 10万レコードで ~1GB |
| **S3 Tables (リクエスト)** | ~$10 | Lambda からの書き込み + クエリからの読み取り |
| **Lambda (メタデータ同期)** | ~$5 | 1000イベント/日 × 200ms × 128MB |
| **Lambda (AI エンリッチメント)** | ~$50 | 100新規ファイル/日 × 30s × 512MB |
| **Bedrock (AI 処理)** | ~$100-500 | モデル選択とボリュームに依存 |
| **Step Functions** | ~$5 | ステート遷移 |
| **SQS** | ~$1 | メッセージ処理 |
| **OpenSearch Serverless (オプション)** | ~$350 | ベクトル検索用 2 OCU 最小 |
| **FSx for ONTAP (既存)** | — | プライマリストレージとして既にプロビジョニング済み |
| | | |
| **合計 (ベクトル検索なし)** | **~$175-575/月** | |
| **合計 (ベクトル検索あり)** | **~$525-925/月** | |

### 代替アプローチとのコスト比較

| アプローチ | 月額コスト (10TB) | メタデータレイテンシ | ガバナンス |
|----------|-----------------|-------------------|-----------|
| **本アーキテクチャ (FPolicy + S3 Tables)** | $175-575 | ~5 秒 | Lake Formation / Horizon |
| S3 フルコピー + Glue Crawler | $230 (S3) + $50 (Glue) | 時間 | Lake Formation |
| S3 フルコピー + S3 Metadata | $230 (S3) + $15 (Metadata) | 分 | Lake Formation |
| カスタム DynamoDB カタログ | $50-200 | 秒 | カスタム IAM |

---

## 成功 KPI

| KPI | Before (現状) | After (本アーキテクチャ) | 計測方法 |
|-----|-------------|------------------------|---------|
| **データ発見時間** | 数日 (手動検索、同僚に確認) | 数秒 (SQL メタデータ検索、自然言語) | 「Xが必要」から「Xを発見」までの時間 |
| **共有リードタイム** | 数週間 (コピー、承認、転送) | 即時 (Iceberg REST + ガバナンスポリシー) | 共有リクエストからアクセス付与までの時間 |
| **AI 処理スループット** | 手動 (人がファイル選択、ツール実行) | 自動 (FPolicy → Step Functions パイプライン) | 人手介入なしで処理されるファイル数/日 |
| **ストレージコスト** | ベースライン (S3 フルコピー + 重複排除なし) | 30-70% 削減 (ONTAP 重複排除 + S3 コピー排除) | 月次ストレージ支出 |
| **ガバナンスカバレッジ** | 0% (メタデータなし、非構造化データにアクセス制御なし) | 100% (全ファイルカタログ化、LF-Tags/Horizon 適用) | 分類 + アクセスポリシー適用済みファイルの割合 |
| **組織横断データ再利用** | ほぼゼロ (サイロ化されたコピー) | 計測可能 (Delta Sharing / Secure Data Sharing メトリクス) | 2組織以上からアクセスされるユニークデータセット数 |

---

## 業界別ユースケース例

| 業界 | ユースケース | 主要ファイル | AI 処理 | ビジネス価値 |
|------|-----------|-----------|---------|------------|
| **製造業** | 設計図面の類似検索 | CAD (DWG, STEP)、図面 (PDF) | Embedding → 類似検索 | 過去設計の再利用率↑、R&D 期間↓ |
| **金融** | 契約書の自動分類 + コンプライアンス検索 | 契約書 (PDF)、明細書 | エンティティ抽出、分類 | コンプライアンス検索時間: 数日→数秒 |
| **医療** | DICOM 画像の匿名化共有（研究用） | 医療画像 (DICOM)、レポート (PDF) | DICOM 匿名化、PII 墨消し | プライバシーリスクなしの研究データセット構築 |
| **メディア** | 動画アセットのタグ検索 + コンテンツ再利用 | 動画 (MP4)、画像 (RAW, JPEG) | シーン分類、物体検出 | コンテンツ再利用効率↑、ライセンスコンプライアンス |
| **公共セクター** | 監視映像のガバナンス + 異常検知 | 動画 (H.264)、センサーログ | 顔検出（ぼかし用）、異常検知 | 市民プライバシー保護 + セキュリティ |
| **エネルギー/ユーティリティ** | IoT センサーログのパターン検出 | センサーデータ (CSV, Parquet)、保守ログ | 異常検知、予知保全 | 計画外ダウンタイム↓、保守コスト↓ |

---

## データ主権、暗号化、監査保持期間

### データ主権

| コンポーネント | 所在地 | リージョン間転送 |
|-------------|--------|---------------|
| 生ファイル (FSx for ONTAP) | FSx ファイルシステムと同一リージョン | なし (S3 AP は同一リージョンのみ) |
| メタデータテーブル (S3 Tables) | 同一リージョン (設定可能) | なし (クエリ結果もリージョン内) |
| AI 処理 (Bedrock/Lambda) | 同一リージョン | なし (リージョン内処理) |
| ガバナンス (Lake Formation) | 同一リージョン | クロスアカウント可能 (同一リージョン) |

**保証**: メタデータと生データの両方が同一 AWS リージョンに留まる。デフォルトアーキテクチャでは越境データ転送は発生しない。規制産業のデータレジデンシー要件を満たす。

### 保存時暗号化

| 層 | 暗号化 | 鍵管理 |
|----|--------|--------|
| FSx for ONTAP | SSE-FSX (AES-256) | AWS KMS マネージド、透過的 |
| S3 Tables | SSE-S3 or SSE-KMS | 顧客選択 (コンプライアンスには KMS 推奨) |
| SQS メッセージ | SSE-SQS or SSE-KMS | AWS マネージド or 顧客 KMS |
| Lambda 環境 | デフォルト暗号化 | AWS マネージド |
| OpenSearch Serverless | デフォルト暗号化 | AWS マネージド or 顧客 KMS |

### 監査ログ保持期間

| 規制 | 必要保持期間 | 推奨設定 |
|------|-----------|---------|
| HIPAA (医療) | 6-7年 | CloudTrail: S3 アーカイブ (7年)、Lake Formation ログ: 7年 |
| SOX / 金融 | 5-7年 | CloudTrail: S3 アーカイブ (7年)、クエリログ: 5年 |
| GDPR (EU) | 処理期間 + 合理的期間 | CloudTrail: 最低3年、削除監査: 無期限 |
| 一般企業 | 1-3年 | CloudTrail: 90日ホット + S3 アーカイブ (3年) |

**実装**: CloudTrail ログを S3 に配信し、保持要件に合わせたライフサイクルポリシーを設定。Lake Formation アクセスログも同様のパターンに従う。

---

## ONTAP Snapshot と FlexClone の AI 処理活用

### パターン: Snapshot ベースのバッチ AI 処理

```
1. AI バッチ処理前に Snapshot を作成
   → 一貫性あるポイントインタイムビューを保証
   → 処理中にファイルが変更されない

2. AI パイプラインが Snapshot から読み取り (S3 AP 経由)
   → 本番 NFS/SMB ワークロードへの干渉なし
   → 決定論的結果 (同じ入力 = 同じ出力)

3. 処理完了後、Snapshot を削除可能
   → 追加ストレージコストゼロ (ONTAP Snapshot は容量効率的)
```

**ユースケース**: 毎晩の AI エンリッチメントバッチで全新規ファイルを処理。Snapshot により処理中のファイル変更を防止し、部分読み取りや不整合な分類を防ぐ。

### パターン: FlexClone による AI サンドボックス

```
1. 本番ボリュームを FlexClone
   → 即時 (メタデータのみの操作)
   → 追加ストレージゼロ (Copy-on-Write)

2. AI チームが FlexClone 上で実験
   → ファイルの変更、削除、再編成が自由
   → 本番ボリュームへの影響なし

3. 検証済み結果をメタデータテーブルに書き込み
   → 実験後に FlexClone を削除
```

**ユースケース**: データサイエンスチームが本番データで新しい分類モデルをテストしたい場合。FlexClone がストレージオーバーヘッドゼロで数秒でフルコピーを提供。

---

## 定期フルスキャン同期（リコンシリエーション）

### 必要性

FPolicy 非同期モードは極端な高負荷時（10,000+ イベント/秒の持続）にイベントをドロップする可能性がある。また、FPolicy 有効化前に作成されたファイルにはメタデータレコードがない。定期的なリコンシリエーションによりメタデータテーブルの完全性を保証する。

### 設計

```
EventBridge スケジュール (毎日 02:00 UTC)
  → Step Functions: FullScanReconciliation
    → Lambda: FSx S3 AP で ListObjectsV2 (ページネーション)
    → Lambda: Metadata_Table と比較 (anti-join)
    → Lambda: 欠落レコードを INSERT (enrichment_status = "pending")
    → CloudWatch メトリクス: reconciliation_gap_count
```

### 設定パラメータ

| パラメータ | デフォルト | 備考 |
|----------|---------|------|
| スケジュール | 毎日 02:00 UTC | 低トラフィック時間帯 |
| スコープ | FPolicy 有効な全ボリューム | ボリューム単位で設定可能 |
| バッチサイズ | Lambda 呼び出しあたり 1000 オブジェクト | ページネーション |
| アラート閾値 | gap_count > 100 | FPolicy イベントロスを示唆 |

---

## Snowflake Cortex Search によるメタデータ自然言語検索

### パターン: メタデータテーブルに対する Cortex Search

```
Managed Iceberg Table (メタデータ)
  → Cortex Search Service (インデックス対象: summary, tags, classification, file_name)
    → 自然言語クエリ: 「2025年のポンプ設計に関連するエンジニアリング図面を探して」
      → 結果: file_path + メタデータのランク付きリスト
```

### 設定例

```sql
-- メタデータテーブルに Cortex Search サービスを作成
CREATE OR REPLACE CORTEX SEARCH SERVICE metadata_search
  ON unstructured_file_metadata
  WAREHOUSE = 'COMPUTE_WH'
  TARGET_LAG = '1 hour'
  ATTRIBUTES = 'file_type, classification, sensitivity_level'
  COLUMNS = 'summary, file_name, tags'
  AS (
    SELECT
      file_id,
      file_path,
      file_name,
      file_type,
      classification,
      sensitivity_level,
      summary,
      OBJECT_CONSTRUCT_KEEP_NULL(*) AS tags_json
    FROM unstructured_file_metadata
    WHERE is_deleted = FALSE
      AND enrichment_status = 'completed'
  );
```

### SQL 検索との比較

| 観点 | SQL (Athena/Redshift) | Cortex Search |
|------|---------------------|---------------|
| クエリタイプ | 完全一致、LIKE、正規表現 | 自然言語、セマンティック |
| セットアップ | なし (標準 SQL) | Cortex Search サービス作成 |
| 関連性ランキング | 手動 (ORDER BY) | 自動 (ML ベース) |
| あいまい検索 | 限定的 | 組み込み |
| 最適な用途 | 構造化フィルタ (日付、タイプ、タグ) | 発見 (「Xに関するドキュメントを探す」) |

**推奨**: 構造化クエリ（既知のフィルタ）には SQL、発見（未知またはあいまいな要件）には Cortex Search を使用。両方とも同じ Iceberg メタデータテーブルにアクセス。

---

## 匿名化品質保証プロセス

### 課題

AI ベースの PII 検出は 100% 正確ではない。偽陰性（PII 見逃し）はコンプライアンスリスクを生む。偽陽性（過剰墨消し）はデータの有用性を低下させる。

### 推奨プロセス

```
┌─────────────────────────────────────────────────────────┐
│ Stage 1: 自動 PII 検出                                   │
│   Comprehend + Bedrock → has_pii フラグ                  │
│   期待精度: 95-98%                                       │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│ Stage 2: 自動匿名化                                      │
│   顔ぼかし、PII 墨消し、DICOM 匿名化                    │
│   出力: 匿名化ファイル + anonymized_path                 │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│ Stage 3: 人間によるサンプリングレビュー (週次)            │
│   - 匿名化ファイルのランダム 5% サンプル                 │
│   - レビュー項目: PII 完全除去？ 過剰墨消し？            │
│   - フィードバックループ → モデルファインチューニング     │
│   - エスカレーション: ミス率 > 2% でパイプライン一時停止  │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│ Stage 4: 監査証跡                                        │
│   - 誰がレビューしたか、いつ、どの判断                   │
│   - 各ファイルを処理したパイプラインバージョン            │
│   - 保持期間: 規制要件に準拠                             │
└─────────────────────────────────────────────────────────┘
```

### DICOM 匿名化方式

| 方式 | HIPAA 準拠 | データ有用性 | 複雑度 |
|------|-----------|------------|--------|
| **Safe Harbor** | ✅ (18 識別子を除去) | 低い (積極的除去) | 低 |
| **Expert Determination** | ✅ (統計的検証) | 高い (選択的除去) | 高 |
| **ハイブリッド** (推奨) | ✅ | 中-高 | 中 |

**推奨**: 初期デプロイでは Safe Harbor から開始（シンプル、コンプライアンス保証）。データ有用性が重要な研究データセットでは Expert Determination に移行。

---

## 制約と制限事項

| 制約 | 影響 | 緩和策 |
|------|------|--------|
| FSx S3 AP: conditional writes 未サポート | FSx S3 AP に直接 Iceberg テーブルを書き込めない | メタデータは S3 Tables に格納（FSx ではなく）; 生ファイルは FSx に格納 |
| FSx S3 AP: S3 Event Notifications 未サポート | ネイティブ S3 イベントで変更検知不可 | FPolicy が同等のリアルタイム検知を提供 |
| FSx S3 AP: ListObjectsV2 レイテンシ | ディレクトリ一覧が遅い (ネイティブ S3 比 30-80x) | メタデータテーブルにより LIST 操作が不要に |
| Databricks: Session policy が S3 AP をブロック | UC から FSx ファイルに直接アクセス不可 | メタデータは Iceberg REST 経由; ファイルは Bedrock/Lambda 経由 |
| Snowflake: TO_FILE が S3 AP で失敗 | Vision AI に内部ステージ回避策が必要 | COPY FILES で内部ステージに転送; PARSE_DOCUMENT は直接動作 |
| S3 Tables: リージョン対応 | 全リージョンで利用可能ではない | Glue Catalog + セルフマネージド Iceberg にフォールバック |

詳細なプラットフォーム × フォーマット × モードの検証状況は [互換性マトリクス](compatibility-matrix.md) を参照。

---

## 関連ドキュメント

| ドキュメント | 関係 |
|------------|------|
| [ゼロコピー非構造化データガバナンス](zero-copy-media-governance.md) | ストレージ最適化オプション (A/B/C/D) — 本ドキュメントはメタデータカタログ層にフォーカス |
| [互換性マトリクス](compatibility-matrix.md) | 各プラットフォーム × フォーマット × モードの詳細検証状況 |
| [ガバナンスとコンプライアンス](governance-and-compliance.md) | Horizon Catalog、Lake Formation、監査ログの詳細 |
| [fsxn-observability-integrations](https://github.com/Yoshiki0705/fsxn-observability-integrations) | FSx for ONTAP 監査ログのモニタリングパイプライン |

---

## ペルソナレビューサマリー

| ペルソナ | 主要推奨事項 | 反映箇所 |
|---------|------------|---------|
| **AWS Iceberg SA** | S3 Tables をプライマリメタデータストアに。Iceberg REST でクロスプラットフォーム。S3 Metadata を補完パスに。 | ✅ DD-1, アーキテクチャ |
| **Databricks SA** | Iceberg REST 経由の External Catalog。Mosaic AI でエンリッチメント。Vector Search で発見。Session policy 回避策を文書化。 | ✅ Databricks パス, 制約 |
| **Snowflake PMM** | Horizon Catalog で外部エンジンガバナンス。Cortex AI パイプライン。STORAGE_REQUEST_HISTORY 監査。 | ✅ Snowflake パス, ガバナンス |
| **Storage Specialist** | ホットメタデータ × コールド実データ分離。ONTAP 重複排除の価値。Snapshot でバッチ一貫性。 | ✅ コアコンセプト, アーキテクチャ |
| **Partner SA** | FPolicy パイプラインで既存基盤活用。FlexCache S3 AP 将来パス。DataSync 代替パス。 | ✅ イベント検知, アーキテクチャ |
| **Public Sector SA** | PII 検出 + 匿名化パイプライン。データクリーンルームパターン。監査証跡要件。 | ✅ AI エンリッチメント, セキュリティ |
| **Outcome SA** | 顧客価値の再定義（検索、共有、AI、コスト）。成功 KPI。段階的導入。 | ✅ エグゼクティブサマリー, コスト |

---

## 次のステップ

1. **Phase 1**: S3 Tables テーブルバケット + Iceberg スキーマのデプロイ (1週間)
2. **Phase 2**: FPolicy → SQS → Lambda メタデータ同期パイプライン構築 (1-2週間)
3. **Phase 3**: AI エンリッチメント Step Functions ワークフロー実装 (2-3週間)
4. **Phase 4**: クロスプラットフォームアクセス設定 (Databricks, Snowflake, EMR) (1-2週間)
5. **Phase 5**: 検索・発見機能構築 (SQL + ベクトル) (1-2週間)
6. **Phase 6**: 匿名化パイプライン実装 (1-2週間)

詳細な実装計画は [タスク一覧](../../.kiro/specs/iceberg-unstructured-metadata-catalog/tasks.md) を参照。


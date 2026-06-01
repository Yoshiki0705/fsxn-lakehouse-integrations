# 非構造化データ向け Iceberg メタデータカタログ

🌐 日本語 | [English](README.md)

## 概要

FSx for ONTAP 上の非構造化ファイルを S3 にコピーせずに即座に検索可能にする **AI パワードメタデータカタログ**。Apache Iceberg（S3 Tables）をメタデータレイヤーとして、Bedrock で AI 分類、OpenSearch Serverless NextGen でベクトル検索を実現。

**主要結果**（2026-05-31 検証済み）: 40 ファイルを 30 秒でカタログ化、AI 分類 ~$0.01/ファイル、Athena クエリ 2 秒未満、フルデモ 42 秒で $0.07。

## アーキテクチャ

```
FSx for ONTAP ──S3 Access Point──→ AI Enrichment (Bedrock)
       │                                    │
       │                                    ▼
       │                          S3 Tables (Iceberg)
       │                                    │
       │                          ┌─────────┴─────────┐
       │                          ▼                   ▼
       │                    Athena (SQL)      OpenSearch (kNN)
       │                          │
       │                    Lake Formation (governance)
       │
       └──NFS/SMB──→ 既存アプリケーション (変更なし)
```

## クイックスタート

```bash
# 依存パッケージインストール
pip install -r requirements.txt

# オプション A: フルデモ (FSx for ONTAP + S3 Access Point が必要)
cd demo/scripts
./run-demo.sh --ap-alias <your-ap-alias-ext-s3alias>

# オプション B: S3 のみモード (FSx 不要)
# demo/docs/quickstart-s3-only-ja.md を参照
```

## フェーズ (全て検証済み ✅)

| フェーズ | 状態 | 説明 | 主要エビデンス |
|---------|:----:|------|-------------|
| **Phase 1** | ✅ 検証済み | S3 Tables + PyIceberg スキーマ + 初期スキャン | 40 ファイルを 3 秒で |
| **Phase 2** | ✅ 検証済み | FPolicy → SQS → Lambda パイプライン | E2E 検証、DLQ = 0 |
| **Phase 3** | ✅ 検証済み | AI エンリッチメント (Bedrock Vision + Titan Embeddings) | invoice を信頼度 0.95 で分類 |
| **Phase 4** | ⚠️ 部分的 | クロスプラットフォーム (Athena ✅、Databricks ⚠️、Snowflake ⚠️) | テスト済みパスを文書化 |
| **Phase 5** | ✅ 検証済み | OpenSearch Serverless NextGen (scale-to-zero、kNN) | スコア 0.67、コールドスタート 10-30 秒 |
| **Phase 6** | ✅ 検証済み | PII 匿名化 (Comprehend EN + Bedrock Claude JA) | 7/7 エンティティ検出 |

## ディレクトリ構成

```
integrations/iceberg-metadata-catalog/
├── README.md                              # 英語版
├── README-ja.md                           # 本ファイル
├── requirements.txt                       # Python 依存パッケージ（バージョン固定）
├── scripts/
│   ├── create-table-bucket.sh             # S3 Tables セットアップ
│   └── initial-metadata-scan.py           # 初期メタデータ投入
├── lambda/
│   └── metadata-sync-handler/             # FPolicy → SQS → Iceberg 同期
├── demo/
│   ├── scripts/                           # フルデモ (run-demo.sh + 16 スクリプト)
│   ├── docs/                              # デモガイド、S3 のみクイックスタート
│   ├── cloudformation/                    # デモインフラスタック
│   ├── notebooks/                         # Databricks/Snowflake ノートブック
│   └── sample-data/                       # 業界別サンプルデータカタログ
├── docs/
│   ├── poc-guide.md / poc-guide-ja.md     # PoC デプロイガイド
│   ├── poc-results-summary.md / -ja.md    # PoC 結果（1 ページサマリー）
│   └── standards-vs-service-behavior.md   # Iceberg 仕様 vs S3 Tables 動作
├── ops/
│   ├── iceberg-maintenance-runbook.md     # 本番メンテナンスガイド
│   └── athena-named-queries/              # キュレート済み SQL ビュー (latest_records、PII カバレッジ)
├── schema/
│   └── extensions/                        # ドメインメタデータ拡張 (製造業等)
├── verification-evidence/
│   ├── evidence-record.yaml               # 検証済み vs 推定の一覧
│   ├── cost-assumptions.yaml              # 全コスト前提条件
│   ├── cross-platform-compatibility.yaml  # プラットフォーム別テスト済みパス
│   └── 2026-05-31/                        # 詳細テスト結果
└── cloudformation/
    └── metadata-sync-pipeline.yaml        # 本番パイプラインスタック
```

## S3 Tables アクセスパス

| アクセスパス | 最適な用途 | ガバナンス | 検証済み |
|---|---|---|:---:|
| S3 Tables REST (`s3tables.<region>.amazonaws.com/iceberg`) | 直接 PoC | IAM + S3 Tables | ✅ |
| AWS Glue REST (`glue.<region>.amazonaws.com/iceberg`) | 本番 | IAM + Lake Formation | ✅ |
| Athena via Glue federated catalog | SQL 分析 | Lake Formation | ✅ |

> 本番環境では **AWS Glue Iceberg REST エンドポイント** + Lake Formation を使用してください。[ドキュメント](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-glue-endpoint.html) 参照。

## クロスプラットフォーム状況 (2026-05-31 テスト)

| プラットフォーム | 状態 | パス |
|-------------|:----:|------|
| Athena | ✅ | Glue フェデレーテッドカタログ |
| PyIceberg | ✅ | S3 Tables REST + Glue REST |
| EMR Spark | ✅ 見込み | Iceberg REST catalog |
| Databricks SQL Warehouse | ⚠️ | テスト済みパスで `iceberg_rest` 接続タイプ非対応 |
| Databricks Spark | TBD | Iceberg REST + SigV4 / UC Foreign Iceberg を検証予定 |
| Snowflake | ⚠️ | テスト済みパスで S3 Tables REST が対応カタログタイプではない |

詳細: [cross-platform-compatibility.yaml](verification-evidence/cross-platform-compatibility.yaml)

## ドキュメント

| ドキュメント | EN | JA |
|-----------|----|----|
| アーキテクチャ | [EN](../../docs/en/iceberg-metadata-catalog.md) | [JA](../../docs/ja/iceberg-metadata-catalog.md) |
| PoC 結果サマリー | [EN](docs/poc-results-summary.md) | [JA](docs/poc-results-summary-ja.md) |
| PoC ガイド | [EN](docs/poc-guide.md) | [JA](docs/poc-guide-ja.md) |
| デモガイド | [EN](demo/docs/demo-guide.md) | [JA](demo/docs/demo-guide-ja.md) |
| S3 のみクイックスタート | [EN](demo/docs/quickstart-s3-only.md) | [JA](demo/docs/quickstart-s3-only-ja.md) |
| Iceberg 仕様 vs S3 Tables | [EN](docs/standards-vs-service-behavior.md) | — |
| メンテナンス Runbook | [EN](ops/iceberg-maintenance-runbook.md) | — |

## ブログシリーズ

- **Part 1**: アーキテクチャ & PoC 結果 — 数時間から 2 秒へ
- **Part 2**: AI エンリッチメントパイプライン — Bedrock Vision + OpenSearch NextGen
- **Part 3**: ガバナンス & クロスプラットフォームアクセス

## 主要な制約事項

- テーブル、名前空間、カラム名は**小文字**を使用（S3 Tables + Athena の要件）
- Iceberg は主キーの一意性を強制しない — `ops/athena-named-queries/latest_records.sql` を使用
- Lake Formation カラム除外グラント: S3 Tables フェデレーテッドカタログパスで観測された制限
- S3 Tables の自動コンパクションはサービスマネージド — 保持要件に対する動作を確認すること

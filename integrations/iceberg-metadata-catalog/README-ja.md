# 非構造化データ向け Iceberg メタデータカタログ

🌐 日本語 | [English](README.md)

## 概要

本モジュールは **Iceberg メタデータカタログ**パターンを実装する — FSx for ONTAP に格納された非構造化データのメタデータを、Amazon S3 Tables 上の Apache Iceberg テーブルで管理する。

**アーキテクチャ**: 詳細は [docs/ja/iceberg-metadata-catalog.md](../../docs/ja/iceberg-metadata-catalog.md) を参照。

## クイックスタート (1週間 PoC)

### 前提条件

- AWS CLI v2
- Python 3.12+
- FSx for ONTAP + S3 Access Point 設定済み
- IAM 権限: `s3tables:*`, `s3:GetObject`, `s3:ListBucket` (AP ARN に対して)

### Step 1: S3 Tables テーブルバケット作成

```bash
chmod +x scripts/create-table-bucket.sh
./scripts/create-table-bucket.sh create
```

### Step 2: 初期メタデータスキャン実行

```bash
pip install boto3 pyarrow 'pyiceberg[s3tables]'

python scripts/initial-metadata-scan.py \
  --access-point-arn arn:aws:s3:ap-northeast-1:178625946981:accesspoint/your-ap-name \
  --table-bucket-arn arn:aws:s3tables:ap-northeast-1:178625946981:bucket/fsxn-metadata-catalog \
  --max-files 1000
```

### Step 3: Athena でクエリ

```sql
-- 2025年以降に作成された PDF ファイルを検索
SELECT file_name, file_path, file_size, created_at
FROM "metadata"."unstructured_files"
WHERE file_type = 'application/pdf'
  AND created_at >= TIMESTAMP '2025-01-01'
ORDER BY created_at DESC;

-- ファイルタイプ別分布
SELECT file_type, COUNT(*) as count, SUM(file_size) as total_bytes
FROM "metadata"."unstructured_files"
WHERE is_deleted = false
GROUP BY file_type
ORDER BY count DESC;

-- AI エンリッチメント待ちファイル数
SELECT COUNT(*) as pending_count
FROM "metadata"."unstructured_files"
WHERE enrichment_status = 'pending';
```

## ディレクトリ構成

```
integrations/iceberg-metadata-catalog/
├── README.md                          # 英語版
├── README-ja.md                       # 本ファイル
├── scripts/
│   ├── create-table-bucket.sh         # S3 Tables セットアップスクリプト
│   └── initial-metadata-scan.py       # 初期メタデータ投入
├── lambda/                            # (Phase 2) FPolicy → メタデータ同期
│   └── metadata-sync-handler/
├── step-functions/                    # (Phase 3) AI エンリッチメントワークフロー
│   └── enrichment-workflow.asl.json
└── queries/                           # (Phase 5) Athena Named Queries
    └── common-searches.sql
```

## フェーズ

| Phase | 状態 | 説明 |
|-------|------|------|
| **Phase 1** | ✅ 実装済み | S3 Tables セットアップ + 初期スキャンスクリプト |
| Phase 2 | 🔲 計画中 | FPolicy → SQS → Lambda メタデータ同期 |
| Phase 3 | 🔲 計画中 | AI エンリッチメント (Step Functions + Bedrock) |
| Phase 4 | 🔲 計画中 | クロスプラットフォームアクセス (Databricks, Snowflake) |
| Phase 5 | 🔲 計画中 | 検索・発見 (SQL + ベクトル) |
| Phase 6 | 🔲 計画中 | 匿名化パイプライン |

## 関連ドキュメント

- [アーキテクチャドキュメント (JA)](../../docs/ja/iceberg-metadata-catalog.md)
- [アーキテクチャドキュメント (EN)](../../docs/en/iceberg-metadata-catalog.md)
- [互換性マトリクス](../../docs/ja/compatibility-matrix.md)

# DuckDB 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: ✅ 機能検証済み (2026-05-23)**
>
> DuckDB 1.4.4 + httpfs で FSx for ONTAP S3 AP（internet-origin）上のローカル検証完了。
> - 読み取り: 10K 行 628ms、5M 行 779ms
> - 集計: GROUP BY 1.2s、Window 関数 1.0s
> - 書き戻し: COPY TO Parquet 304ms

## 概要

DuckDB を使用した FSx for ONTAP データの軽量インプロセス分析。サーバー不要。
Lambda にデプロイしてサーバーレス従量課金クエリ、またはローカル/EC2 で実行可能。

## アーキテクチャ

```
Lambda (arm64, Python 3.12)          ローカル / EC2
    │                                    │
    └── DuckDB (インプロセス)              └── DuckDB (インプロセス)
            │                                    │
            └── httpfs 拡張                       └── httpfs 拡張
                    │                                    │
                    └── S3 AP ──→ FSx for ONTAP          └── S3 AP ──→ FSx for ONTAP
```

## 主な特徴

- **インフラ不要**: DuckDB はインプロセスで動作（データベースサーバー不要）
- **Lambda デプロイ**: サーバーレス、従量課金、arm64 Graviton
- **Parquet プッシュダウン**: 述語・射影プッシュダウンで最小限のデータ転送
- **書き戻し**: 結果を FSx for ONTAP に Parquet/CSV で書き込み
- **サブ秒クエリ**: ウォーム Lambda で 200-500ms

## 非構造化データ対応

| フォーマット | 対応 | アクセス方法 | ユースケース |
|------------|:---:|------------|------------|
| 画像 (JPEG, PNG, TIFF) | ⚠️ | httpfs バイナリ読み取り（Lambda） | メタデータ抽出、ファイル一覧 |
| 動画 (MP4, MOV) | ⚠️ | httpfs バイナリ読み取り（Lambda） | ファイルカタログ、サイズ追跡 |
| ドキュメント (PDF, DOCX) | ⚠️ | httpfs バイナリ読み取り（Lambda） | ファイル一覧、パイプライントリガー |
| 音声 (WAV, MP3) | ⚠️ | httpfs バイナリ読み取り（Lambda） | ファイルカタログ、メタデータクエリ |
| バイナリ / アーカイブ | ⚠️ | httpfs バイナリ読み取り（Lambda） | ダウンロード、カスタム処理 |

DuckDB は構造化データ（Parquet, CSV, JSON）のクエリエンジンですが、httpfs 経由でバイナリファイルの読み取りが可能です。ビルトインのファイルカタログや非構造化データ処理機能はありません。

**非構造化データワークフローのパターン:**
1. **ファイルカタログクエリ** — S3 AP 上のファイル一覧をメタデータテーブルとしてクエリ
2. **メタデータ抽出** — Parquet メタデータ（行数、スキーマ）を DuckDB で高速に取得
3. **パイプライン連携** — DuckDB でファイルパスを抽出し、Lambda/Bedrock で非構造化処理

```sql
-- S3 AP 上のファイル一覧をクエリ（glob パターン）
SELECT filename, size
FROM glob('s3://<ap-alias>/documents/*.pdf');

-- メタデータテーブルから処理対象を抽出
SELECT file_path, file_size, last_modified
FROM file_catalog
WHERE file_type = 'image/jpeg' AND processed = false;
```

**FSx for ONTAP 上の非構造化データの推奨代替手段:**
- **AWS Lambda** でサーバーレスファイル処理（[AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-process-files-with-lambda.html)）
- **Amazon Bedrock** でドキュメント RAG（[AWS チュートリアル](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)）
- **Snowflake**（Directory Table + GET_PRESIGNED_URL）でファイルカタログとセキュア URL 生成

## クイックスタート

```bash
# ローカルクエリ
pip install duckdb boto3
python notebooks/01_local_queries.py --ap-alias <your-ap-alias>

# Lambda デプロイ
./lambda/build_layer.sh
./deploy.sh
python scripts/validate_connectivity.py
```

# AWS Glue 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: 🚧 実装中**

## 概要

AWS Glue 4.0 を使用して Amazon FSx for NetApp ONTAP 上にメダリオンアーキテクチャ（Bronze → Silver → Gold）ETL パイプラインを構築します。GlueContext/DynamicFrame API と S3 Access Points を使用。サーバーレスでスケーラブルなデータ変換を実現します。

## アーキテクチャ

```
EventBridge (スケジュール)
    │
    ▼
Glue Crawler ──→ Glue Data Catalog
    │                    │
    ▼                    ▼
Glue ETL Job         Glue ETL Job
(Bronze→Silver)      (Silver→Gold)
    │                    │
    ▼                    ▼
S3 Access Point (internet origin) ──→ FSx for ONTAP Volume
                                        ├── bronze/ (生データ)
                                        ├── silver/ (クレンジング済み)
                                        └── gold/ (集計済み)
```

## 重要: ネットワークオリジン

Glue は **internet ネットワークオリジン** の S3 Access Point が必要です。
VPC 限定のアクセスポイントは Glue ETL ジョブでは動作しません。

## 主な特徴

- **Glue 4.0** (Spark 3.3+) — GlueContext と DynamicFrame API
- **Job Bookmarks** — インクリメンタル処理（過去データの再処理なし）
- **メダリオンアーキテクチャ**: Bronze（生）→ Silver（クレンジング）→ Gold（集計）
- **データ品質**: DQDL ルールによる完全性・一意性・値範囲・鮮度チェック
- **ZSTD 圧縮**: Silver/Gold Parquet ファイルの最適圧縮

## 非構造化データ対応

Glue は主に構造化データの ETL に使用されますが、非構造化データのメタデータ管理パイプラインも構築可能です。

**パターン:**
1. **Glue Crawler** — S3 AP 上のファイル構造をカタログ化（パス、サイズ、更新日時）
2. **PySpark バイナリ読み込み** — `binaryFile` フォーマットで画像・PDF を処理
3. **メタデータ ETL** — ファイルメタデータを Bronze → Silver → Gold で管理
4. **イベント駆動** — FPolicy + EventBridge で新規ファイル検出時に Crawler を自動実行

```python
# Glue ETL でファイルメタデータを処理
from awsglue.context import GlueContext
glueContext = GlueContext(SparkContext.getOrCreate())

# ファイルカタログからメタデータを読み込み
df = glueContext.create_dynamic_frame.from_catalog(
    database="fsxn_catalog",
    table_name="file_metadata"
).toDF()

# 非構造化ファイルのメタデータを集計
df.filter(df.file_type.isin(['image/jpeg', 'application/pdf'])) \
  .groupBy("file_type").count().show()
```

## クイックスタート

```bash
# 1. パラメータをコピーして値を設定
cp params.example.json params.json

# 2. サンプルデータを生成
pip install pandas pyarrow boto3
python scripts/generate_sample_data.py

# 3. FSx for ONTAP に NFS 経由でアップロード
rsync -avz ./sample_data/bronze/ /mnt/fsxn/bronze/

# 4. インフラをデプロイ
./deploy.sh

# 5. ETL パイプラインを実行
python scripts/run_etl_pipeline.py
```

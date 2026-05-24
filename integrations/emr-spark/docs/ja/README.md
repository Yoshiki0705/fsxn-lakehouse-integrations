# EMR Serverless Spark 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: ✅ 機能検証済み (2026-05-23)**
>
> - 読み取り 10K 行: 6.78s
> - GROUP BY 集計: 2.52s
> - Window 関数: 1.19s
> - FSxN への書き戻し: 3.61s
> - Spark 実行合計: 16.35s（ジョブ合計: 37s、コールドスタート含む）

## 概要

EMR Serverless を使用して FSx for ONTAP のデータを S3 Access Points 経由で Spark SQL 処理します。
Parquet の読み取り、変換、書き戻し — クラスター管理不要。

## アーキテクチャ

```
EMR Serverless (Spark 3.5)
    │
    └── EMRFS (s3:// — S3 AP エイリアスをネイティブサポート)
            │
            └── S3 Access Point (internet-origin) ──→ FSx for ONTAP Volume
```

## 重要な発見: EMRFS vs S3A

- **EMRFS (`s3://`)**: S3 AP エイリアスをネイティブサポート。こちらを使用。
- **S3A (`s3a://`)**: AP エイリアスでは動作しない（URL パースエラー）。使用不可。

## 非構造化データ対応

EMR Spark は構造化データの大規模 ETL に最適化されていますが、非構造化データの処理パイプラインも構築可能です。

**パターン:**
1. **Spark バイナリファイル読み取り** — `spark.read.format("binaryFile")` で画像・PDF をバイナリとして読み込み
2. **UDF による処理** — Spark UDF 内で画像処理・テキスト抽出を実行
3. **メタデータ ETL** — ファイルメタデータを構造化テーブルとして管理し、処理パイプラインを構築

```python
# バイナリファイルの読み込み（画像、PDF など）
df = spark.read.format("binaryFile") \
    .option("pathGlobFilter", "*.pdf") \
    .load("s3://<ap-alias>/documents/")

# ファイルメタデータの取得
df.select("path", "length", "modificationTime").show()
```

## クイックスタート

```bash
# 1. EMR Serverless アプリケーションを作成
aws emr-serverless create-application \
  --name "fsxn-spark" --release-label "emr-7.1.0" --type "SPARK"

# 2. PySpark スクリプトをアップロード
aws s3 cp scripts/spark_verification.py s3://<your-bucket>/emr-scripts/

# 3. ジョブを実行
aws emr-serverless start-job-run \
  --application-id <app-id> \
  --execution-role-arn <role-arn> \
  --job-driver '{"sparkSubmit":{"entryPoint":"s3://<bucket>/emr-scripts/spark_verification.py"}}'

# 4. アプリケーションを停止（コスト管理）
aws emr-serverless stop-application --application-id <app-id>
```

## コスト

EMR Serverless は vCPU 時間と GB 時間で課金。37 秒のジョブは約 $0.05。
アプリケーション停止時はコストゼロ。

🌐 [English](README.md) | **日本語**

# モジュール 05: EMR Serverless Spark ETL（読み取り + 書き戻し）

## 概要

EMR Serverless Spark が S3 Access Points 経由で FSx for ONTAP の Parquet を読み取り、変換し、書き戻します。クラスタ管理不要、読み取りにデータコピー不要。

```
FSx for ONTAP ──S3 AP──▶ EMR Serverless Spark ──S3 AP──▶ FSx for ONTAP (gold/)
                         (読み取り + 変換 + 書き込み)
```

## 前提条件

- S3 Access Point 付き FSx for ONTAP（読み書き可能なファイルシステムユーザー）
- スクリプト保存用 S3 バケット（通常の S3、S3 AP ではない）
- S3 AP + S3 バケット権限付き IAM 実行ロール

## クイックスタート

```bash
# 1. PySpark スクリプトを S3 にアップロード
aws s3 cp spark-job.py s3://<SCRIPTS_BUCKET>/emr-scripts/

# 2. EMR Serverless アプリケーション作成
aws emr-serverless create-application \
  --name "fsxn-poc-spark" \
  --release-label "emr-7.1.0" \
  --type "SPARK"

# 3. ジョブ送信
aws emr-serverless start-job-run \
  --application-id <APP_ID> \
  --execution-role-arn <ROLE_ARN> \
  --job-driver '{
    "sparkSubmit": {
      "entryPoint": "s3://<SCRIPTS_BUCKET>/emr-scripts/spark-job.py"
    }
  }'
```

## 重要な注意事項

- **`s3://`（EMRFS）を使用**、`s3a://` は不可 — S3A は AP エイリアスをパースできない
- **Parquet タイムスタンプはマイクロ秒必須** — ナノ秒（pandas デフォルト）は Spark エラーの原因
- **スクリプトは通常の S3 に配置** — FSx S3 AP 上ではない

## ベンチマーク

| 操作 | 所要時間 |
|------|---------|
| 10K 行読み取り | 6.78秒 |
| GROUP BY 集計 | 2.52秒 |
| ウィンドウ関数 | 1.19秒 |
| FSxN への書き戻し | 3.61秒 |
| **Spark 実行合計** | **16.35秒** |
| ジョブ合計（コールドスタート含む） | 37秒 |
| **ジョブあたりコスト** | **~$0.05** |

## コスト

- ゼロアイドルコスト（ジョブ間はアプリケーション停止）
- ~$0.05/ジョブ（37秒実行）
- 10ジョブ/日 = ~$15/月

# Delta Lake OSS 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: 🚧 実装中**

## 概要

オープンソース Delta Lake（delta-spark + delta-rs）を FSx for ONTAP 上で S3 Access Points 経由で使用します。Databricks Runtime なしで ACID トランザクション、Time Travel、OPTIMIZE/VACUUM をエンタープライズ NAS ストレージ上で実現。

## アーキテクチャ

```
Apache Spark (EMR / セルフマネージド)
    └── delta-spark 3.1.0
            └── S3A FileSystem
                    └── S3 Access Point ──→ FSx for ONTAP Volume
                                              ├── _delta_log/
                                              └── data/*.parquet

Python (ローカル / Lambda)
    └── deltalake (delta-rs)
            └── S3 Access Point ──→ FSx for ONTAP Volume
```

## 主な特徴

- **delta-spark**: フル CRUD（INSERT, UPDATE, DELETE, MERGE）、OPTIMIZE、VACUUM
- **delta-rs**: Spark 不要の Python アクセス（Delta テーブルの読み書き）
- **Time Travel**: 過去バージョンのクエリ、RESTORE TABLE
- **クロス互換性**: Spark で作成したテーブルを delta-rs で読み取り可能（逆も同様）

## 非構造化データ対応

| フォーマット | 対応 | アクセス方法 | ユースケース |
|------------|:---:|------------|------------|
| 画像 (JPEG, PNG, TIFF) | ❌ | N/A（構造化テーブルフォーマット） | — |
| 動画 (MP4, MOV) | ❌ | N/A | — |
| ドキュメント (PDF, DOCX) | ❌ | N/A | — |
| 音声 (WAV, MP3) | ❌ | N/A | — |
| バイナリ / アーカイブ | ❌ | N/A | — |

Delta Lake は構造化データ（Parquet ベースのテーブル）のフォーマットです。非構造化データの直接格納やクエリはサポートされていません。ただし、Delta テーブルを使用してファイルメタデータを ACID トランザクション、Change Data Feed、Time Travel 付きで管理できます。

**メタデータ管理パターン:**
```python
# delta-rs でファイルメタデータを管理（Spark 不要）
import deltalake as dl
import pandas as pd

# ファイルカタログを Delta テーブルとして書き込み
df = pd.DataFrame({
    'file_path': ['s3://ap-alias/images/001.jpg', 's3://ap-alias/docs/report.pdf'],
    'file_type': ['image/jpeg', 'application/pdf'],
    'file_size': [2048000, 512000],
    'processed': [False, False]
})
dl.write_deltalake('s3://<ap-alias>/file_catalog/', df, mode='append')

# Time Travel で過去のカタログ状態を確認
dt = dl.DeltaTable('s3://<ap-alias>/file_catalog/', version=3)
print(dt.to_pandas())
```

## クイックスタート

```bash
# delta-rs（Spark 不要）
pip install deltalake pandas boto3
python notebooks/05_delta_rs.py --s3-ap-alias <alias>

# delta-spark (EMR)
spark-submit --packages io.delta:delta-spark_2.12:3.1.0 \
    --properties-file config/spark-defaults.conf \
    notebooks/01_delta_crud.py --s3-ap-alias <alias>
```

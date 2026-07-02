# Trino / Starburst 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: ✅ 読み取り検証済み (2026-05-24)**
>
> - **読み取り**: FSx for ONTAP S3 AP 上の全クエリ成功（10K / 5M 行 Parquet）
> - **書き戻し (CTAS)**: ファイルベースメタストアの制限により失敗（FSx for ONTAP S3 AP の問題ではない）
> - **セッションポリシー問題なし**: 直接 IAM 認証情報、中間ガバナンスレイヤーなし
>
> **ベンチマーク (Trino 438, シングルノード Docker arm64, ap-northeast-1):**
>
> | クエリ | 10K 行 | 5M 行 (103 MB) |
> |-------|--------|----------------|
> | COUNT(*) | 1,136 ms | 1,075 ms |
> | GROUP BY + AVG | 860 ms | 1,462 ms |
> | WHERE フィルター | — | 1,227 ms |

## 概要

Trino（オープンソース分散 SQL クエリエンジン）を使用して FSx for ONTAP のデータを S3 Access Points 経由でクエリします。Trino の S3 ファイルシステム実装はパススタイルアクセスをサポートしており、FSx for ONTAP S3 AP エイリアスと互換性があります。

## アーキテクチャ

```
Trino (Docker, シングルノード)
    │
    └── Hive Connector (ファイルベースメタストア)
            │
            └── S3 filesystem (パススタイルアクセス)
                    │
                    └── FSx S3 Access Point (internet-origin)
                            │
                            └── FSx for ONTAP Volume (Parquet ファイル)
```

## 非構造化データ対応

| フォーマット | 対応 | アクセス方法 | ユースケース |
|------------|:---:|------------|------------|
| 画像 (JPEG, PNG, TIFF) | ❌ | N/A（構造化データ用 SQL エンジン） | — |
| 動画 (MP4, MOV) | ❌ | N/A | — |
| ドキュメント (PDF, DOCX) | ❌ | N/A | — |
| 音声 (WAV, MP3) | ❌ | N/A | — |
| バイナリ / アーカイブ | ❌ | N/A | — |

Trino は構造化データの分散 SQL クエリに特化したエンジンです。非構造化データの直接クエリはサポートされていません。メタデータテーブルとフェデレーテッドクエリを活用したパターンが可能です。

**パターン:**
1. **メタデータテーブル** — ファイルパス・サイズ・タイプを Hive テーブルとして登録しクエリ
2. **マルチソースフェデレーション** — FSx for ONTAP S3 AP のファイルカタログと他のデータソース（RDS, PostgreSQL）を JOIN
3. **Hive Connector** — パススタイルアクセスで S3 AP 上の Parquet メタデータを直接読み取り

```sql
-- ファイルカタログをクエリ
SELECT file_path, file_type, file_size, last_modified
FROM fsxn.default.file_catalog
WHERE file_type = 'image/jpeg'
  AND file_size > 1000000;

-- 他のデータソースとフェデレーテッド JOIN
SELECT f.file_path, m.model_name, m.accuracy
FROM fsxn.default.file_catalog f
JOIN ml_catalog.default.model_results m ON f.file_path = m.input_path;
```

## 主な設定

```properties
# catalog/fsxn.properties
connector.name=hive
hive.metastore=file
hive.metastore.catalog.dir=s3://<FSx-S3-AP-alias>/
hive.s3.path-style-access=true
hive.s3.endpoint=https://s3.ap-northeast-1.amazonaws.com
hive.s3.region=ap-northeast-1
```

## クイックスタート

```bash
# 1. Trino を起動 (Docker)
docker compose up -d

# 2. Trino CLI で接続
docker exec -it trino trino --catalog fsxn --schema default

# 3. クエリを実行
trino> SELECT COUNT(*) FROM sensor_data;
trino> SELECT status, AVG(temperature) FROM sensor_data GROUP BY status;
```

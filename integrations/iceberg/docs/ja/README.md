# Apache Iceberg 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: 🚧 計画中**

## 概要

Amazon FSx for NetApp ONTAP（FSx for ONTAP）上でベンダー中立な Apache Iceberg テーブル管理を実現します。REST Catalog によるメタデータ管理で、Iceberg 互換の任意のエンジンからアクセス可能。

## アーキテクチャ

```
任意のエンジン (Spark/Trino/Flink/Databricks/Snowflake)
    │
    └── REST Catalog (Lambda/ECS)
            │
            └── S3 Access Point ──→ FSx for ONTAP Volume (Parquet データ + Iceberg メタデータ)
```

## 非構造化データ対応

| フォーマット | 対応 | アクセス方法 | ユースケース |
|------------|:---:|------------|------------|
| 画像 (JPEG, PNG, TIFF) | ❌ | N/A（構造化テーブルフォーマット） | — |
| 動画 (MP4, MOV) | ❌ | N/A | — |
| ドキュメント (PDF, DOCX) | ❌ | N/A | — |
| 音声 (WAV, MP3) | ❌ | N/A | — |
| バイナリ / アーカイブ | ❌ | N/A | — |

Iceberg は構造化データ（Parquet テーブル）のテーブルフォーマットです。非構造化データの直接格納やクエリはサポートされていません。ただし、Iceberg テーブルを使用して非構造化ファイルのメタデータを ACID 保証付きで管理し、Time Travel やスキーマ進化を活用できます。

**メタデータ管理パターン:**
```sql
-- 非構造化ファイルのメタデータを Iceberg テーブルで管理
CREATE TABLE file_catalog (
    file_path STRING,
    file_type STRING,
    file_size BIGINT,
    last_modified TIMESTAMP,
    processed BOOLEAN,
    tags MAP<STRING, STRING>
) USING iceberg
PARTITIONED BY (file_type, days(last_modified));

-- Time Travel でファイルカタログの過去状態を確認
SELECT * FROM file_catalog VERSION AS OF 5;
```

## ONTAP の価値

| ONTAP 機能 | Iceberg へのメリット |
|-----------|-------------------|
| Snapshot | Iceberg テーブル全体（メタデータ + データファイル）の復旧 |
| FlexClone | 本番環境のクローンでスキーマ/パーティション進化をテスト |
| 重複排除 | Iceberg コンパクションで生成される重複ブロックのストレージ削減 |
| FabricPool | 古いスナップショット/パーティションの S3 自動階層化 |

## 計画コンテンツ

- [ ] CloudFormation テンプレート（REST Catalog on Lambda/ECS）
- [ ] Iceberg REST Catalog 設定
- [ ] サンプルテーブル作成スクリプト
- [ ] マルチエンジンアクセス例（Spark, Trino, Databricks, Snowflake）
- [ ] E2E 検証タスク

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

Iceberg は構造化データ（Parquet テーブル）のテーブルフォーマットですが、非構造化データの管理に以下のパターンで活用できます。

**パターン:**
1. **メタデータテーブル** — 非構造化ファイルのパス・サイズ・タイプを Iceberg テーブルで管理
2. **Time Travel** — ファイルカタログの履歴を Iceberg のバージョン管理で追跡
3. **パーティション進化** — ファイルタイプ・日付でパーティションを動的に変更
4. **スキーマ進化** — メタデータスキーマを無停止で拡張（新しいタグ列の追加など）

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

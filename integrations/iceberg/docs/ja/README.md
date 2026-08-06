# Apache Iceberg 統合

🌐 [English](../../README.md) | **日本語**

> **検証ステータス: ✅ 読み取り検証済み / ❌ 書き込み失敗**
> - Iceberg **読み取り** (PyIceberg + S3 Tables REST Catalog): ✅（881ms スキャン、23 フィールドスキーマ、SigV4 認証）
> - Iceberg **書き込み** (CREATE TABLE on FSx for ONTAP S3 AP): ❌ NullPointerException — S3FileIO が AP alias のメタデータコミットを処理できない
> - 完全なメタデータカタログアーキテクチャは [`integrations/iceberg-metadata-catalog/`](../../../iceberg-metadata-catalog/) を参照

## 概要

Amazon FSx for NetApp ONTAP（FSx for ONTAP）上でベンダー中立な Apache Iceberg テーブル管理を実現します。REST Catalog によるメタデータ管理で、Iceberg 互換の任意のエンジンからアクセス可能。

## アーキテクチャ

```
任意のエンジン (Spark/Trino/Flink/Databricks/Snowflake)
    │
    ├── Iceberg REST Catalog (S3 Tables)  ──→  マネージド Iceberg テーブル（メタデータ）
    │                                              ↓ file_path 参照
    └── S3 Access Point ──→ FSx for ONTAP Volume（生データファイル）
```

## 検証結果 (2026-05-24)

| 操作 | ステータス | 詳細 |
|------|:---:|------|
| PyIceberg + S3 Tables REST endpoint | ✅ | スキーマ（23 フィールド）、namespace 一覧、データスキャン（881ms）。SigV4 認証必要 |
| Iceberg READ（既存テーブル、Glue メタデータ） | ✅ | delta-rs/PyIceberg が S3 AP 上の GetObject で Iceberg メタデータファイルを読み取り |
| Iceberg WRITE（CREATE TABLE, Spark + S3FileIO） | ❌ | メタデータコミット時の NullPointerException — S3FileIO が AP alias を解決できない |
| Iceberg WRITE（CREATE TABLE, Spark + S3A） | ❌ | S3A FileSystem は AP alias 非対応 |
| Glue Catalog データベース作成 | ✅ | `glue:CreateDatabase` は動作 |

### 根本原因（書き込み失敗）

Iceberg の `S3FileIO` が warehouse パス（FSx for ONTAP S3 AP）にメタデータファイル (`metadata.json`) を書き込む際にコミットフェーズで失敗:

1. S3FileIO が S3 AP alias をバケット名として正しく処理できない
2. メタデータ書き込みに条件付き書き込み（競合検出）が必要 → FSx for ONTAP S3 AP は `501 Not Implemented` を返す
3. Delta Lake・Hudi と同一の根本原因 — [Part 7（テーブルフォーマット制約）](../../../../docs/ja/fsx-ontap-to-databricks-unity-catalog-guide.md) 参照

### 推奨パターン

**メタデータとデータレイヤーを分離:**

```
Iceberg メタデータ  →  標準 S3 バケット（または S3 Tables）
Iceberg データファイル →  FSx for ONTAP S3 AP（読み取りパス）
                        または標準 S3（書き込みパス）
```

このパターンの完全な実装は [`integrations/iceberg-metadata-catalog/`](../../../iceberg-metadata-catalog/) を参照 — S3 Tables で Iceberg メタデータを管理し、生ファイルは FSx for ONTAP に保持するメタデータカタログアーキテクチャ。

## データフォーマット対応

| フォーマット | S3 AP 経由読み取り | S3 AP 経由書き込み | 備考 |
|------------|:---:|:---:|------|
| Parquet（フラット） | ✅ | ✅ | PutObject でフラットファイル書き込み可 |
| Parquet（Iceberg テーブル） | ✅ | ❌ | 読み取り可、書き込みはメタデータコミットが必要 |
| Iceberg メタデータ JSON | ✅ (GetObject) | ❌ | メタデータ読み取り可、コミット書き込み不可 |

## 非構造化データ対応

Apache Iceberg は構造化データのテーブルフォーマット。非構造化データの直接格納・クエリはできません。ただし、Iceberg テーブルで**非構造化ファイルのメタデータを管理**することで、ACID 保証、タイムトラベル、スキーマ進化の恩恵を受けられます。

```sql
-- 非構造化ファイルのメタデータを Iceberg テーブルで管理
CREATE TABLE file_catalog (
    file_path STRING,
    file_type STRING,
    file_size BIGINT,
    last_modified TIMESTAMP,
    classification STRING,
    embedding BINARY,
    tags MAP<STRING, STRING>
) USING iceberg
PARTITIONED BY (file_type, days(last_modified));
```

このパターンの完全実装: [`integrations/iceberg-metadata-catalog/`](../../../iceberg-metadata-catalog/)

## ONTAP の価値

| 機能 | メリット |
|------|---------|
| Snapshot | Iceberg テーブル全体（メタデータ + データファイル）の状態復旧 |
| FlexClone | 本番影響なしでスキーマ/パーティション変更をクローン上でテスト |
| 重複排除 | Iceberg コンパクションが重複ブロックを生成 → dedup でスペース節約 |
| FabricPool | 古いスナップショット/パーティションを自動的に S3 に階層化 |
| S3 AP | S3 コピーなしで Iceberg データファイルの読み取りパス |

## 関連ドキュメント

| ドキュメント | 説明 |
|-------------|------|
| [Iceberg Metadata Catalog](../../../iceberg-metadata-catalog/) | 完全実装: FPolicy + S3 Tables + AI エンリッチメント |
| [Iceberg Metadata Catalog (docs)](../../../../docs/ja/iceberg-metadata-catalog.md) | アーキテクチャ詳細解説 |
| [Part 7: テーブルフォーマット制約](../../../../docs/ja/compatibility-matrix.md) | Delta/Iceberg/Hudi の書き込みが S3 AP で失敗する理由 |
| [検証エビデンス](../../../../verification-pack/iceberg/) | 生テスト結果 |

## エビデンス

- [`verification-pack/iceberg/evidence/2026-05-24/`](../../../../verification-pack/iceberg/evidence/2026-05-24/) — Iceberg 書き込み失敗エビデンス（NPE）
- [`verification-pack/opensharing-sts-vending/`](../../../../verification-pack/opensharing-sts-vending/) — Iceberg メタデータ GetObject の credential vending 経由確認

# ETL パス: S3 Tables → 標準 Glue Iceberg → Snowflake

🌐 日本語 | [English](README.md)

## 目的

> **これは 2026-06-03 時点の制約に対するワークアラウンドです**: S3 Tables 内部バケットは以下の理由により Snowflake からアクセスできません: (1) Glue Iceberg REST が標準 Iceberg REST `/credentials` エンドポイントを実装していない、(2) S3 Tables 内部バケットが Snowflake のストレージアクセスパターンに必要な `ListObjectsV2` を拒否する。AWS は `/credentials` エンドポイント実装のフィーチャーリクエストを受理済みです。これが解決されれば、この ETL パスは不要となり、Snowflake から S3 Tables への直接アクセスが可能になります。

このワークアラウンドは、S3 Tables から**メタデータのみ**（ソースファイルではない）を通常の S3 バケット上の標準 Glue 管理 Iceberg テーブルにレプリケートします。そこから Snowflake の `VENDED_CREDENTIALS` + Lake Formation 統合（public preview）で統制された Iceberg アクセスが可能になります。

**変わらないもの**:
- ソースファイルは FSx for ONTAP に残る（ゼロコピーストレージ原則を維持）
- S3 Tables が権威的メタデータカタログとして継続（Athena、EMR Spark アクセスは変更なし）
- 複製されるのは Iceberg メタデータテーブルのデータファイルのみ（~MB スケール）

**なぜ標準 S3 であり、FSx S3 Access Point ではないか**:
- FSx S3 AP は PutObject/DeleteObject/ListObjectsV2 をサポートしているが、Iceberg テーブルのデータファイル保存先として使う場合、PyIceberg/Spark の Iceberg ライブラリが FSx S3 AP エイリアス形式の URI をサポートしているか未検証
- Iceberg カタログ（Glue Data Catalog）にテーブルロケーションとして FSx S3 AP パスを登録できるか未確認
- 標準 S3 バケットは Glue + Lake Formation + Snowflake の全コンポーネントとの互換性が確認済みのため、確実なパスとして選択
- FSx S3 AP をメタデータ Iceberg テーブルの保存先として使えるかは将来の検証候補

---

## アーキテクチャ

```
S3 Tables (信頼のソース)
    │
    │ PyIceberg 読み取り
    ▼
ETL Lambda / スクリプト
    │
    │ PyIceberg 書き込み
    ▼
標準 S3 バケット (Iceberg 形式)
    │
    │ Glue Data Catalog に登録
    ▼
Lake Formation (ガバナンス)
    │
    │ VENDED_CREDENTIALS
    ▼
Snowflake (CATALOG INTEGRATION)
```

## 前提条件

- S3 Tables メタデータテーブルにデータが存在すること（検証済み）
- Iceberg ターゲット用の標準 S3 バケット (例: `s3://<bucket>/iceberg-mirror/`)
- ミラーテーブル用の Glue データベース
- 適切な権限で設定された Lake Formation
- Iceberg カタログ統合機能を持つ Snowflake アカウント

## ステップ

### ステップ 1: ターゲット S3 バケットと Glue データベースの作成

```bash
# ミラー Iceberg テーブル用 S3 バケットの作成
aws s3 mb s3://fsxn-metadata-mirror-<ACCOUNT_ID> --region ap-northeast-1

# Glue データベースの作成
aws glue create-database \
  --database-input '{"Name":"metadata_mirror","Description":"Snowflake アクセス用に S3 Tables からミラーされたメタデータ"}' \
  --region ap-northeast-1
```

### ステップ 2: ETL スクリプト — S3 Tables から読み取り、標準 Iceberg に書き込み

```bash
python etl-s3tables-to-standard-iceberg.py
```

完全なスクリプトは [etl-s3tables-to-standard-iceberg.py](etl-s3tables-to-standard-iceberg.py) を参照。

### ステップ 3: Lake Formation への登録

```bash
# S3 ロケーションを Lake Formation に登録
aws lakeformation register-resource \
  --resource-arn 'arn:aws:s3:::fsxn-metadata-mirror-<ACCOUNT_ID>' \
  --use-service-linked-role \
  --region ap-northeast-1

# Snowflake IAM ロールに権限を付与
aws lakeformation grant-permissions \
  --principal '{"DataLakePrincipal":{"DataLakePrincipalIdentifier":"arn:aws:iam::<ACCOUNT_ID>:role/fsxn-snowflake-verification-role"}}' \
  --resource '{"Table":{"DatabaseName":"metadata_mirror","Name":"unstructured_files","CatalogId":"<ACCOUNT_ID>"}}' \
  --permissions '["SELECT","DESCRIBE"]' \
  --region ap-northeast-1
```

### ステップ 4: Athena で検証

```sql
SELECT * FROM metadata_mirror.unstructured_files LIMIT 10;
```

### ステップ 5: Snowflake CATALOG INTEGRATION（標準 Glue、s3tablescatalog ではない）

```sql
-- snowflake-setup.sql を参照
```

## 期待される結果

| テスト | 期待値 |
|--------|--------|
| PyIceberg ETL (S3 Tables 読み取り → 標準 S3 書き込み) | ✅ 動作するはず |
| Athena でミラーテーブルをクエリ | ✅ 動作するはず |
| Snowflake CATALOG INTEGRATION (標準 Glue) | ✅ 動作するはず (public preview) |
| Snowflake CREATE ICEBERG TABLE | ✅ 動作するはず |
| Snowflake SELECT | ✅ 動作するはず |
| Lake Formation ガバナンス経由 Snowflake | ⚠️ 要検証 |

## 制約事項

- **ゼロコピーではない**: メタデータが S3 Tables から標準 S3 に複製される（ただしメタデータのみ、生ファイルはコピーされない）
- **同期ラグ**: ETL はスケジュール実行（リアルタイムではない）
- **デュアルテーブル管理**: スキーマ変更は S3 Tables とミラーの両方に適用が必要
- **Public Preview**: Snowflake + Lake Formation 統合に制限がある可能性
- **コスト**: 追加 S3 ストレージ（最小限 — メタデータのみ）+ ETL コンピュート

## このパスが不要になる条件

以下のいずれかが実現された場合、この ETL パスは不要になります:
1. AWS が Glue Iceberg REST エンドポイントに標準 Iceberg REST `/credentials` を実装（フィーチャーリクエスト提出済み）
2. Snowflake がネイティブ S3 Tables サポートを追加（公開タイムラインなし）
3. S3 Tables 内部バケットが外部エンジンからアクセス可能になる（公開タイムラインなし）

---

*関連: [Snowflake アクティベーションパターン](../../demo/scenarios/snowflake-activation-pattern-ja.md)*
*関連: [Glue REST credential vending 検証](../glue-rest-vended-credentials-validation-ja.md)*

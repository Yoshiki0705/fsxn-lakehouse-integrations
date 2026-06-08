# 次の検証項目

🌐 [English](next-validations.md) | 日本語

## 目的

エキスパートレビューで特定された残りの検証項目を追跡する。プラットフォームと優先度でグループ化。

## A. AWS ネイティブパス — 再現性

| # | 検証内容 | 優先度 | 状態 |
|---|---------|:---:|:---:|
| A-1 | 新規アカウント / 新規リージョンでの再現（CloudFormation エンドツーエンド） | 高 | TBD |
| A-2 | 最小 IAM 権限の文書化 | 高 | TBD |
| A-3 | ap-northeast-1 vs us-east-1 の差分（S3 Tables、Bedrock、OpenSearch NextGen、Glue REST） | 中 | TBD |
| A-4 | S3 Tables direct REST vs Glue Iceberg REST: PyIceberg、Spark、Athena、Lake Formation | 中 | ✅ 検証済み: Athena ✅、PyIceberg ✅、EMR Spark 7.13.0 ✅ (full SELECT + time travel)、Glue REST credential vending ❌ (未実装) |
| A-5 | Glue REST /v1/config の credential vending 指標を監視 | 低 | TBD — `token-refresh-enabled` が `false` から `true` に変わるか定期確認（credential vending サポート追加の兆候） |

## B. Databricks 検証

| # | 検証内容 | 優先度 | 状態 |
|---|---------|:---:|:---:|
| B-1 | Spark cluster + AWS Glue Iceberg REST: read、append、time travel | 高 | ❌ Unity Catalog によりブロック（spark.conf.set とクラスター Spark config の両方が無効; UC がカタログ登録を制御） |
| B-2 | Glue REST 経由の Lake Formation credential vending（Databricks から） | 高 | ❌ S3 Tables は Databricks で非サポート (2026-06-02 確認済み) |
| B-3 | Spark からの S3 Tables metadata table アクセス（$history、$manifests） | 中 | ❌ S3 Tables は Databricks で非サポート |
| B-4 | Unity Catalog Foreign Iceberg: S3 Tables direct REST | 高 | ❌ **非サポート** (2026-06-02): S3 Tables は Databricks で非サポート。内部プロダクトリクエスト DB-I-15824 で追跡中。 |
| B-5 | Unity Catalog Foreign Iceberg: Glue Iceberg REST | 高 | ❌ **非サポート** (2026-06-02): Iceberg REST カタログ用の UC connection type は現時点で存在しない。Glue foreign catalog サポートは Glue catalog/metastore API 経由のみ。 |
| B-6 | Databricks SQL Warehouse: CREATE CONNECTION TYPE iceberg_rest | 低 | 制限確認済み (2026-05-31) |
| B-7 | 外部 Iceberg REST アクセスの UC 監査ログ | 低 | ✅ 確認済み (2026-06-01) |
| B-8 | S3 Access Point 経由の Delta Sharing（session policy bypass） | 低 | ❌ 非対応確認済み (2026-06-01)。Sharing server は同じ UC storage credentials を使用。 |
| B-9 | NFS マウントパスを UC External Volume として登録 | 低 | ❌ 非対応確認済み (2026-06-01)。クラウドストレージ URI のみ。EFS/NFS 用の内部 AHA あり。 |

## C. Snowflake 検証

| # | 検証内容 | 優先度 | 状態 |
|---|---------|:---:|:---:|
| C-1 | CATALOG INTEGRATION (ICEBERG_REST + AWS_GLUE + VENDED_CREDENTIALS): credential vending | 高 | ✅ **完全動作** (2026-06-05): 明示的 `ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS` + デフォルト EXTERNAL_VOLUME なしのスキーマ + CREATE TABLE に EXTERNAL_VOLUME 未指定。以前の失敗はデフォルトモード (EXTERNAL_VOLUME_CREDENTIALS) が ListObjectsV2 を発行していたため。AWS前提条件: `register-resource --with-federation`。 |
| C-2 | CREATE ICEBERG TABLE + SELECT クエリ | 高 | ✅ **検証済み** (2026-06-05): CREATE 成功 (5.9s)、SELECT * LIMIT 5 成功 (1.6s)、5行返却。Query ID: 01c4e515-0003-ee3c-0003-6a86002d62b2 |
| C-3 | AUTO_REFRESH 動作（Iceberg スナップショット検出） | 中 | ✅ **完全検証済み** (2026-06-08): AUTO_REFRESH 有効化 (131ms)。**実動作テスト**: PyIceberg で 1レコード追加 → Snowflake COUNT(*) が 170→171 に 30秒以内で自動反映。Time Travel も検証: AT(OFFSET => -1200) で 170 (過去スナップショット) を取得。 |
| C-4 | Snowflake Open Catalog / Polaris を代替カタログとして | 中 | TBD |
| C-5 | Cortex Search 用に Snowflake マネージドテーブルへメタデータ同期 | 中 | TBD |
| C-6 | 同期メタデータに対する Horizon ガバナンス（Row Access Policy） | 低 | TBD |
| C-7 | Object Store catalog integration（メタデータファイル直接読み取り） | 高 | ❌ **Access Denied** (2026-06-02): AssumeRole は成功するが、Snowflake のアクセスパターン（ListBucket 含む）が S3 Tables 内部バケットの制限によりブロックされる。メタデータを標準 S3 バケットにエクスポートする必要あり。 |
| C-10 | Glue REST + EXTERNAL_VOLUME_CREDENTIALS | 高 | ❌ **根本原因特定** (2026-06-05): EXTERNAL_VOLUME_CREDENTIALS はデフォルトモード。ListObjectsV2 を発行し S3 Tables に拒否される。**解決策**: 明示的 `ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS` を使用（動作確認済み）。 |
| C-8 | TO_FILE の文字列リテラル構文で S3 AP ステージ再テスト | 中 | ✅ **成功** (2026-06-02): 文字列リテラル構文 + 正しいファイルパスで TO_FILE が S3 AP ステージから正常動作。問題は (1) 構文エラー (2) 存在しないファイルパスの2点だった。S3 AP 固有の制限ではない。 |
| C-9 | SYSTEM$VERIFY_CATALOG_INTEGRATION('S3TABLES_GLUE_REST_INT') | 中 | ✅ 正常 (2026-06-02): "Statement executed successfully" — 接続確認済み |
| C-11 | ETL S3 Tables → 標準 Glue Iceberg → Snowflake VENDED_CREDENTIALS | 中 | ❌ **根本原因判明** (2026-06-03): Glue Iceberg REST エンドポイントは `s3tablescatalog` フェデレーテッドカタログの loadTable のみサポート。標準 Glue Data Catalog テーブルは admin 権限でも 403 を返す。権限の問題ではなくサービススコープの制限。ETL で標準 Glue に書き出しても Glue Iceberg REST 経由の Snowflake アクセスは解決しない。 |

## D. ONTAP / FSx 検証

| # | 検証内容 | 優先度 | 状態 |
|---|---------|:---:|:---:|
| D-1 | S3 AP アイデンティティマトリクス: UNIX vs Windows vs mixed security style | 高 | TBD |
| D-2 | バックフィルの NFS/SMB レイテンシへの影響（同時アクセス） | 高 | TBD |
| D-3 | コールドファイルエンリッチメント時のキャパシティプール読み取り活動 | 中 | TBD |
| D-4 | 10 万ファイル以上での S3 AP ListObjectsV2 ページネーション | 中 | ✅ 検証済み (ページネーション動作確認、~275ms/ページ) |
| D-5 | FPolicy イベント設計: create/modify/rename/delete のみ | 中 | 設計文書化済み |
| D-6 | FPolicy スループット影響の測定 | 中 | TBD |
| D-7 | SnapMirror DR フェイルオーバー + カタログリバインドテスト | 低 | 設計文書化済み |

## E. ガバナンス / セキュリティ検証

| # | 検証内容 | 優先度 | 状態 |
|---|---------|:---:|:---:|
| E-1 | Lake Formation カラムレベル: 代替登録パス | 高 | ❌ **VENDED_CREDENTIALS では非サポート** (2026-06-08): `AllowFullTableExternalDataAccess=false` にすると、明示的な column/table-level grant や ExternalDataFilteringAllowList 設定に関わらず VENDED_CREDENTIALS パスが完全ブロックされる。カラムレベルガバナンスは Snowflake Horizon (Row Access Policy / Column Masking) または別 Iceberg テーブルで実装する必要あり。 |
| E-2 | LF-Tags 分類体系のデプロイとテスト | 中 | ✅ 検証済み (タグ作成、割り当て、グラント成功) |
| E-3 | データペリメーター: VPC エンドポイント + SCP 適用 | 中 | パターン文書化済み |
| E-4 | Bedrock プライベート接続（VPC エンドポイント） | 中 | パターン文書化済み |
| E-5 | マルチアカウントデプロイ（プラットフォーム / セキュリティ / ワークロード分離） | 低 | TBD |

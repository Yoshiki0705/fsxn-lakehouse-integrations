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

## B. Databricks 検証

| # | 検証内容 | 優先度 | 状態 |
|---|---------|:---:|:---:|
| B-1 | Spark cluster + AWS Glue Iceberg REST: read、append、time travel | 高 | ❌ Unity Catalog によりブロック（spark.conf.set とクラスター Spark config の両方が無効; UC がカタログ登録を制御） |
| B-2 | Glue REST 経由の Lake Formation credential vending（Databricks から） | 高 | TBD |
| B-3 | Spark からの S3 Tables metadata table アクセス（$history、$manifests） | 中 | TBD |
| B-4 | Unity Catalog Foreign Iceberg: S3 Tables direct REST | 高 | Databricks サポートにフォローアップ送信済み (2026-06-01) |
| B-5 | Unity Catalog Foreign Iceberg: Glue Iceberg REST | 高 | Databricks サポートにフォローアップ送信済み (2026-06-01) |
| B-6 | Databricks SQL Warehouse: CREATE CONNECTION TYPE iceberg_rest | 低 | 制限確認済み (2026-05-31) |
| B-7 | 外部 Iceberg REST アクセスの UC 監査ログ | 低 | ✅ 確認済み (2026-06-01) |
| B-8 | S3 Access Point 経由の Delta Sharing（session policy bypass） | 低 | ❌ 非対応確認済み (2026-06-01)。Sharing server は同じ UC storage credentials を使用。 |
| B-9 | NFS マウントパスを UC External Volume として登録 | 低 | ❌ 非対応確認済み (2026-06-01)。クラウドストレージ URI のみ。EFS/NFS 用の内部 AHA あり。 |

## C. Snowflake 検証

| # | 検証内容 | 優先度 | 状態 |
|---|---------|:---:|:---:|
| C-1 | CATALOG INTEGRATION (ICEBERG_REST + AWS_GLUE + VENDED_CREDENTIALS): credential vending | 高 | ❌ **非互換確定** (2026-06-02): Snowflake サポートが loadTable レスポンスに s3.access-key-id/secret/token が必須と確認。Glue REST はこれらを返さない。Snowflake 側の既知の問題なし — AWS Glue REST が credential を提供しないことが原因。 |
| C-2 | CREATE ICEBERG TABLE + SELECT クエリ | 高 | ❌ C-1 でブロック（Snowflake サポートと我々の loadTable 証拠で確認済み） |
| C-3 | AUTO_REFRESH 動作（Iceberg スナップショット検出） | 中 | ❌ C-1 でブロック |
| C-4 | Snowflake Open Catalog / Polaris を代替カタログとして | 中 | TBD |
| C-5 | Cortex Search 用に Snowflake マネージドテーブルへメタデータ同期 | 中 | TBD |
| C-6 | 同期メタデータに対する Horizon ガバナンス（Row Access Policy） | 低 | TBD |
| C-7 | Object Store catalog integration（メタデータファイル直接読み取り） | 高 | ❌ **Access Denied** (2026-06-02): AssumeRole は成功するが、Snowflake のアクセスパターン（ListBucket 含む）が S3 Tables 内部バケットの制限によりブロックされる。メタデータを標準 S3 バケットにエクスポートする必要あり。 |
| C-10 | Glue REST + EXTERNAL_VOLUME_CREDENTIALS | 高 | ❌ **Access Denied** (2026-06-02): サポート推奨のテスト実施。同じ S3 Tables 内部バケット制限でブロック。credential vending モードに関係なく、S3 Tables 内部バケット自体がブロッカーと確定。 |
| C-8 | TO_FILE の文字列リテラル構文で S3 AP ステージ再テスト | 中 | ✅ **成功** (2026-06-02): 文字列リテラル構文 + 正しいファイルパスで TO_FILE が S3 AP ステージから正常動作。問題は (1) 構文エラー (2) 存在しないファイルパスの2点だった。S3 AP 固有の制限ではない。 |
| C-9 | SYSTEM$VERIFY_CATALOG_INTEGRATION('S3TABLES_GLUE_REST_INT') | 中 | 未実行 |

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
| E-1 | Lake Formation カラムレベル: 代替登録パス | 高 | TBD |
| E-2 | LF-Tags 分類体系のデプロイとテスト | 中 | ✅ 検証済み (タグ作成、割り当て、グラント成功) |
| E-3 | データペリメーター: VPC エンドポイント + SCP 適用 | 中 | パターン文書化済み |
| E-4 | Bedrock プライベート接続（VPC エンドポイント） | 中 | パターン文書化済み |
| E-5 | マルチアカウントデプロイ（プラットフォーム / セキュリティ / ワークロード分離） | 低 | TBD |

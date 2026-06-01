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
| A-4 | S3 Tables direct REST vs Glue Iceberg REST: PyIceberg、Spark、Athena、Lake Formation | 中 | ✅ 検証済み (Athena + PyIceberg) |

## B. Databricks 検証

| # | 検証内容 | 優先度 | 状態 |
|---|---------|:---:|:---:|
| B-1 | Spark cluster + AWS Glue Iceberg REST: read、append、time travel | 高 | TBD |
| B-2 | Glue REST 経由の Lake Formation credential vending（Databricks から） | 高 | TBD |
| B-3 | Spark からの S3 Tables metadata table アクセス（$history、$manifests） | 中 | TBD |
| B-4 | Unity Catalog Foreign Iceberg: S3 Tables direct REST | 中 | TBD |
| B-5 | Unity Catalog Foreign Iceberg: Glue Iceberg REST | 中 | TBD |
| B-6 | Databricks SQL Warehouse: CREATE CONNECTION TYPE iceberg_rest | 低 | 制限確認済み (2026-05-31) |
| B-7 | 外部 Iceberg REST アクセスの UC 監査ログ | 低 | ✅ 確認済み (2026-06-01) |

## C. Snowflake 検証

| # | 検証内容 | 優先度 | 状態 |
|---|---------|:---:|:---:|
| C-1 | CATALOG INTEGRATION (ICEBERG_REST + AWS_GLUE + VENDED_CREDENTIALS): credential vending | 高 | 🔄 進行中（サポートケース対応中） |
| C-2 | CREATE ICEBERG TABLE + SELECT クエリ | 高 | C-1 でブロック |
| C-3 | AUTO_REFRESH 動作（Iceberg スナップショット検出） | 中 | C-1 でブロック |
| C-4 | Snowflake Open Catalog / Polaris を代替カタログとして | 中 | TBD |
| C-5 | Cortex Search 用に Snowflake マネージドテーブルへメタデータ同期 | 中 | TBD |
| C-6 | 同期メタデータに対する Horizon ガバナンス（Row Access Policy） | 低 | TBD |

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

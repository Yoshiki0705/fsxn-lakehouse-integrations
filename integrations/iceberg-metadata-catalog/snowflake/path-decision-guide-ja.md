# Snowflake 統合パス判断ガイド

🌐 日本語 | [English](path-decision-guide.md)

## 目的

Snowflake ユーザーとパートナーが、FSx for ONTAP メタデータカタログへの Snowflake からのアクセスに適切な統合パスを選択できるようにする。

## パス判断

| 要件 | 推奨パス | ステータス |
|---|---|---|
| Snowflake ダッシュボードのみ | 匿名化メタデータを Snowflake テーブルに同期 | ✅ 今すぐ利用可能 |
| Cortex Search / Intelligence | サマリー + 匿名化メタデータを同期 | ✅ 今すぐ利用可能 |
| ゼロコピー Iceberg クエリ | Glue REST + vended credentials を検証 | 🔄 進行中 |
| Snowflake ファースト Iceberg ガバナンス | Open Catalog / Polaris | 戦略的代替案 |
| Snowflake での生ファイル処理 | External stage (FSx S3 AP) | ✅ 検証済み（TO_FILE + Cortex AI 含む） |
| クロスプラットフォーム Iceberg 相互運用 | Glue REST + vended credentials | 🔄 進行中 |

## ガバナンスポリシーマッピング

メタデータを Snowflake に同期する場合、AWS ガバナンスフィールドを Snowflake オブジェクトにマッピング:

| AWS メタデータフィールド | Snowflake ガバナンスオブジェクト | 目的 |
|---|---|---|
| `sensitivity_level` | タグ + マスキングポリシー | 機密度によるカラム可視性制御 |
| `tenant_id` | Row Access Policy | テナントによる行制限 |
| `has_pii` | タグ + マスキングポリシー | PII 含有フィールドのマスク |
| `path_classification` | Row Access Policy または制限ビュー | パス可視性の制御 |
| `raw_path` | 制限テーブルのみ（一般ビューには同期しない） | パス露出の防止 |

## メタデータ同期パターン

### 同期対象

```sql
-- キュレートされた最新レコードビューを同期（append-only ベーステーブルではない）
-- AWS 側から（PyIceberg または Athena エクスポート）:
SELECT file_id, file_name, file_type, classification, confidence_score,
       summary, sensitivity_level, tenant_id, has_pii, pii_status,
       path_classification, scan_run_id, change_type, is_deleted,
       created_at, modified_at
FROM latest_records_view
WHERE is_deleted = false;
-- 同期しない: raw_path, embedding_vector, anonymized_path（必要でない限り）
```

### 同期頻度

| パターン | 頻度 | 最適な用途 |
|---|---|---|
| スケジュールタスク | 毎時 / 毎日 | 低頻度ダッシュボード |
| イベント駆動 (SNS → Snowpipe) | ほぼリアルタイム | アクティブな発見ユースケース |
| 手動リフレッシュ | オンデマンド | 開発 / テスト |

### 冪等性

`MERGE INTO` を `file_id` をマージキーとして使用し、再同期時の重複を防止:

```sql
MERGE INTO metadata_catalog t
USING staged_metadata s
ON t.file_id = s.file_id
WHEN MATCHED AND s.modified_at > t.modified_at THEN UPDATE SET ...
WHEN NOT MATCHED THEN INSERT ...;
```

## Snowflake コストモデル

| コンポーネント | ドライバー | 見積もり |
|---|---|---|
| Warehouse コンピュート（同期ジョブ） | X-SMALL、毎時 | ~$2-5/月 |
| Warehouse コンピュート（ダッシュボード） | X-SMALL、オンデマンド | ~$5-15/月 |
| Cortex Search サービス | クエリ単位 + インデックスリフレッシュ | ~$10-30/月 |
| ストレージ（同期メタデータ） | 10万ファイルで ~1 GB | ~$0.02/月 |
| Tasks / Streams | 実行頻度 | ~$1-3/月 |
| **合計（メタデータアクティベーション）** | | **~$20-55/月** |

> 生ファイルのコピーは不要。キュレートされたメタデータ（~MB スケール）のみが同期されます。

## 参考資料

- [Snowflake: Cortex Search 概要](https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-search/cortex-search-overview)
- [Snowflake: Iceberg REST catalog integration](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-rest)
- [Snowflake: Vended credentials](https://docs.snowflake.com/en/user-guide/tables-iceberg-configure-catalog-integration-vended-credentials)
- [トラブルシューティングガイド](troubleshooting-guide-ja.md) | [Troubleshooting Guide (EN)](troubleshooting-guide.md)
- [Glue REST 検証](glue-rest-vended-credentials-validation-ja.md)
- [External Stage 検証](external-stage-fsx-s3ap-validation-ja.md)

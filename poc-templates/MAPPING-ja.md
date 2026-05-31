🌐 [English](MAPPING.md) | **日本語**

# PoC テンプレート ↔ ドキュメントマッピング

## 目的

各 PoC テンプレートモジュールと、このリポジトリ内の詳細ドキュメント、デモガイド、ブログ記事、検証エビデンスの対応関係を示します。

---

## モジュール → ドキュメントマップ

| PoC モジュール | 詳細ガイド | デモガイド | ブログ記事 | 検証エビデンス |
|---|---|---|---|---|
| **02-athena-quickstart** | [Athena README](../integrations/athena/README.md) | — | [Part 1: NAS データをその場でクエリ](https://dev.to/aws-builders/query-nas-data-in-place-with-athena-and-fsx-for-ontap-s3-access-points-3lhh) | [verification-pack/athena-parquet-read/](../verification-pack/athena-parquet-read/) |
| **03-snowflake-integration** | [Snowflake README](../integrations/snowflake/README.md) | [AI デモガイド](../integrations/snowflake/docs/ja/ai-demo-guide.md) | [Part 3: Access Denied から動作する External Table へ](https://dev.to/aws-builders/snowflake-and-fsx-for-ontap-s3-access-points-from-access-denied-to-working-external-tables-9k8) | [verification-pack/snowflake/](../verification-pack/snowflake/) |
| **04-databricks-integration** | [Databricks README](../integrations/databricks/README.md) | [AI デモガイド](../integrations/databricks/docs/ja/ai-demo-guide.md) | [Part 2: レイヤーごとの検証](https://dev.to/aws-builders/databricks-and-fsx-for-ontap-s3-access-points-a-layer-by-layer-validation-of-observed-boundaries-p4d) | [verification-pack/databricks/](../verification-pack/databricks/) |
| **05-emr-spark-etl** | [EMR Spark README](../integrations/emr-spark/README.md) | — | [Part 5: 読み書き ETL](https://dev.to/aws-builders/read-write-etl-on-nas-data-with-emr-serverless-spark-no-cluster-no-copy-hgm) | [verification-pack/emr-spark/](../verification-pack/emr-spark/) |
| **06-duckdb-lambda** | [DuckDB README](../integrations/duckdb/README.md) | — | [Part 4: $0.00001/クエリ](https://dev.to/aws-builders/serverless-analytics-on-nas-data-for-000001query-duckdb-lambda-x-fsx-for-ontap-2o5o) | [verification-pack/duckdb-local/](../verification-pack/duckdb-local/) |
| **07-governance** | [ガバナンスガイド](../docs/ja/governance-and-compliance.md) | — | [Part 6: エンタープライズガバナンス](https://dev.to/aws-builders/redshift-spectrum-lake-formation-enterprise-governance-on-nas-data-2pik) | [verification-pack/redshift-spectrum/](../verification-pack/redshift-spectrum/) |

---

## 横断ドキュメント

| トピック | ドキュメント | PoC との関連 |
|---------|-----------|------------|
| 互換性マトリクス | [docs/ja/compatibility-matrix.md](../docs/ja/compatibility-matrix.md) | どのエンジンでどの操作が動作するか |
| ベンダー比較 | [docs/ja/vendor-comparison.md](../docs/ja/vendor-comparison.md) | エンジン選択ガイダンス |
| パートナーオファリング | [docs/ja/partner-offering.md](../docs/ja/partner-offering.md) | 営業ポジショニングとアンチパターン |
| DataSync ガイド | [docs/ja/datasync-to-s3-guide.md](../docs/ja/datasync-to-s3-guide.md) | モジュール 04 (Databricks) 同期メカニズム |
| 非構造化データ | [docs/ja/unstructured-data-access.md](../docs/ja/unstructured-data-access.md) | 画像/PDF/動画アクセスパターン |
| リージョン設計 | [docs/ja/region-design-guide.md](../docs/ja/region-design-guide.md) | 同一リージョン要件 |
| ネットワーキング | [docs/en/fsxn-s3ap-networking.md](../docs/en/fsxn-s3ap-networking.md) | VPC/Internet origin、DNS/AD 問題 |
| リカバリセマンティクス | [docs/ja/recovery-semantics.md](../docs/ja/recovery-semantics.md) | Snapshot + テーブルフォーマットリカバリ |
| ゼロコピー非構造化データガバナンス | [docs/ja/zero-copy-media-governance.md](../docs/ja/zero-copy-media-governance.md) | S3 重複排除 + マルチプラットフォーム活用 + FlexCache S3 AP ロードマップ |
| Iceberg メタデータカタログ | [docs/ja/iceberg-metadata-catalog.md](../docs/ja/iceberg-metadata-catalog.md) | S3 Tables + FSx for ONTAP による非構造化データメタデータ管理 |
| KPI と PoC 検証 | [docs/ja/kpi-and-validation.md](../docs/ja/kpi-and-validation.md) | PoC 成功基準と検証メトリクス |

---

## スクリプト → ソースマッピング

| PoC スクリプト | 完全実装 | 備考 |
|---|---|---|
| `06-duckdb-lambda/handler.py` | [integrations/duckdb/lambda/handler.py](../integrations/duckdb/lambda/handler.py) | PoC 版は簡略化; 完全版はメトリクス、エラーハンドリング付き |
| `06-duckdb-lambda/template.yaml` | [integrations/duckdb/template.yaml](../integrations/duckdb/template.yaml) | PoC 版は最小限; 完全版は全パラメータ付き |
| `05-emr-spark-etl/spark-job.py` | — (PoC 固有) | ブログ Part 5 検証スクリプトに基づく |
| `04-databricks-integration/datasync-task.yaml` | — (PoC 固有) | [DataSync ガイド](../docs/ja/datasync-to-s3-guide.md)に基づく |
| `07-governance/lakeformation-setup.sh` | — (PoC 固有) | ブログ Part 6 検証に基づく |

---

## エビデンス記録フォーマット

PoC モジュール実行後、[verification-pack/](../verification-pack/) と同じ形式でエビデンスを記録:

```yaml
verification_id: poc-<顧客名>-<エンジン>-<日付>
date: "YYYY-MM-DD"
engineer: <名前>
platform: <エンジン>
results:
  read_test:
    status: SUCCESS/FAILED
    duration_ms: <値>
    rows: <件数>
  write_test:
    status: SUCCESS/FAILED/NOT_TESTED
  governance_test:
    status: SUCCESS/FAILED/NOT_TESTED
conclusion: |
  <所見のサマリー>
```

---

## 再現ガイド: PoC セットアップ → デモ実行

### デモガイドのデモを再現する方法

デモガイド（`integrations/*/docs/` 内）は設定済み環境を前提としています。PoC テンプレートがそのセットアップを提供します。

#### Snowflake AI デモガイドの再現

| Step | 実行内容 | 場所 |
|:---:|---|---|
| 1 | サンプルデータ生成 | `poc-templates/sample-data/generate-sensor-data.py` |
| 2 | FSx S3 AP にアップロード | `aws s3 cp sensor_data.parquet s3://<AP_ALIAS>/sensor-data/` |
| 3 | Storage Integration 作成 | `poc-templates/03-snowflake-integration/01-storage-integration.sql` |
| 4 | IAM trust policy 更新 | `03-snowflake-integration/README-ja.md` の Step 2 参照 |
| 5 | Stage + External Table 作成 | `poc-templates/03-snowflake-integration/02-stage-and-table.sql` |
| 6 | **AI デモ実行** | `poc-templates/03-snowflake-integration/03-cortex-ai-demo.sql` または [AI デモガイド](../integrations/snowflake/docs/ja/ai-demo-guide.md) |

**オブジェクト名の対応**（PoC テンプレート → デモガイド）:
- `@fsxn_poc_stage` → `@fsxn_stage`
- `fsxn_poc_sensor_ext` → `fsxn_sensor_ext_table`
- `fsxn_poc_integration` → `fsxn_verification_integration`

> **ヒント**: 最初からデモガイドと同じ名前を使用すれば、後でリネーム不要。

#### Athena デモの再現

| Step | 実行内容 | 場所 |
|:---:|---|---|
| 1 | S3 AP 接続確認 | `poc-templates/scripts/validate.sh --ap-alias <ALIAS>` |
| 2 | サンプルデータ生成 + アップロード | `generate-sensor-data.py` + `aws s3 cp` |
| 3 | Glue テーブル作成 | `poc-templates/02-athena-quickstart/sample-queries.sql` (Steps 1-2) |
| 4 | **クエリ実行** | `poc-templates/02-athena-quickstart/sample-queries.sql` (Steps 3-7) |
| 5 | ガバナンス追加 | `poc-templates/07-governance/lakeformation-setup.sh` |

#### EMR Spark デモの再現

| Step | 実行内容 | 場所 |
|:---:|---|---|
| 1 | サンプルデータを FSx S3 AP にアップロード | Athena Step 2 と同じ |
| 2 | spark-job.py を通常の S3 にアップロード | `aws s3 cp poc-templates/05-emr-spark-etl/spark-job.py s3://<BUCKET>/scripts/` |
| 3 | EMR Serverless アプリ作成 | `poc-templates/05-emr-spark-etl/README-ja.md` 参照 |
| 4 | **ジョブ送信** | `aws emr-serverless start-job-run ...` |
| 5 | 書き戻し確認 | `aws s3api list-objects-v2 --bucket <AP_ALIAS> --prefix gold/` |

#### DuckDB Lambda デモの再現

| Step | 実行内容 | 場所 |
|:---:|---|---|
| 1 | Lambda レイヤービルド | `poc-templates/06-duckdb-lambda/README-ja.md` Step 1 |
| 2 | CloudFormation デプロイ | `poc-templates/06-duckdb-lambda/template.yaml` |
| 3 | **Lambda 呼び出し** | `aws lambda invoke --function-name fsxn-duckdb-query --payload '{"query":"..."}' response.json` |

> **本番実装リファレンス**: メトリクスとエラーハンドリング付きの本番グレードハンドラーは [integrations/duckdb/lambda/handler.py](../integrations/duckdb/lambda/handler.py) を参照

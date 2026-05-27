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

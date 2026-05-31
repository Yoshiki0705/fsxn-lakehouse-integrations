# クロスプラットフォームアクセス設定

🌐 日本語 | [English](README.md)

## 概要

本ディレクトリには、Iceberg メタデータカタログに複数の分析エンジンからアクセスするためのプラットフォーム別設定を格納する。全プラットフォームが Iceberg REST endpoint または Glue Catalog 統合を通じて**同一のメタデータ**にアクセスする。

## プラットフォーム別アクセスパス

```
                    S3 Tables (Iceberg メタデータ)
                              │
              ┌───────────────┼───────────────┐
              │               │               │
    Iceberg REST        Glue Catalog    Snowflake Managed
    endpoint            (SageMaker      Iceberg (コピー)
              │         Lakehouse)            │
              │               │               │
    ┌─────────┤         ┌─────┤         ┌─────┤
    │         │         │     │         │     │
Databricks  EMR     Athena  Redshift  Snowflake  外部
(External   Spark   SQL     Spectrum  (Cortex    エンジン
 Catalog)                             Search)    (Horizon経由)
```

## クイックリファレンス

| プラットフォーム | アクセス方式 | ガバナンス | 設定ファイル |
|---------------|-----------|----------|-----------|
| **Athena** | Glue Catalog (SageMaker Lakehouse) | Lake Formation LF-Tags | `athena-emr/athena-queries.sql` |
| **EMR Spark** | Iceberg REST endpoint (直接) | Lake Formation | `athena-emr/emr-spark-access.py` |
| **Databricks** | External Catalog (Iceberg REST) | Unity Catalog + Lake Formation | `databricks/external-catalog-setup.py` |
| **Snowflake** | Managed Iceberg Table (コピー) | Horizon Row Access Policy | `snowflake/managed-iceberg-setup.sql` |
| **Redshift Spectrum** | Glue Catalog | Lake Formation | Athena と同様 |

## ガバナンス適用マトリクス

| クエリエンジン | Lake Formation | Horizon Catalog | Unity Catalog |
|-------------|:-:|:-:|:-:|
| Athena | ✅ 適用 | — | — |
| EMR Spark | ✅ 適用 | — | — |
| Redshift Spectrum | ✅ 適用 | — | — |
| Databricks (External Catalog 経由) | ✅ 適用 | — | ✅ 補完 |
| Snowflake (内部) | — | ✅ 適用 | — |
| 外部エンジン (Horizon REST 経由) | — | ✅ 適用 | — |

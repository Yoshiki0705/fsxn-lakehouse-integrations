# 未検証項目インベントリ

🌐 [English](../en/unverified-inventory.md) | **日本語**

> 2026-08-06 時点。本リポジトリの主張のうち、実行記録に裏付けられて**いない**ものと、その阻害要因の一覧です。

抜けを数えられる状態にすることが目的です。[互換性マトリクス](./compatibility-matrix.md) で ⚠️ または 🔲 が付いた主張は、本ページに現れるはずです。現れていなければ、マトリクスが先行しており本ページが不正確ということになります。

動作**しない**ことが判明している事項は [ブロッカートラッカー](./blocker-tracker.md) が扱います。本ページの対象は「壊れているもの」ではなく「未知のもの」です。

**合計 27 件。**

## サマリ

| 阻害要因 | 件数 | 内容 |
|---|:---:|---|
| 現在実行可能。未実施のみ | 12 | 本プロジェクトで既に使用している AWS サービスのみで完結します。次の現実的な候補です。 |
| Snowflake セッションが必要 | 6 | 認証情報は本リポジトリに保持していません。サインインすれば一度の作業で実行可能です。 |
| Databricks ワークスペースが必要 | 3 | 2026 年 5 月に使用したワークスペースは削除済みです。なお Unity Catalog 経路は BLK-001 により、いずれにせよブロックされます。 |
| 別エンジンのデプロイが必要 | 3 | ClickHouse インスタンスは稼働していません。 |
| アカウントティアまたはコストによる制約 | 1 | 有償ティアまたは課金リソースが必要です。 |
| 経過時間による制約 | 1 | 短縮できません。 |
| 検証不可 | 1 | 未リリースの要素に依存します。 |

## 現在実行可能。未実施のみ

本プロジェクトで既に使用している AWS サービスのみで完結します。次の現実的な候補です。

| ID | 対象 | 未検証の主張 | 必要なもの |
|---|---|---|---|
| UNV-012 | Databricks | No automated tests exist for the integration (`integrations/databricks/tests/` holds only `.gitkeep`) | Test authoring. Snowflake has 8 test files; Databricks has none. |
| UNV-016 | EMR Serverless | Iceberg write commit | An EMR Serverless run. Recorded as failing with a NullPointerException in S3FileIO; the failure is noted but no evidence record exists. |
| UNV-017 | AWS Glue ETL | Delta Lake write commit protocol | A Glue job run. Expected to fail for the same reason Delta fails elsewhere. |
| UNV-018 | AWS Glue ETL | Iceberg write with concurrent writers | Two simultaneous Glue jobs against one table. |
| UNV-019 | AWS Glue ETL / EMR Spark | Iceberg REST Catalog against S3 Tables | A job configured with the REST catalog. Inferred from the PyIceberg result. |
| UNV-020 | Redshift Spectrum | Glue federated catalog path to S3 Tables | A Redshift Serverless workgroup and a federated catalog. The plain Glue-table path over the AP is verified (2026-05-23). |
| UNV-021 | Athena | Iceberg at realistic table size — manifest growth, compaction cost, partition evolution | A larger dataset. The 2026-08-06 run used a single-digit row count. |
| UNV-022 | Athena | Concurrency above 25, and working sets larger than the ONTAP cache | A dataset well beyond cache size and a higher concurrency sweep. The 2026-08-06 run was cache-resident. |
| UNV-023 | Hudi | Any operation on an FSx for ONTAP S3 AP | A Hudi-capable engine. Listed under BLK-002 but never tested. |
| UNV-025 | FSx for ONTAP | ListObjectsV2 latency above 5,000 objects | A larger object population. The 2026-08-05 measurement covered 10 to 5,000 objects. |
| UNV-026 | Bedrock | Whether the Managed Knowledge Base S3 connector accepts an S3 AP URI (the traditional Knowledge Base path is verified) | A Managed Knowledge Base run. |
| UNV-027 | Tooling | PyIceberg wheel on macOS Apple Silicon | A run on that platform. A wheel exists; this project has not exercised it. |

## Snowflake セッションが必要

認証情報は本リポジトリに保持していません。サインインすれば一度の作業で実行可能です。

| ID | 対象 | 未検証の主張 | 必要なもの |
|---|---|---|---|
| UNV-001 | Snowflake | Managed Iceberg Table write end to end (COPY INTO from an AP-backed stage into a Managed Iceberg Table on customer S3) | A Snowflake session. The External Volume creation and the COPY INTO into a standard table are already recorded; the Managed Iceberg leg is not. |
| UNV-002 | Snowflake | Dynamic Table with an AP-backed stage as source (FULL refresh, minimum 60 s TARGET_LAG) | A Snowflake session plus one refresh cycle. |
| UNV-004 | Snowflake | Horizon Catalog governance (row access policies, masking) enforced on external engines reading the Iceberg table | A Snowflake session and a second engine configured against the Horizon catalog. |
| UNV-005 | Snowflake | Snowpark file access (`SnowflakeFile.open`) against an AP-backed stage | A Snowflake session with Snowpark enabled. |
| UNV-006 | Snowflake | COPY INTO unload (write back to the FSx for ONTAP S3 AP) | A Snowflake session. Expected to fail — external stages are read-only by design — but the failure mode is not recorded. |
| UNV-008 | Snowflake | Read of JSON, Avro and ORC from an AP-backed stage (Parquet and CSV are verified) | A Snowflake session and sample files in each format. |

## Databricks ワークスペースが必要

2026 年 5 月に使用したワークスペースは削除済みです。なお Unity Catalog 経路は BLK-001 により、いずれにせよブロックされます。

| ID | 対象 | 未検証の主張 | 必要なもの |
|---|---|---|---|
| UNV-009 | Databricks | Iceberg REST Catalog from a Databricks Spark cluster (`spark.sql.catalog.s3tables`) | A Databricks workspace with a Spark cluster. Inferred from the EMR mechanism; no run. |
| UNV-010 | Databricks | Executor-scale boto3 access from a customer-managed VPC | A customer-managed-VPC workspace. The Databricks-managed VPC case is recorded as failing (egress to FSx blocked); the customer-VPC case is untested. |
| UNV-011 | Databricks | 9 of the 11 cases in `verification-pack/databricks/test-cases.yaml` have no recorded run | A workspace matching each case's preconditions. |

## 別エンジンのデプロイが必要

ClickHouse インスタンスは稼働していません。

| ID | 対象 | 未検証の主張 | 必要なもの |
|---|---|---|---|
| UNV-013 | ClickHouse | `s3()` table function reading Parquet directly from an FSx for ONTAP S3 AP | A ClickHouse instance with IAM credentials. |
| UNV-014 | ClickHouse | `iceberg()` table function plus Glue Catalog integration | ClickHouse 23.8+ and a Glue-catalogued Iceberg table. |
| UNV-015 | ClickHouse | S3Queue engine ingesting from a standard S3 bucket fed by DataSync | A ClickHouse instance. Direct S3Queue against the AP is blocked by BLK-003 (no event notifications). |

## アカウントティアまたはコストによる制約

有償ティアまたは課金リソースが必要です。

| ID | 対象 | 未検証の主張 | 必要なもの |
|---|---|---|---|
| UNV-007 | Snowflake | PrivateLink connectivity to an AP-backed stage | A Snowflake Business Critical account or higher, plus PrivateLink setup. |

## 経過時間による制約

短縮できません。

| ID | 対象 | 未検証の主張 | 必要なもの |
|---|---|---|---|
| UNV-003 | Snowflake | COPY INTO 64-day load-history deduplication | A Snowflake session and 64 days of elapsed time. Cannot be shortened; the window is a Snowflake-side retention period. |

## 検証不可

未リリースの要素に依存します。

| ID | 対象 | 未検証の主張 | 必要なもの |
|---|---|---|---|
| UNV-024 | FSx for ONTAP | Behaviour on ONTAP 9.18.1 and later | The release. Cannot be verified today. |

## 直近でクローズした項目

本一覧に載っていたもののうち、実測が完了したものです。

| 対象 | 主張 | 結果 | エビデンス |
|---|---|---|---|
| Athena | FSx for ONTAP S3 AP 上の Iceberg 読み取り**および書き込み** | 検証済み — UPDATE、DELETE、タイムトラベル、OPTIMIZE、VACUUM、2 件の同時コミットを含むライフサイクル全体 | [2026-08-06](../../verification-pack/athena-iceberg/evidence/2026-08-06/evidence-record.yaml) |
| Athena | 高同時実行スキャン（10-50 アナリスト） | 25 並列まで検証。25/25 成功、全カラムスキャンで約 2 倍に劣化、キュー時間は 200 ms 未満。データセットはキャッシュに収まる規模 | [2026-08-06](../../verification-pack/athena-concurrency/evidence/2026-08-06/evidence-record.yaml) |
| Snowflake | 合成した S3 通知で Snowpipe COPY が発火するか | 検証済み — publish から約 0.5 秒で取り込み | [2026-08-06](../../verification-pack/snowpipe-pattern-a/evidence/2026-08-06/snowflake-side-verification.yaml) |
| FSx for ONTAP | ネイティブ S3 に対する ListObjectsV2 レイテンシ | 10〜5,000 オブジェクトで 1.3〜1.4 倍として再測定。従来の 30〜80 倍は再現せず撤回 | [2026-08-05](../../verification-pack/s3ap-list-latency/evidence/2026-08-05/benchmark-result.yaml) |

## 本ページの使い方

主張が未検証から実測済みに移ったとき: エビデンスを `verification-pack/<topic>/evidence/<date>/` に記録し、マトリクスの該当行がそれを参照するよう更新し、上記の**直近でクローズした項目**へ移し、合計件数を調整してください。

検証ではなく撤回に至った場合は、その旨と理由をマトリクスに残してください。撤回も結果のひとつです。

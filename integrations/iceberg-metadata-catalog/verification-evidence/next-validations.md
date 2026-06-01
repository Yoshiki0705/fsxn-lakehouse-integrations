# Next Validations

🌐 [日本語](next-validations-ja.md) | English

## Purpose

Track remaining validation items identified through expert review. Items are grouped by platform and priority.

## A. AWS Native Path — Reproducibility

| # | Validation | Priority | Status |
|---|-----------|:---:|:---:|
| A-1 | Fresh account / fresh region reproduction (CloudFormation end-to-end) | High | TBD |
| A-2 | Minimum IAM permissions documentation | High | TBD |
| A-3 | ap-northeast-1 vs us-east-1 differences (S3 Tables, Bedrock, OpenSearch NextGen, Glue REST) | Medium | TBD |
| A-4 | S3 Tables direct REST vs Glue Iceberg REST: PyIceberg, Spark, Athena, Lake Formation | Medium | ✅ Verified (Athena + PyIceberg) |

## B. Databricks Validation

| # | Validation | Priority | Status |
|---|-----------|:---:|:---:|
| B-1 | Spark cluster + AWS Glue Iceberg REST: read, append, time travel | High | TBD |
| B-2 | Lake Formation credential vending via Glue REST from Databricks | High | TBD |
| B-3 | S3 Tables metadata table access ($history, $manifests) from Spark | Medium | TBD |
| B-4 | Unity Catalog Foreign Iceberg: S3 Tables direct REST | Medium | TBD |
| B-5 | Unity Catalog Foreign Iceberg: Glue Iceberg REST | Medium | TBD |
| B-6 | Databricks SQL Warehouse: CREATE CONNECTION TYPE iceberg_rest | Low | Observed limitation (2026-05-31) |
| B-7 | UC audit logging for external Iceberg REST access | Low | ✅ Confirmed (2026-06-01) |

## C. Snowflake Validation

| # | Validation | Priority | Status |
|---|-----------|:---:|:---:|
| C-1 | CATALOG INTEGRATION (ICEBERG_REST + AWS_GLUE + VENDED_CREDENTIALS): credential vending | High | 🔄 In progress (support case active) |
| C-2 | CREATE ICEBERG TABLE + SELECT query | High | Blocked by C-1 |
| C-3 | AUTO_REFRESH behavior (Iceberg snapshot detection) | Medium | Blocked by C-1 |
| C-4 | Snowflake Open Catalog / Polaris as alternative catalog | Medium | TBD |
| C-5 | Metadata sync to Snowflake managed table for Cortex Search | Medium | TBD |
| C-6 | Horizon governance (Row Access Policy) on synced metadata | Low | TBD |

## D. ONTAP / FSx Validation

| # | Validation | Priority | Status |
|---|-----------|:---:|:---:|
| D-1 | S3 AP identity matrix: UNIX vs Windows vs mixed security style | High | TBD |
| D-2 | Backfill impact on NFS/SMB latency (concurrent access) | High | TBD |
| D-3 | Capacity pool read activity during cold file enrichment | Medium | TBD |
| D-4 | S3 AP ListObjectsV2 pagination at 100K+ files | Medium | ✅ Verified (pagination works, ~275ms/page) |
| D-5 | FPolicy event design: create/modify/rename/delete only | Medium | Design documented |
| D-6 | FPolicy throughput impact measurement | Medium | TBD |
| D-7 | SnapMirror DR failover + catalog rebinding test | Low | Design documented |

## E. Governance / Security Validation

| # | Validation | Priority | Status |
|---|-----------|:---:|:---:|
| E-1 | Lake Formation column-level: alternative registration path | High | TBD |
| E-2 | LF-Tags taxonomy deployment and testing | Medium | ✅ Verified (tags created, assigned, grant succeeded) |
| E-3 | Data perimeter: VPC endpoint + SCP enforcement | Medium | Pattern documented |
| E-4 | Bedrock private connectivity (VPC endpoints) | Medium | Pattern documented |
| E-5 | Multi-account deployment (platform / security / workload separation) | Low | TBD |

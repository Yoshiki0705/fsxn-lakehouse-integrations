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
| A-4 | S3 Tables direct REST vs Glue Iceberg REST: PyIceberg, Spark, Athena, Lake Formation | Medium | ✅ Verified: Athena ✅, PyIceberg ✅, EMR Spark 7.13.0 ✅ (full SELECT + time travel), Glue REST credential vending ❌ (not implemented) |
| A-5 | Monitor Glue REST /v1/config for credential vending indicators | Low | TBD — Periodically check if `token-refresh-enabled` changes from `false` to `true` (would indicate credential vending support added) |

## B. Databricks Validation

| # | Validation | Priority | Status |
|---|-----------|:---:|:---:|
| B-1 | Spark cluster + AWS Glue Iceberg REST: read, append, time travel | High | ❌ Blocked by Unity Catalog (spark.conf.set and cluster Spark config both ineffective; UC controls catalog registration) |
| B-2 | Lake Formation credential vending via Glue REST from Databricks | High | TBD |
| B-3 | S3 Tables metadata table access ($history, $manifests) from Spark | Medium | TBD |
| B-4 | Unity Catalog Foreign Iceberg: S3 Tables direct REST | High | Follow-up submitted to Databricks support (2026-06-01) |
| B-5 | Unity Catalog Foreign Iceberg: Glue Iceberg REST | High | Follow-up submitted to Databricks support (2026-06-01) |
| B-6 | Databricks SQL Warehouse: CREATE CONNECTION TYPE iceberg_rest | Low | Observed limitation (2026-05-31) |
| B-7 | UC audit logging for external Iceberg REST access | Low | ✅ Confirmed (2026-06-01) |
| B-8 | Delta Sharing via S3 Access Point (session policy bypass) | Low | ❌ Confirmed not supported (2026-06-01). Sharing server uses same UC storage credentials. |
| B-9 | NFS mount path as UC External Volume | Low | ❌ Confirmed not supported (2026-06-01). Cloud storage URIs only. Internal AHA exists for EFS/NFS. |

## C. Snowflake Validation

| # | Validation | Priority | Status |
|---|-----------|:---:|:---:|
| C-1 | CATALOG INTEGRATION (ICEBERG_REST + AWS_GLUE + VENDED_CREDENTIALS): credential vending | High | ❌ **Confirmed incompatible** (2026-06-02): Snowflake Support confirmed loadTable must return s3.access-key-id/secret/token. Glue REST does not return these. No known Snowflake-side issue — AWS Glue REST simply does not vend credentials. |
| C-2 | CREATE ICEBERG TABLE + SELECT query | High | ❌ Blocked by C-1 (fundamental incompatibility confirmed by both Snowflake Support and our loadTable evidence) |
| C-3 | AUTO_REFRESH behavior (Iceberg snapshot detection) | Medium | ❌ Blocked by C-1 |
| C-4 | Snowflake Open Catalog / Polaris as alternative catalog | Medium | TBD |
| C-5 | Metadata sync to Snowflake managed table for Cortex Search | Medium | TBD |
| C-6 | Horizon governance (Row Access Policy) on synced metadata | Low | TBD |
| C-7 | Object Store catalog integration (read metadata file directly) | High | ❌ **Access Denied** (2026-06-02): AssumeRole succeeds but Snowflake's access pattern (includes ListBucket) is blocked by S3 Tables internal bucket restrictions. Metadata must be exported to standard S3 bucket first. |
| C-10 | Glue REST + EXTERNAL_VOLUME_CREDENTIALS | High | ❌ **Access Denied** (2026-06-02): Tested per Snowflake Support recommendation. Same S3 Tables internal bucket restriction. Blocker is NOT credential mode — it's the storage layer itself. |
| C-8 | TO_FILE with string literal syntax on S3 AP stage | Medium | ✅ **Verified** (2026-06-02): TO_FILE works with S3 AP stage using string literal syntax + correct file path. Original issues were (1) syntax error (identifier vs string literal) and (2) non-existent file path. NOT an S3 AP-specific limitation. |
| C-9 | SYSTEM$VERIFY_CATALOG_INTEGRATION('S3TABLES_GLUE_REST_INT') | Medium | ✅ Healthy (2026-06-02): "Statement executed successfully" — connectivity confirmed |
| C-11 | ETL S3 Tables → standard Glue Iceberg → Snowflake VENDED_CREDENTIALS | Medium | ❌ **Root Cause Found** (2026-06-03): Glue Iceberg REST endpoint ONLY supports loadTable for `s3tablescatalog` federated catalogs. Standard Glue Data Catalog tables return 403 even with admin credentials. This is NOT a permissions issue — it is a service scope limitation. ETL to standard Glue does NOT resolve Snowflake access via Glue Iceberg REST. The endpoint is designed exclusively for S3 Tables. |

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

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
| B-2 | Lake Formation credential vending via Glue REST from Databricks | High | ❌ S3 Tables not supported in Databricks (confirmed 2026-06-02) |
| B-3 | S3 Tables metadata table access ($history, $manifests) from Spark | Medium | ❌ S3 Tables not supported in Databricks |
| B-4 | Unity Catalog Foreign Iceberg: S3 Tables direct REST | High | ❌ **Not supported** (2026-06-02): S3 Tables is not supported in Databricks. Internal product request DB-I-15824 tracking. |
| B-5 | Unity Catalog Foreign Iceberg: Glue Iceberg REST | High | ❌ **Not supported** (2026-06-02): No UC connection type for Iceberg REST catalogs exists today. Glue foreign catalog support is via Glue catalog/metastore APIs only. |
| B-10 | Post-GA revalidation: HMS Federation + S3 Tables | High | ❌ **Still blocked** (2026-06-09): Retested after Foreign Iceberg + Credential Vending GA (2026-05-28). Glue Connection ✅, Service Credential ✅, Storage Credential ✅ all succeeded. External Location creation fails with `AWSBadRequestException` — S3 Tables internal bucket rejects standard S3 API (HeadBucket/ListBucket) validation. Without External Location, Foreign Catalog `authorized_paths` cannot be satisfied. Root cause identical to Snowflake (S3 Tables internal bucket API constraint), but Snowflake bypasses via VENDED_CREDENTIALS; Databricks has no bypass. |
| B-6 | Databricks SQL Warehouse: CREATE CONNECTION TYPE iceberg_rest | Low | Observed limitation (2026-05-31) |
| B-7 | UC audit logging for external Iceberg REST access | Low | ✅ Confirmed (2026-06-01) |
| B-8 | Delta Sharing via S3 Access Point (session policy bypass) | Low | ❌ Confirmed not supported (2026-06-01). Sharing server uses same UC storage credentials. |
| B-9 | NFS mount path as UC External Volume | Low | ❌ Confirmed not supported (2026-06-01). Cloud storage URIs only. Internal AHA exists for EFS/NFS. |

## C. Snowflake Validation

| # | Validation | Priority | Status |
|---|-----------|:---:|:---:|
| C-1 | CATALOG INTEGRATION (ICEBERG_REST + AWS_GLUE + VENDED_CREDENTIALS): credential vending | High | ✅ **FULLY WORKING** (2026-06-05): Explicit `ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS` + schema with no default EXTERNAL_VOLUME + no EXTERNAL_VOLUME in CREATE TABLE. Previous failures were due to default mode (EXTERNAL_VOLUME_CREDENTIALS) triggering ListObjectsV2. AWS prerequisite: `register-resource --with-federation`. |
| C-2 | CREATE ICEBERG TABLE + SELECT query | High | ✅ **VERIFIED** (2026-06-05): CREATE SUCCESS (5.9s), SELECT * LIMIT 5 SUCCESS (1.6s), 5 rows returned. Query ID: 01c4e515-0003-ee3c-0003-6a86002d62b2 |
| C-3 | AUTO_REFRESH behavior (Iceberg snapshot detection) | Medium | ✅ **FULLY VERIFIED** (2026-06-08): AUTO_REFRESH enabled (131ms). **Real-world test**: PyIceberg appended 1 record → Snowflake COUNT(*) changed 170→171 within 30s automatically. Time Travel also verified: AT(OFFSET => -1200) returns 170 (prior snapshot). |
| C-4 | Snowflake Open Catalog / Polaris as alternative catalog | Medium | TBD |
| C-5 | Metadata sync to Snowflake managed table for Cortex Search | Medium | TBD |
| C-6 | Horizon governance (Row Access Policy) on synced metadata | Low | TBD |
| C-7 | Object Store catalog integration (read metadata file directly) | High | ❌ **Access Denied** (2026-06-02): AssumeRole succeeds but Snowflake's access pattern (includes ListBucket) is blocked by S3 Tables internal bucket restrictions. Metadata must be exported to standard S3 bucket first. |
| C-10 | Glue REST + EXTERNAL_VOLUME_CREDENTIALS | High | ❌ **Root cause identified** (2026-06-05): EXTERNAL_VOLUME_CREDENTIALS is the DEFAULT mode. Triggers ListObjectsV2 which S3 Tables rejects. **RESOLUTION**: Use explicit `ACCESS_DELEGATION_MODE = VENDED_CREDENTIALS` instead (verified working). |
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
| E-1 | Lake Formation column-level: alternative registration path | High | ❌ **Not supported via VENDED_CREDENTIALS** (2026-06-08): When `AllowFullTableExternalDataAccess=false`, VENDED_CREDENTIALS path is completely blocked regardless of explicit column/table-level grants or ExternalDataFilteringAllowList. Column-level governance must be implemented via Snowflake Horizon (Row Access Policy / Column Masking) or separate Iceberg tables. |
| E-2 | LF-Tags taxonomy deployment and testing | Medium | ✅ Verified (tags created, assigned, grant succeeded) |
| E-3 | Data perimeter: VPC endpoint + SCP enforcement | Medium | Pattern documented |
| E-4 | Bedrock private connectivity (VPC endpoints) | Medium | Pattern documented |
| E-5 | Multi-account deployment (platform / security / workload separation) | Low | TBD |

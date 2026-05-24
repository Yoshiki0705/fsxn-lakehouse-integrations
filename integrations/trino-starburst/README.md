# Trino / Starburst Integration

🌐 **English** | [日本語](docs/ja/README.md)

## Overview

Query FSx for ONTAP data via S3 Access Points using Trino — an open-source distributed SQL query engine. Trino uses its own S3 filesystem implementation that supports path-style access, making it compatible with FSx S3 AP aliases.

## Status: ✅ Read Verified (2026-05-24)

- **Read**: All queries succeed on FSx S3 AP (10K and 5M row Parquet)
- **Write-back (CTAS)**: Failed due to file-based metastore limitation (not FSx S3 AP issue). Requires Glue Catalog or Hive Metastore for write operations.
- **No session policy issues**: Direct IAM credentials, no intermediary governance layer
- Tested on separate SVM (svm-0e5ef72d9b4470f19) while original SVM has a service issue

**Benchmark (Trino 438, single-node Docker arm64, ap-northeast-1):**

| Query | 10K rows | 5M rows (103 MB) |
|-------|----------|-------------------|
| COUNT(*) | 1,136 ms | 1,075 ms |
| GROUP BY + AVG | 860 ms | 1,462 ms |
| WHERE filter | — | 1,227 ms |

## Architecture

```
Trino (Docker, single-node)
    │
    └── Hive Connector (file-based metastore)
            │
            └── S3 filesystem (path-style access)
                    │
                    └── FSx S3 Access Point (internet-origin)
                            │
                            └── FSx for ONTAP Volume (Parquet files)
```

## Key Configuration

Trino's Hive connector supports `hive.s3.path-style-access=true`, which is required for S3 AP alias resolution (same pattern as DuckDB's `s3_url_style='path'`).

```properties
# catalog/fsxn.properties
connector.name=hive
hive.metastore=file
hive.metastore.catalog.dir=s3://<FSx-S3-AP-alias>/
hive.s3.path-style-access=true
hive.s3.endpoint=https://s3.ap-northeast-1.amazonaws.com
hive.s3.region=ap-northeast-1
hive.s3.aws-access-key=<from-instance-profile-or-explicit>
hive.s3.aws-secret-key=<from-instance-profile-or-explicit>
```

## Expected Behavior

Based on DuckDB and EMR Spark verification results (both use path-style S3 access):
- **Read Parquet**: Expected to WORK (same S3 API pattern as DuckDB httpfs)
- **Write Parquet**: Expected to WORK (flat file PutObject)
- **Delta/Iceberg write**: Expected to FAIL (same atomic rename constraint)
- **No session policy issues**: Direct IAM credentials, no intermediary governance layer

## Unstructured Data Support

| Format | Support | Access Method | Use Case |
|--------|:---:|--------------|----------|
| Images (JPEG, PNG, TIFF) | ❌ | N/A (SQL engine for structured data) | — |
| Video (MP4, MOV) | ❌ | N/A | — |
| Documents (PDF, DOCX) | ❌ | N/A | — |
| Audio (WAV, MP3) | ❌ | N/A | — |
| Binary / Archives | ❌ | N/A | — |

Trino is a distributed SQL query engine for structured data. It cannot directly query unstructured data. However, you can create metadata tables and use federated queries across multiple data sources.

**Patterns:**
1. **Metadata table** — Register file paths, sizes, and types as Hive tables for querying
2. **Multi-source federation** — JOIN FSx S3 AP file catalogs with other data sources (RDS, PostgreSQL)
3. **Hive Connector** — Read Parquet metadata directly from S3 AP with path-style access

```sql
-- Query file catalog
SELECT file_path, file_type, file_size, last_modified
FROM fsxn.default.file_catalog
WHERE file_type = 'image/jpeg'
  AND file_size > 1000000;

-- Federated JOIN with other data sources
SELECT f.file_path, m.model_name, m.accuracy
FROM fsxn.default.file_catalog f
JOIN ml_catalog.default.model_results m ON f.file_path = m.input_path;
```

## Quick Start

```bash
# 1. Start Trino (Docker)
docker compose up -d

# 2. Connect with Trino CLI
docker exec -it trino trino --catalog fsxn --schema default

# 3. Run queries
trino> SELECT COUNT(*) FROM sensor_data;
trino> SELECT status, AVG(temperature) FROM sensor_data GROUP BY status;
```

## Directory Structure

```
integrations/trino-starburst/
├── README.md                          ← This file
├── docker-compose.yaml                ← Trino single-node + config
├── config/
│   ├── etc/
│   │   ├── config.properties          ← Trino server config
│   │   ├── jvm.config                 ← JVM settings
│   │   ├── node.properties            ← Node identity
│   │   └── catalog/
│   │       └── fsxn.properties        ← FSx S3 AP connector config
├── sql/
│   ├── 01_create_schema.sql           ← Schema + table DDL
│   ├── 02_read_queries.sql            ← SELECT, GROUP BY, aggregation
│   └── 03_write_back.sql             ← CTAS write-back test
├── scripts/
│   ├── run_verification.sh            ← End-to-end verification
│   └── cleanup.sh                     ← Stop and remove containers
└── params.example.json                ← Parameter template
```

## Comparison with Other Engines

| Feature | Trino | DuckDB | Athena | EMR Spark |
|---------|-------|--------|--------|-----------|
| Deployment | Docker / EC2 / K8s | In-process / Lambda | Serverless | EMR Serverless |
| S3 AP support | path-style access | path-style + endpoint | Native (EMRFS) | Native (EMRFS) |
| Session policy risk | None (direct IAM) | None (direct IAM) | None (AWS-native) | None (AWS-native) |
| Write-back | PutObject (flat files) | COPY TO | CTAS | Spark write |
| Cost model | Compute (EC2/container) | Per-invocation (Lambda) | Per-scan | Per-job |
| Best for | Federated SQL, multi-source | Lightweight ad-hoc | Serverless SQL | Large-scale ETL |

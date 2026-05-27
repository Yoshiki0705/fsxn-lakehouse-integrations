# Vendor Comparison Matrix

🌐 [日本語](../ja/vendor-comparison.md)

## Project Concept

Amazon FSx for NetApp ONTAP (FSx for ONTAP) × S3 Access Points × Lakehouse/Data Lake Integrations

A pattern library enabling direct access from Lakehouse/Data Lake platforms to
FSx for ONTAP enterprise storage via S3 Access Points.
Leverages ONTAP deduplication, compression, Snapshot, and tiering while integrating
with modern analytics platforms.

```
Lakehouse Platform ←→ S3 Access Point ←→ FSx for NetApp ONTAP
(External Table / Stage / Location)         (NFS/SMB/S3 unified storage)
```

---

## Tier 1: Primary Candidates

| Vendor | Integration Method | Use Case | Status |
|--------|-------------------|----------|--------|
| **Databricks** | Unity Catalog External Location / S3 External Table | Delta Lake on FSx for ONTAP, ML Feature Store | ⚠️ Blocked (session policy — UC table creation fails) |
| **Snowflake** | External Stage + `AWS_ACCESS_POINT_ARN` / External Table | Governed analytics, Cortex AI, Data Sharing, Managed Iceberg | ✅ Verified (May 2026) |

### Databricks

- **Auth**: Cross-account IAM Role + External ID
- **Network**: VPC network origin (recommended)
- **Formats**: Delta Lake, Iceberg, Parquet, CSV, JSON, ORC
- **Unstructured**: UC Volumes + `read_files()` + `ai_query()` (LLM on images/docs) + `ai_parse_document()` (OCR)
- **AI Capabilities**: Mosaic AI (ML training, Feature Store, Model Registry), `ai_query` (LLM on files), `ai_parse_document` (OCR), Vector Search (RAG), MLflow experiment tracking
- **Governance**: Unity Catalog — Table/Column Grants, Row Filters, Column Masks, UC Tags, Automatic Lineage (column-level), Audit Logs (system tables), Lakehouse Monitoring (data quality + drift)
- **Data Sharing**: Delta Sharing — open protocol, readable by Snowflake, Pandas, Spark, Power BI without Databricks account
- **ONTAP Value**: FlexClone (dev/test), Snapshot (complements Delta Time Travel), FabricPool (cold data tiering)
- **Unique strengths**: Automatic data lineage (column-level), ML model governance (MLflow + Model Registry), Lakehouse Monitoring, Iceberg REST Catalog (external engine access to UC tables)
- **Limitation**: UC session policy blocks table creation and subdirectory listing on FSx S3 AP directly. **Recommended path: DataSync → S3 → UC** (full governance, full AI, full lineage)

### Snowflake

- **Auth**: Storage Integration + IAM Role
- **Network**: Internet network origin (PrivateLink optional)
- **Formats**: Parquet, CSV, JSON, Avro, ORC, Iceberg
- **Unstructured**: Directory Table + Pre-signed URLs + Cortex AI (PARSE_DOCUMENT for OCR, multimodal vision via staging)
- **AI Capabilities**: 8/10 Cortex AI functions verified on FSx data (SUMMARIZE, TRANSLATE, SENTIMENT, COMPLETE, EXTRACT_ANSWER, PARSE_DOCUMENT, Cortex Search 198ms, Vision AI via staging)
- **Governance**: Object Tags, Row Access Policy, Column Masking, Data Sharing — all verified on External Table
- **Advanced Patterns**: Dynamic Table (confirmed, FULL refresh, min 60s TARGET_LAG), Managed Iceberg Table (confirmed, open format on customer S3)
- **ONTAP Value**: Snapshot (beyond Time Travel retention), FlexClone (test env), multi-protocol (NFS/SMB/S3 on same data)
- **Data Sharing**: Governed distribution to partners/suppliers via Snowflake Data Sharing (External Table shareable)
- **Known Limitation**: AUTO_REFRESH not available (no S3 Event Notifications); use Task + ALTER EXTERNAL TABLE REFRESH

---

## Tier 2: Open Table Formats

| Format/Engine | Integration Method | Use Case | Status |
|--------------|-------------------|----------|--------|
| **Apache Iceberg** | S3 Catalog + S3 AP | Vendor-neutral table format | 🚧 Planned |
| **Delta Lake (OSS)** | S3 Storage Layer | Spark/Databricks compatible | 🚧 Planned |
| **Apache Hudi** | S3 Storage Layer | CDC, incremental processing | 🚧 Planned |
| **Dremio** | S3 Source / Nessie Catalog | Iceberg-native Lakehouse | 🚧 Planned |
| **Starburst / Trino** | S3 Connector / Hive Metastore | Distributed SQL federation | 🚧 Planned |

### Apache Iceberg

- **Auth**: IAM Role (engine-dependent)
- **Catalog**: REST Catalog, Glue Catalog, Hive Metastore
- **Features**: Vendor-neutral, schema evolution, partition evolution
- **Unstructured**: File management via metadata tables

### Dremio

- **Auth**: IAM Role / Access Key
- **Catalog**: Nessie (Git-like catalog) / Arctic
- **Features**: Iceberg-native, reflections (acceleration)
- **Unstructured**: Metadata cataloging only

### Starburst / Trino

- **Auth**: IAM Role / Instance Profile
- **Catalog**: Hive Metastore / Glue Catalog
- **Features**: Distributed SQL, federated queries, many connectors
- **Unstructured**: File metadata queryable

---

## Tier 3: Cloud-Native Analytics (AWS)

| Service | Integration Method | Use Case | Status |
|---------|-------------------|----------|--------|
| **AWS Athena** | Direct S3 AP query via Glue Catalog | Serverless SQL | ✅ Security Verified |
| **AWS Glue** | S3 AP Crawler / ETL Job | Data catalog + ETL + write-back | ✅ Functional Verified |
| **AWS Lake Formation** | Governance on Glue Catalog tables | Fine-grained access (table/column/row/tag) | ✅ Verified (column, row filter, LF-Tag) |
| **Amazon Redshift Spectrum** | External Schema on Glue Catalog | DWH + Data Lake federated query | ✅ Functional Verified |
| **Amazon EMR Serverless** | EMRFS (`s3://`) direct access | Spark ETL + write-back | ✅ Functional Verified |
| **Amazon Bedrock KB** | S3 AP as data source | RAG / document retrieval | ✅ AWS-documented path |
| **DuckDB Lambda** | httpfs extension + path-style | Lightweight serverless analytics | ✅ Functional Verified |

### AWS Athena

- **Auth**: IAM Role (service role)
- **Network**: Internet network origin **required**
- **Features**: Serverless, pay-per-query ($5/TB scanned), Glue Catalog integration
- **AI Integration**: Athena + Bedrock KB (RAG on same FSx data), Athena + SageMaker (ML inference UDF)
- **Governance**: Lake Formation (table/column/row/tag) — same permissions apply to Athena and Redshift Spectrum
- **Write-back**: ✅ CTAS writes Parquet back to FSx S3 AP (verified, 3.7s)
- **Unique strengths**: Zero infrastructure, shared Glue Catalog with all AWS engines, Lake Formation governance automatic
- **Benchmark**: 54.8 MB/s peak (5M rows in 2.2s)
- **Reference**: [AWS Tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

### AWS Glue

- **Auth**: Glue service role
- **Network**: Internet network origin **required**
- **Features**: Crawler (schema discovery), ETL Job (PySpark/Python Shell/Ray), Data Quality
- **AI Integration**: Glue + Bedrock (AI-powered transforms), Glue Data Quality (automated validation)
- **Governance**: Glue Data Catalog is the foundation for Lake Formation — all permissions defined here
- **Write-back**: ✅ ETL write-back to FSx S3 AP (verified, 64s for 10K row medallion pipeline)
- **Unique strengths**: Schema discovery (Crawler), visual ETL (Studio), serverless Spark, Data Quality rules
- **Reference**: [AWS Tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

### AWS Lake Formation

- **Auth**: Lake Formation admin + per-principal grants
- **Network**: N/A (governance layer, not a query engine)
- **Features**: Table/column-level grants, Row Filters (Data Cells Filter), LF-Tags (tag-based access control), cross-account sharing
- **AI Integration**: Governs data accessed by Bedrock KB, SageMaker, EMR ML workloads
- **Governance**: ✅ **The strongest AWS-native governance** — fine-grained (column/row/tag), multi-engine (Athena + Redshift + EMR + Glue all share same permissions), zero data movement
- **Unique strengths**: Single governance definition applies to ALL AWS analytics engines simultaneously. No per-engine configuration needed. Cross-account table sharing without data copy.
- **Verified capabilities (May 2026)**: Column-level permission (deny specific columns), Row Filter (Data Cells Filter with expression), LF-Tag (sensitivity classification + tag-based grants)

### Amazon Redshift Spectrum

- **Auth**: Redshift IAM Role with S3 AP permissions
- **Network**: Internet network origin **required**
- **Features**: DWH + Data Lake federated query, materialized views, stored procedures
- **AI Integration**: Redshift ML (CREATE MODEL), federated query to SageMaker endpoints
- **Governance**: Lake Formation (same permissions as Athena — configure once, apply everywhere)
- **Write-back**: ❌ (query results stay in Redshift; use EMR for write-back)
- **Unique strengths**: JOIN NAS data with local DWH tables, materialized views on external data, same Glue Catalog as Athena
- **Benchmark**: 5M rows in 4.3s (Serverless 8 RPU)
- **Reference**: [AWS re:Post](https://repost.aws/articles/AR7E4oxFvtR5GgajAQT7X1xQ)

### Amazon EMR Serverless (Spark)

- **Auth**: Execution role (IAM)
- **Network**: Internet network origin (EMRFS handles S3 AP natively)
- **Features**: Full Spark SQL, UDFs, window functions, MLlib, distributed processing
- **AI Integration**: Spark MLlib, SageMaker Spark connector, Iceberg table creation on S3
- **Governance**: IAM-based (pair with Lake Formation for governed reads on output)
- **Write-back**: ✅ **Best write-back path** — flat Parquet to FSx S3 AP (verified, 16s total ETL)
- **Unique strengths**: No session policy issues (direct IAM), full Spark power, write-back to FSx, Iceberg table creation on S3
- **Benchmark**: 10K rows read+transform+write in 16s, $0.05/job
- **Critical note**: Use `s3://` (EMRFS), NOT `s3a://` (S3A cannot parse AP alias)

### Amazon Bedrock Knowledge Bases

- **Auth**: Bedrock service role with S3 AP permissions
- **Network**: Internet network origin
- **Features**: RAG document ingestion, vector embeddings, permission-aware retrieval
- **AI Integration**: ✅ **Native RAG path** — ingest documents from FSx S3 AP, create embeddings, semantic search with guardrails
- **Governance**: Bedrock guardrails (topic filtering, PII detection, hallucination reduction), IAM model access policies
- **Unique strengths**: Zero-copy RAG (reads directly from FSx S3 AP without COPY INTO), permission-aware retrieval, Bedrock agents for multi-step reasoning
- **Reference**: [AWS Tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-build-rag-with-bedrock.html)

### DuckDB Lambda

- **Auth**: Lambda execution role (IAM)
- **Network**: Internet network origin (no VPC needed)
- **Features**: In-process SQL, sub-second warm queries, arm64 (Graviton2)
- **AI Integration**: Minimal (SQL-only; pair with Bedrock for AI)
- **Governance**: IAM + S3 AP policy only (no table-level governance)
- **Write-back**: ✅ COPY TO Parquet (verified, 304ms)
- **Unique strengths**: Cheapest path ($0.00001/query), zero idle cost, sub-second warm latency (452ms)
- **Benchmark**: 10K rows in 452ms (warm), 5M rows in 779ms

### AWS-Native Unique Value Proposition

| Advantage | Detail |
|-----------|--------|
| **No session policy issues** | All AWS services use direct IAM — no intermediary session policies that block S3 AP ARN format |
| **Shared Glue Catalog** | Athena, Redshift Spectrum, EMR, Glue all share the same catalog. Register once, query from any engine. |
| **Lake Formation multi-engine** | One governance definition applies to ALL engines simultaneously. No per-platform configuration. |
| **Zero-copy RAG** | Bedrock KB reads directly from FSx S3 AP — no COPY INTO, no staging, no data movement for RAG |
| **Serverless-first** | Athena, Glue, EMR Serverless, Lambda — zero idle cost across the entire stack |
| **Write-back verified** | EMR, Athena CTAS, DuckDB all write flat Parquet back to FSx S3 AP (Snowflake/Databricks cannot) |
| **Iceberg on S3** | EMR Spark creates Iceberg tables on standard S3 → registered in Glue Catalog → queryable by Athena/Redshift/Snowflake/Databricks |

### Google BigQuery Omni

- **Auth**: S3 Connection (IAM Role)
- **Network**: Internet network origin
- **Features**: Cross-cloud analytics, BigLake tables
- **Unstructured**: Object Table for image/video metadata

### Microsoft Fabric / Synapse

- **Auth**: S3 Shortcut (Access Key / IAM Role)
- **Network**: Internet network origin
- **Features**: OneLake integration, Power BI connectivity
- **Unstructured**: File access via OneLake Shortcut

---

## Tier 4: Emerging & Specialized

| Vendor | Integration Method | Use Case | Status |
|--------|-------------------|----------|--------|
| **Firebolt** | S3 External Table | High-speed OLAP | 📋 Research |
| **ClickHouse** | S3 Table Function | Real-time analytics | 📋 Research |
| **DuckDB** | S3 httpfs Extension | Edge/Lambda analytics | ✅ Functional Verified |
| **Apache Spark (Self-managed)** | S3A FileSystem | Custom Spark cluster | 📋 Research |
| **Presto / PrestoDB** | Hive Connector + S3 | Distributed query | 📋 Research |

### DuckDB

- **Auth**: Access Key / IAM Role (Lambda execution role)
- **Network**: VPC network origin possible
- **Features**: In-process analytics, runs inside Lambda, lightweight
- **Unstructured**: Parquet/CSV only (no binary support)
- **Use Case**: Lightweight analytics in Lambda, edge computing

### ClickHouse

- **Auth**: Access Key
- **Network**: Internet network origin
- **Features**: Columnar, real-time analytics, high-speed aggregation
- **Unstructured**: Not supported (structured data only)

### Firebolt

- **Auth**: IAM Role
- **Network**: Internet network origin
- **Features**: High-speed OLAP, sub-second queries
- **Unstructured**: Not supported

---

## Unstructured Data Support Matrix

| Platform | Images | Video | Audio | Documents | Method |
|----------|--------|-------|-------|-----------|--------|
| **SageMaker** | ✅ | ✅ | ✅ | ✅ | Direct S3 AP read |
| **Bedrock** | ✅ | ❌ | ❌ | ✅ | Knowledge Base (RAG) |
| **Rekognition** | ✅ | ✅ | ❌ | ❌ | Direct S3 AP read |
| **Transcribe** | ❌ | ❌ | ✅ | ❌ | Direct S3 AP read |
| **Textract** | ✅ | ❌ | ❌ | ✅ | Direct S3 AP read |
| **Lambda** | ✅ | ✅ | ✅ | ✅ | S3 AP read/write |
| **Databricks** | ✅ | ✅ | ✅ | ✅ | binaryFile format |
| **Snowflake** | ✅ | ✅ | ✅ | ✅ | Directory Table + Pre-signed URLs |
| **EMR Spark** | ✅ | ✅ | ✅ | ✅ | binaryFile / custom |
| **Athena** | ❌ | ❌ | ❌ | ❌ | Structured data only |
| **BigQuery Omni** | ✅ | ✅ | ❌ | ❌ | Object Table |

✅ = Direct processing / 📋 = Metadata only / ❌ = Not supported

---

## Network Origin Requirements

| Network Origin | Supported Platforms |
|---------------|-------------------|
| **VPC origin** | Databricks, EMR, Lambda, DuckDB (in Lambda) |
| **Internet origin** | Athena, Glue, Redshift Spectrum, Snowflake, BigQuery Omni, Fabric |

⚠️ VPC origin: Access only from within same VPC (more secure)
⚠️ Internet origin: Protected by IAM auth (broader service compatibility)

---

## Selection Guide

### Structured Data Analytics

```
High-frequency queries + governance → Databricks (Unity Catalog) — requires DataSync → S3
AI on NAS data (summarize, RAG, sentiment) → Snowflake (External Table + Cortex AI)
Data sharing + SQL-centric + governance → Snowflake (External Table + Tags + Data Sharing)
Serverless + low cost → Athena
ETL pipelines → Glue
DWH integration → Redshift Spectrum
Open format interoperability → Snowflake Managed Iceberg Table (readable by all engines)
```

### Unstructured Data Processing

```
AI/ML training → SageMaker + S3 AP
RAG pipelines → Bedrock + S3 AP
Image/video analysis → Rekognition + Lambda + S3 AP
Document processing → Textract + Lambda + S3 AP
Media transcoding → MediaConvert + S3 AP
```

### Vendor Neutrality Priority

```
Table format → Apache Iceberg
Catalog → REST Catalog or Glue Catalog
Engine → Trino / Spark / Dremio
```

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
| **Databricks** | Unity Catalog External Location / S3 External Table | Delta Lake on FSx for ONTAP, ML Feature Store | ⚠️ Blocked (session policy) |
| **Snowflake** | External Stage / External Table / Iceberg Table | Data sharing, ELT pipelines | ⚠️ Blocked (session policy) |

### Databricks

- **Auth**: Cross-account IAM Role + External ID
- **Network**: VPC network origin (recommended)
- **Formats**: Delta Lake, Iceberg, Parquet, CSV, JSON, ORC
- **Unstructured**: `binaryFile` format for image/video reading
- **ONTAP Value**: FlexClone (dev/test), Snapshot (complements Time Travel)

### Snowflake

- **Auth**: Storage Integration + IAM Role
- **Network**: Internet network origin (PrivateLink optional)
- **Formats**: Parquet, CSV, JSON, Avro, ORC, Iceberg
- **Unstructured**: Directory Table + Pre-signed URLs (works despite AWS docs saying "Not supported")
- **ONTAP Value**: Snapshot (beyond Time Travel retention), FlexClone (test env)
- **Known Limitation**: High latency on S3 AP operations (30s-5min+ for stage/list)

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

## Tier 3: Cloud-Native Analytics

| Service | Integration Method | Use Case | Status |
|---------|-------------------|----------|--------|
| **AWS Athena** | Direct S3 AP query | Serverless SQL | ✅ Security Verified |
| **AWS Glue** | S3 AP Crawler / ETL Job | Data catalog + ETL | ✅ Functional Verified |
| **AWS Lake Formation** | S3 AP registration | Governance, permissions | 🚧 Planned |
| **Amazon Redshift Spectrum** | External Schema on S3 AP | DWH + Data Lake | 🚧 Planned |
| **Amazon EMR (Spark)** | S3A Connector → S3 AP | Large-scale batch | 🚧 Planned |
| **Google BigQuery Omni** | S3 Connection | Cross-cloud analytics | 📋 Research |
| **Microsoft Fabric / Synapse** | S3 Shortcut / External Table | Microsoft ecosystem | 📋 Research |

### AWS Athena

- **Auth**: IAM Role (service role)
- **Network**: Internet network origin **required**
- **Features**: Serverless, pay-per-query (data scanned)
- **Unstructured**: Metadata query only (file path, size)
- **Reference**: [AWS Tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-query-data-with-athena.html)

### AWS Glue

- **Auth**: Glue service role
- **Network**: Internet network origin **required**
- **Features**: Crawler (schema discovery), ETL Job (PySpark/Python Shell/Ray)
- **Unstructured**: Crawler collects file metadata, ETL transforms
- **Reference**: [AWS Tutorial](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/tutorial-transform-data-with-glue.html)

### Amazon Redshift Spectrum

- **Auth**: Redshift IAM Role
- **Network**: Internet network origin **required**
- **Features**: DWH + Data Lake federated query
- **Unstructured**: Not supported (structured data only)
- **Reference**: [AWS re:Post](https://repost.aws/articles/AR7E4oxFvtR5GgajAQT7X1xQ)

### Amazon EMR (Spark)

- **Auth**: Instance Profile / IAM Role
- **Network**: VPC network origin possible
- **Features**: Large-scale batch, Spark/Hive/Presto
- **Unstructured**: `binaryFile` format, image processing libraries

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
| **DuckDB** | S3 httpfs Extension | Edge/Lambda analytics | 🚧 Planned |
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
High-frequency queries + governance → Databricks (Unity Catalog)
Data sharing + SQL-centric → Snowflake
Serverless + low cost → Athena
ETL pipelines → Glue
DWH integration → Redshift Spectrum
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

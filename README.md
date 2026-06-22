🌐 **English** | [日本語](./README-ja.md)

# FSx for ONTAP Lakehouse Integrations

> **A validation framework for testing how different analytics and lakehouse engines interact with FSx for ONTAP S3 Access Points.** Each integration directory contains reproducible evidence, test templates, and observed boundary documentation — not production-ready connectors.

---

## Start Here — Choose Your Path

| Your role | Start with | Time |
|-----------|-----------|:----:|
| 📊 **Business leader / Sales / Account manager** | [**Plain-Language Business Guide**](docs/en/quickstart-business-guide.md) — No jargon, what it does, what it costs | 5 min |
| 🏭 **Industry solution architect** | [**Industry Solution Catalog**](docs/en/industry-solution-catalog.md) — 26 industries, recommended patterns per use case | 20 min |
| 🔧 **Technical lead / Data engineer** | [**UC Connection Guide**](docs/en/fsx-ontap-to-databricks-unity-catalog-guide.md) — Full architecture, all paths, constraints | 30 min |
| 🚀 **Implementation partner / SI** | [**PoC Execution Guide**](docs/implementation-guide/poc-execution-guide.md) — Step-by-step checklist, troubleshooting | 15 min |
| 📐 **Solutions architect** | [**Architecture Comparison**](docs/adoption-guide/architecture-comparison.md) — Decision framework, trade-offs | 15 min |
| 🔍 **Evaluating cost** | [**Cost Estimation**](docs/adoption-guide/cost-estimation.md) — Component breakdown, scaling formulas | 10 min |

---

## Overview

**Turn existing enterprise file assets into analytics- and AI-ready data without disrupting NFS/SMB workloads.**

Data Lake and Lakehouse platform integrations with **Amazon FSx for NetApp ONTAP (FSx for ONTAP)** via **S3 Access Points**.

---

## Business Outcomes

| Outcome | Description |
|---------|-------------|
| **Eliminate data copies** | N redundant copies → 1 authoritative source on FSx for ONTAP |
| **Remove NAS→S3 sync pipelines** | No ETL jobs needed to copy file data to S3 for analytics |
| **Accelerate time-to-insight** | Days of pipeline setup → hours of direct query via S3 Access Point |
| **Preserve existing NFS/SMB workloads** | Applications continue writing via NFS/SMB unchanged |
| **Unified governance** | Single data location with dual-layer access control (IAM + file system permissions) |
| **Enable AI/ML on file data** | Amazon Bedrock, SageMaker, EMR access existing files via S3 AP without data movement |

FSx for ONTAP S3 Access Points enable S3 API access to file data without data movement, allowing S3-compatible applications and AWS services to directly read and write file data. ([AWS Documentation](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html))

---

## Core Technical Capabilities

<details>
<summary>ONTAP capabilities and their lakehouse benefits (click to expand)</summary>

| ONTAP Capability | Lakehouse Benefit |
|-----------------|-------------------|
| Deduplication & Compression | Storage cost reduction for similar datasets |
| Snapshot | Point-in-time recovery complementing Delta/Iceberg time travel (see [Recovery Semantics](docs/en/recovery-semantics.md)) |
| FlexClone | Instant dev/test dataset provisioning |
| SnapMirror | Cross-region DR for lakehouse data |
| FabricPool Tiering | Automatic cold data offload to S3 |
| Multi-protocol (NFS/SMB/iSCSI/S3) | Unified access from any workload |

</details>

---

## Architecture Patterns

<details>
<summary>5 architecture patterns (click to expand)</summary>

### Pattern A: Read-Only Analytics

```
Lakehouse Platform → (S3 API) → S3 Access Point → FSx for ONTAP Volume
```

- Register as External Table / External Stage
- Query Parquet, CSV, JSON, ORC files directly

### Pattern B: Read-Write Managed Tables

```
Lakehouse Platform ←→ S3 Access Point ←→ FSx for ONTAP Volume
```

- Use as storage layer for Iceberg / Delta / Hudi tables
- ONTAP Snapshot for point-in-time table recovery

### Pattern C: ETL Pipeline (Medallion Architecture)

```
Source (FSx for ONTAP) → S3 AP → Glue/EMR/Lambda → Transform → S3 AP → FSx for ONTAP (curated)
```

- Raw → Bronze → Silver → Gold

### Pattern D: Data Sharing

```
FSx for ONTAP (Producer) → S3 AP (scoped policy) → Consumer Platform
```

- S3 AP policy for per-consumer access control
- ONTAP FlexClone for instant logical copies

### Pattern E: OpenSharing (Zero-Copy Governed Access) — Analysis Stage

```
FSx for ONTAP → OpenSharing Server (sharing + access control)
                    → Catalog (governance boundary)
                    → Lakehouse Serverless Compute (in-place query)
                    → Iceberg IRC clients (cross-engine)
```

- Forward-looking pattern based on the [OpenSharing announcement](https://www.databricks.com/company/newsroom/press-releases/databricks-announces-opensharing) (2026-06-10), the evolution of Delta Sharing hosted by the Linux Foundation
- Presigned-URL sharing model may bypass the current Databricks S3 AP ARN limitation (hypothesis under validation)
- See [OpenSharing Integration Analysis](docs/en/opensharing-integration-analysis.md)

</details>

---

## Supported Integrations

<details>
<summary>Platform verification status (click to expand)</summary>
| Platform | Verification Status | Pattern | Notes |
|----------|:---:|---------|-------|
| [AWS Athena](integrations/athena/) | ✅ Security Verified | Glue Data Catalog + Serverless | Read-only. [Benchmark: 54.8 MB/s peak, 5M rows in 2s](verification-pack/athena-parquet-read/) |
| [AWS Glue ETL](integrations/glue/) | ✅ Functional Verified | Crawler + ETL + Medallion | Read + Write-back (Parquet). [64s for 10K row ETL](verification-pack/glue-etl/) |
| [Delta Lake OSS](integrations/delta-lake-oss/) | ✅ Read Verified / ❌ Write | delta-rs + Spark | Read works. Write returns 501 (conditional writes not supported). |
| [Databricks](integrations/databricks/) | ⚠️ Blocked | Unity Catalog + Delta Lake | Session policy does not recognize S3 AP ARN format. Support case filed. OpenSharing path under analysis (see [Pattern E](#pattern-e-opensharing-zero-copy-governed-access--analysis-stage)). |
| [Snowflake](integrations/snowflake/) | ✅ Verified | External Stage + External Table | Works with `AWS_ACCESS_POINT_ARN` stage parameter. SELECT + External Table verified. |
| [Apache Iceberg](integrations/iceberg/) | ⚠️ Read Experimental / ❌ Write Failed | REST Catalog (vendor-neutral) | Write fails: S3FileIO cannot handle AP alias for metadata. Read of pre-existing tables expected to work. |
| [Iceberg Metadata Catalog](integrations/iceberg-metadata-catalog/) | ✅ AWS Native Verified / ⚠️ Cross-platform in progress | S3 Tables + PyIceberg + Glue REST + Bedrock | AI-powered metadata catalog. AWS path verified; Databricks/Snowflake paths under validation. [Details](integrations/iceberg-metadata-catalog/docs/poc-results-summary.md) |
| [EMR + Spark](integrations/emr-spark/) | ✅ Functional Verified | Spark SQL + Iceberg | Read + Write-back verified. [10K rows in 16s total (EMR Serverless)](verification-pack/emr-spark/) |
| [Redshift Spectrum](integrations/redshift-spectrum/) | ✅ Functional Verified | External Schema | Same pattern as Athena. [5M rows in 4.3s](verification-pack/redshift-spectrum/) |
| [DuckDB](integrations/duckdb/) | ✅ Functional Verified | Lambda lightweight analytics | Read + Write-back. [5M rows in 779ms, write-back 304ms](integrations/duckdb/) |
| [Manufacturing Data Platform](integrations/manufacturing-data-platform/) | 🔧 Design + PoC | Kafka + ClickHouse + Databricks (streaming) | Edge-to-cloud streaming pipeline (not S3 AP query). Syncs with the [edge project](#related-projects). [Edge ↔ Lakehouse sync](integrations/manufacturing-data-platform/docs/en/14_edge_lakehouse_sync.md) |
| [Dremio](integrations/dremio/) | 🔲 Planned | Arctic Catalog | — |
| [Trino / Starburst](integrations/trino-starburst/) | 🔲 Planned | Hive Connector | — |
| [BigQuery Omni](integrations/bigquery-omni/) | 🔲 Planned | BigLake | Requires GCP environment |
| [Microsoft Fabric](integrations/microsoft-fabric/) | 🔲 Planned | OneLake Shortcut | Requires Azure environment |

> **Key finding**: AWS-native services (Athena, Glue, EMR, Bedrock) work correctly. Third-party platforms require explicit S3 AP ARN configuration: Snowflake uses `AWS_ACCESS_POINT_ARN` (fully resolved), Databricks uses `access_point` field (partially resolved). See [Compatibility Matrix](docs/en/compatibility-matrix.md) for details.

> **Note**: The table above shows FSx for ONTAP S3 Access Point integration status (general). For the S3 Tables / Iceberg Metadata Catalog cross-platform status (Databricks Spark, Snowflake Glue REST, etc.), see [integrations/iceberg-metadata-catalog/README.md](integrations/iceberg-metadata-catalog/README.md#cross-platform-status-tested-2026-05-31-updated-2026-06-01).

</details>

---

## Engine Selection Guide

<details>
<summary>Which engine for which use case? (click to expand)</summary>

| Primary Question | Recommended Engine | Access Pattern | Governance | AI Readiness | PoC Cost (1 day) |
|---|---|---|---|---|---|
| "Cheapest way to query NAS data" | DuckDB Lambda | Zero-copy | None (IAM only) | Discovery / profiling | ~$0.01 |
| "Serverless SQL, no infrastructure" | Athena | Zero-copy | Glue + Lake Formation | Discovery → curated dataset | ~$0.05 |
| "Need Spark ETL with write-back" | EMR Serverless | Zero-copy (read) + write to FSx for ONTAP | IAM | Curated Parquet / Iceberg creation | ~$0.50 |
| "Need DWH JOINs + enterprise governance" | Redshift Spectrum + Lake Formation | Zero-copy | Lake Formation (column/row/tag) | Governed analytics | ~$1.50 |
| "Need AI on NAS data (summarize, RAG, sentiment)" | Snowflake External Table + Cortex | Zero-copy | Snowflake RBAC + Tags | AI-ready (Cortex AI immediate) | ~$5 |
| "Already use Databricks, need full UC + ML" | DataSync → S3 → UC | With S3 sync | Unity Catalog (full) | Full ML/AI (Mosaic AI, Feature Store) | ~$10 |
| "Can we use Delta/Iceberg on FSx for ONTAP?" | No — read from FSx for ONTAP, write to S3 | Read: zero-copy, Write: S3 | Depends on engine | Depends on engine | ~$0.50 |

### When FSx for ONTAP + S3 AP Applies (vs S3-only)

| Consideration | S3 only | FSx for ONTAP + S3 AP |
|---|---|---|
| Existing NFS/SMB workloads | Must migrate or maintain dual paths | No change — existing apps continue on NFS/SMB |
| Storage efficiency | No dedup/compression | ONTAP dedup + compression (1.5-2x typical) |
| Point-in-time recovery | S3 Versioning (per-object, costly at scale) | ONTAP Snapshot (volume-level, instant, space-efficient) |
| Dev/test data provisioning | Full copy required | FlexClone (instant zero-copy clone) |
| Multi-protocol access | S3 only | NFS + SMB + S3 on same data simultaneously |
| Application changes needed | Yes (rewrite to S3 SDK) | No (NFS/SMB unchanged, S3 AP is additive) |

### Open Table Format: Multi-Platform Bridge

For environments using both Snowflake and Databricks, curated datasets can be shared via open Iceberg format:

```
FSx for ONTAP (source) → S3 AP / DataSync → S3 → Snowflake Managed Iceberg Table
                                                          ↓
                                                Same Iceberg on S3
                                                          ↓
                                    Databricks UC / Athena / EMR (read Iceberg)
```

No vendor lock-in. Data ownership retained. Each platform applies its own governance.

</details>

---

## Use Cases

| Industry | Use Case | Key Pattern | Deployment Considerations |
|----------|----------|-------------|--------------------------|
| [Financial Services](use-cases/financial-data-mesh/) | Data Mesh | Pattern D (Data Sharing) | Segregation of duties, per-domain access points, audit retention (7+ years), DR/BCP |
| [Manufacturing](use-cases/manufacturing-iot-lake/) | IoT Data Lake | Pattern C (ETL Pipeline) | OT/IT boundary separation, edge ingestion via NFS, long-term retention (FabricPool) |
| [Healthcare](use-cases/healthcare-research/) | Research Data | Pattern B (Managed Tables) | De-identification pipeline, VPC-origin AP, read-only access, synthetic test data only, BAA |
| [Media](use-cases/media-asset-analytics/) | Asset Analytics | Pattern A (Read-Only) | Large file handling (5 GB upload limit), CloudFront integration for streaming |

---

## Quick Start

<details>
<summary>Prerequisites and deploy commands (click to expand)</summary>

### Prerequisites

- AWS Account with FSx for NetApp ONTAP
- S3 Access Points enabled on FSx for ONTAP SVM
- AWS CLI v2 configured
- Python 3.12+
- **Important**: Analytics platform and FSx for ONTAP must be in the same AWS region.
  See [Region Design Guide](docs/en/region-design-guide.md)

### Deploy Base Infrastructure

```bash
# Set your target region (must match FSx for ONTAP location)
export AWS_REGION=<YOUR_REGION>  # e.g., ap-northeast-1, us-east-1, eu-west-1

# Deploy VPC + FSx for ONTAP + S3 Access Point
aws cloudformation deploy \
  --template-file shared/cloudformation/vpc-networking.yaml \
  --stack-name fsxn-lakehouse-vpc \
  --capabilities CAPABILITY_IAM \
  --region ${AWS_REGION}

aws cloudformation deploy \
  --template-file shared/cloudformation/fsxn-s3ap-base.yaml \
  --stack-name fsxn-lakehouse-base \
  --capabilities CAPABILITY_IAM \
  --region ${AWS_REGION}
```

### Validate S3 AP Access

```bash
python shared/scripts/validate-access.py \
  --access-point-arn arn:aws:s3:${AWS_REGION}:<YOUR_ACCOUNT_ID>:accesspoint/fsxn-lakehouse \
  --region ${AWS_REGION}
```

</details>

---

## Repository Structure

<details>
<summary>Directory layout (click to expand)</summary>
```
fsxn-lakehouse-integrations/
├── README.md                    # This file (English)
├── README-ja.md                 # Japanese version
├── docs/                        # Documentation
│   ├── ja/                      # Japanese docs
│   ├── en/                      # English docs
│   ├── adoption-guide/          # Technical adoption guides (JA/EN pairs)
│   ├── implementation-guide/    # PoC execution guides (JA/EN pairs)
│   └── images/                  # Diagrams
├── shared/                      # Common modules
│   ├── cloudformation/          # Base CFn templates
│   ├── scripts/                 # Utility scripts
│   └── sample-data/             # Sample datasets
├── integrations/                # Per-vendor implementations
│   ├── databricks/
│   ├── snowflake/
│   ├── iceberg/
│   └── ...
├── use-cases/                   # Industry use cases
│   ├── financial-data-mesh/
│   ├── manufacturing-iot-lake/
│   └── ...
└── .github/workflows/           # CI/CD
```

</details>

---

## Technology Stack

<details>
<summary>Languages, frameworks, and tested versions (click to expand)</summary>
- **Infrastructure**: CloudFormation (YAML) + Terraform (Databricks/Snowflake)
- **Scripts**: Python 3.12, Bash
- **Notebooks**: Jupyter / Databricks Notebooks
- **SQL**: Snowflake SQL, Athena SQL, Trino SQL
- **Testing**: pytest, cfn-lint
- **Documentation**: Markdown (bilingual JA/EN)

### Tested With (Iceberg Metadata Catalog)

| Component | Version | Notes |
|-----------|---------|-------|
| Python | 3.12+ | macOS/Linux |
| PyIceberg | 0.7+ (tested 0.11.1) | With `[s3tables]` extra |
| Apache Iceberg | format-version 2 | Position Delete Files for soft delete |
| S3 Tables | GA (2024-12) | Auto-compaction, Iceberg REST endpoint |
| OpenSearch Serverless NextGen | GA (2026-05-28) | Scale-to-zero, kNN vector search |
| Amazon Bedrock | Claude 3 Haiku, Titan Embeddings V2 | Vision classification + 1024-dim embeddings |
| PyArrow | 17.0+ (tested 24.0.0) | Arrow-based Iceberg writes |

</details>

---

## Documentation

<details>
<summary>Full document index (click to expand)</summary>
| Document | Link |
|----------|------|
| **Start Here (Non-Technical)** | [**Plain-Language Business Guide**](docs/en/quickstart-business-guide.md) |
| Architecture | [Architecture](docs/en/architecture.md) |
| Getting Started | [Getting Started](docs/en/getting-started.md) |
| Region Design Guide | [Region Design Guide](docs/en/region-design-guide.md) |
| Supported Regions | [Supported Regions](docs/en/supported-regions.md) |
| Vendor Comparison | [Vendor Comparison](docs/en/vendor-comparison.md) |
| Unstructured Data | [Unstructured Data](docs/en/unstructured-data-access.md) |
| Compatibility Matrix | [Compatibility Matrix](docs/en/compatibility-matrix.md) |
| Recovery Semantics | [Recovery Semantics](docs/en/recovery-semantics.md) |
| Governance & Compliance | [Governance & Compliance](docs/en/governance-and-compliance.md) |
| Zero-Copy Unstructured Data Governance | [Zero-Copy Governance](docs/en/zero-copy-media-governance.md) |
| OpenSharing Integration Analysis | [OpenSharing Analysis](docs/en/opensharing-integration-analysis.md) |
| KPI & Validation | [KPI & Validation](docs/en/kpi-and-validation.md) |
| **FSx for ONTAP → Databricks UC Guide** | [**UC Connection Guide**](docs/en/fsx-ontap-to-databricks-unity-catalog-guide.md) |
| DataSync → S3 Guide | [DataSync Guide](docs/en/datasync-to-s3-guide.md) |
| Kafka-ClickHouse-UC Connectivity | [Kafka-CH-UC Connectivity](docs/en/kafka-clickhouse-unity-catalog-connectivity.md) |
| S3 Annotations Governance | [S3 Annotations Evaluation](docs/en/s3-annotations-governance-evaluation.md) |
| Industry Solution Catalog | [Industry Catalog](docs/en/industry-solution-catalog.md) |
| **Adoption Guide** | |
| Technical Overview | [Technical Overview](docs/adoption-guide/technical-overview.md) |
| Architecture Comparison | [Architecture Comparison](docs/adoption-guide/architecture-comparison.md) |
| Technical FAQ | [Technical FAQ](docs/adoption-guide/technical-faq.md) |
| Cost Estimation | [Cost Estimation](docs/adoption-guide/cost-estimation.md) |
| **Implementation Guide** | |
| PoC Execution Guide | [PoC Execution Guide](docs/implementation-guide/poc-execution-guide.md) |

</details>

---

## Blog Series

<details>
<summary>Published and in-progress blog series (click to expand)</summary>
### Series 1: "FSx for ONTAP S3 Access Points × Lakehouse Deep Dive" (Published)

A 7-part validation series on dev.to:

| Part | Platform | URL |
|:---:|----------|-----|
| 0 | Series Overview — What Works, What Doesn't, and Why | [dev.to](https://dev.to/aws-builders/fsx-for-ontap-s3-access-points-x-lakehouse-what-works-what-doesnt-and-why-1jo3) |
| 1 | Athena — Query NAS Data In Place | [dev.to](https://dev.to/aws-builders/query-nas-data-in-place-with-athena-and-fsx-for-ontap-s3-access-points-3lhh) |
| 2 | Databricks — A Layer-by-Layer Validation of Observed Boundaries | [dev.to](https://dev.to/aws-builders/databricks-and-fsx-for-ontap-s3-access-points-a-layer-by-layer-validation-of-observed-boundaries-p4d) |
| 3 | Snowflake — From 'Access Denied' to Working External Tables | [dev.to](https://dev.to/aws-builders/snowflake-and-fsx-for-ontap-s3-access-points-from-access-denied-to-working-external-tables-9k8) |
| 4 | DuckDB Lambda — Serverless Analytics for $0.00001/Query | [dev.to](https://dev.to/aws-builders/serverless-analytics-on-nas-data-for-000001query-duckdb-lambda-x-fsx-for-ontap-2o5o) |
| 5 | EMR Spark — Read-Write ETL on NAS Data | [dev.to](https://dev.to/aws-builders/read-write-etl-on-nas-data-with-emr-serverless-spark-no-cluster-no-copy-hgm) |
| 6 | Redshift Spectrum + Lake Formation — Enterprise Governance | [dev.to](https://dev.to/aws-builders/redshift-spectrum-lake-formation-enterprise-governance-on-nas-data-2pik) |
| 7 | Table Format Boundaries — Why Delta/Iceberg/Hudi Can't Write | [dev.to](https://dev.to/aws-builders/why-delta-iceberg-and-hudi-cant-write-to-fsx-s3-access-points-and-what-works-instead-5be3) |

### Series 2: "Iceberg Metadata Catalog for Unstructured Data" (In Progress)

AI-powered metadata catalog that makes unstructured files on FSx for ONTAP instantly searchable — without copying to S3.

| Part | Topic | Status |
|:---:|-------|--------|
| 1 | Architecture & PoC Results — From Hours to Seconds | 📝 Draft |
| 2 | AI Enrichment Pipeline — Bedrock Vision + Embeddings | 📝 Draft |
| 3 | Governance & Cross-Platform Access — Lake Formation + OpenSearch | 📝 Draft |

**Key results**: 40 files cataloged in 30s, AI classification at $0.01/file, Athena queries < 2s, vector search with scale-to-zero ($0 idle), full demo in 47 seconds for $0.07.

See: [Architecture](docs/en/iceberg-metadata-catalog.md) | [PoC Results](integrations/iceberg-metadata-catalog/docs/poc-results-summary.md) | [Demo Guide](integrations/iceberg-metadata-catalog/demo/docs/demo-guide.md)

</details>

---

## Related Projects

| Project | Role | Relationship |
|---------|------|--------------|
| [ontap-edge-to-cloud-ai](https://github.com/Yoshiki0705/ontap-edge-to-cloud-ai) | Edge device (Raspberry Pi) → ONTAP → Kafka ingestion | Generates events and payloads consumed by this repo's [Manufacturing Data Platform](integrations/manufacturing-data-platform/). Schema, ClickHouse DDL, and Databricks pipelines are kept in sync — see [Edge ↔ Lakehouse sync](integrations/manufacturing-data-platform/docs/en/14_edge_lakehouse_sync.md). |
| [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | 17 serverless patterns for FSx for ONTAP S3 Access Points | Companion pattern library for the S3 AP integrations above. |

This repository owns the **Kafka + ClickHouse + Databricks** side of the edge-to-cloud architecture; the edge device side lives in `ontap-edge-to-cloud-ai`.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

# FSxN Lakehouse Integrations

🌐 [日本語](docs/ja/architecture.md) | [English](docs/en/architecture.md)

---

## Overview / 概要

Data Lake and Lakehouse platform integrations with **Amazon FSx for NetApp ONTAP (FSx for ONTAP)** via **S3 Access Points**.

Amazon FSx for NetApp ONTAP（FSx for ONTAP）のエンタープライズストレージを S3 Access Points 経由で各 Data Lake / Lakehouse プラットフォームと統合するパターン集です。

---

## Core Value / コアバリュー

| ONTAP Capability | Lakehouse Benefit |
|-----------------|-------------------|
| Deduplication & Compression | Storage cost reduction for similar datasets |
| Snapshot | Point-in-time recovery complementing Delta/Iceberg time travel |
| FlexClone | Instant dev/test dataset provisioning |
| SnapMirror | Cross-region DR for lakehouse data |
| FabricPool Tiering | Automatic cold data offload to S3 |
| Multi-protocol (NFS/SMB/iSCSI/S3) | Unified access from any workload |

---

## Architecture Patterns / アーキテクチャパターン

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

---

## Supported Integrations / 対応プラットフォーム

| Platform | Status | Pattern |
|----------|--------|---------|
| [Databricks](integrations/databricks/) | ✅ Implemented | Unity Catalog + Delta Lake |
| [Snowflake](integrations/snowflake/) | ✅ Implemented | External Stage + Iceberg |
| [Apache Iceberg](integrations/iceberg/) | 🚧 Planned | REST Catalog (vendor-neutral) |
| [AWS Athena](integrations/athena/) | 🚧 Planned | Glue Data Catalog + Serverless |
| [AWS Glue](integrations/glue/) | 🚧 Planned | Crawler + ETL + Medallion |
| [Redshift Spectrum](integrations/redshift-spectrum/) | 🚧 Planned | External Schema |
| [EMR + Spark](integrations/emr-spark/) | 🚧 Planned | Spark SQL + Iceberg |
| [Dremio](integrations/dremio/) | 🚧 Planned | Arctic Catalog |
| [Trino / Starburst](integrations/trino-starburst/) | 🚧 Planned | Hive Connector |
| [BigQuery Omni](integrations/bigquery-omni/) | 🚧 Planned | BigLake |
| [Microsoft Fabric](integrations/microsoft-fabric/) | 🚧 Planned | OneLake Shortcut |
| [DuckDB](integrations/duckdb/) | 🚧 Planned | Lambda lightweight analytics |

---

## Use Cases / ユースケース

| Industry | Use Case | Key Pattern |
|----------|----------|-------------|
| [Financial Services](use-cases/financial-data-mesh/) | Data Mesh | Pattern D (Data Sharing) |
| [Manufacturing](use-cases/manufacturing-iot-lake/) | IoT Data Lake | Pattern C (ETL Pipeline) |
| [Healthcare](use-cases/healthcare-research/) | Research Data | Pattern B (Managed Tables) |
| [Media](use-cases/media-asset-analytics/) | Asset Analytics | Pattern A (Read-Only) |

---

## Quick Start / クイックスタート

### Prerequisites

- AWS Account with FSx for NetApp ONTAP
- S3 Access Points enabled on FSx for ONTAP SVM
- AWS CLI v2 configured
- Python 3.12+

### Deploy Base Infrastructure

```bash
# Deploy VPC + FSx for ONTAP + S3 Access Point
aws cloudformation deploy \
  --template-file shared/cloudformation/vpc-networking.yaml \
  --stack-name fsxn-lakehouse-vpc \
  --capabilities CAPABILITY_IAM \
  --region <YOUR_REGION>

aws cloudformation deploy \
  --template-file shared/cloudformation/fsxn-s3ap-base.yaml \
  --stack-name fsxn-lakehouse-base \
  --capabilities CAPABILITY_IAM \
  --region <YOUR_REGION>
```

### Validate S3 AP Access

```bash
python shared/scripts/validate-access.py \
  --access-point-arn arn:aws:s3:<YOUR_REGION>:123456789012:accesspoint/fsxn-lakehouse \
  --region <YOUR_REGION>
```

---

## Repository Structure / リポジトリ構造

```
fsxn-lakehouse-integrations/
├── README.md                    # This file (bilingual)
├── docs/                        # Documentation
│   ├── ja/                      # Japanese docs
│   ├── en/                      # English docs
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

---

## Technology Stack / 技術スタック

- **Infrastructure**: CloudFormation (YAML) + Terraform (Databricks/Snowflake)
- **Scripts**: Python 3.12, Bash
- **Notebooks**: Jupyter / Databricks Notebooks
- **SQL**: Snowflake SQL, Athena SQL, Trino SQL
- **Testing**: pytest, cfn-lint
- **Documentation**: Markdown (bilingual JA/EN)

---

## License

MIT License - see [LICENSE](LICENSE) for details.

# FSx for ONTAP Lakehouse Integrations

🌐 [日本語](docs/ja/architecture.md) | [English](docs/en/architecture.md)

> **Validation status: Experimental.**
> This repository documents observed validation behavior across analytics and lakehouse engines.
> It is not a production integration pattern, Marketplace listing, or certified partner solution.
> The Databricks Unity Catalog + FSx S3 AP path is currently documented as an observed boundary in this validation.

> **`fsxn-lakehouse-integrations` is a validation framework for testing how different analytics and lakehouse engines interact with FSx for ONTAP S3 Access Points.** Each integration directory contains reproducible evidence, test templates, and observed boundary documentation — not production-ready connectors.

---

## Overview / 概要

**Turn existing enterprise file assets into analytics- and AI-ready data without disrupting NFS/SMB workloads.**

Data Lake and Lakehouse platform integrations with **Amazon FSx for NetApp ONTAP (FSx for ONTAP)** via **S3 Access Points**.

既存のエンタープライズファイル資産を、NFS/SMB ワークロードを中断することなく、分析・AI 対応データに変換します。

Amazon FSx for NetApp ONTAP（FSx for ONTAP）のエンタープライズストレージを S3 Access Points 経由で各 Data Lake / Lakehouse プラットフォームと統合するパターン集です。

---

## Business Outcomes / ビジネス成果

| Outcome / 成果 | Description / 説明 |
|----------------|-------------------|
| **Eliminate data copies** / データコピーの排除 | N redundant copies → 1 authoritative source on FSx for ONTAP |
| **Remove NAS→S3 sync pipelines** / 同期パイプラインの廃止 | No ETL jobs needed to copy file data to S3 for analytics |
| **Accelerate time-to-insight** / インサイトまでの時間短縮 | Days of pipeline setup → hours of direct query via S3 Access Point |
| **Preserve existing NFS/SMB workloads** / 既存ワークロードの維持 | Applications continue writing via NFS/SMB unchanged |
| **Unified governance** / ガバナンスの統一 | Single data location with dual-layer access control (IAM + file system permissions) |
| **Enable AI/ML on file data** / ファイルデータでの AI/ML 活用 | Amazon Bedrock, SageMaker, EMR access existing files via S3 AP without data movement |

FSx for ONTAP S3 Access Points enable S3 API access to file data without data movement, allowing S3-compatible applications and AWS services to directly read and write file data. ([AWS Documentation](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-via-s3-access-points.html))

FSx for ONTAP S3 Access Points により、データ移動なしでファイルデータへの S3 API アクセスが可能になり、S3 互換アプリケーションや AWS サービスがファイルデータを直接読み書きできます。

---

## Core Value / コアバリュー

| ONTAP Capability | Lakehouse Benefit |
|-----------------|-------------------|
| Deduplication & Compression | Storage cost reduction for similar datasets |
| Snapshot | Point-in-time recovery complementing Delta/Iceberg time travel (see [Recovery Semantics](docs/en/recovery-semantics.md)) |
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

| Platform | Verification Status | Pattern | Notes |
|----------|:---:|---------|-------|
| [AWS Athena](integrations/athena/) | ✅ Verified | Glue Data Catalog + Serverless | Read-only. [Benchmark: 54.8 MB/s peak, 5M rows in 2s](verification-pack/athena-parquet-read/) |
| [AWS Glue ETL](integrations/glue/) | ✅ Verified | Crawler + ETL + Medallion | Read + Write-back (Parquet). [64s for 10K row ETL](verification-pack/glue-etl/) |
| [EMR + Spark](integrations/emr-spark/) | ✅ Verified | Spark SQL | Read + Write-back verified. [10K rows in 16s total (EMR Serverless)](verification-pack/emr-spark/) |
| [Redshift Spectrum](integrations/redshift-spectrum/) | ✅ Verified | External Schema | Same pattern as Athena. [5M rows in 4.3s](verification-pack/redshift-spectrum/) |
| [DuckDB](integrations/duckdb/) | ✅ Verified | Lambda lightweight analytics | Read + Write-back. [5M rows in 779ms, write-back 304ms](integrations/duckdb/) |
| [Trino / Starburst](integrations/trino-starburst/) | ✅ Read Verified | Hive Connector | Read verified. [5M rows in 1.5s (Docker single-node)](integrations/trino-starburst/) |
| [Databricks](integrations/databricks/) | ⚠️ Blocked in validation | Unity Catalog + Delta Lake | Session policy does not recognize S3 AP ARN format. Support case filed. |
| [Snowflake](integrations/snowflake/) | ⚠️ Blocked in validation | External Stage | LIST succeeds, GetObject denied. Session policy issue. Support case filed. |
| [Delta Lake OSS](integrations/delta-lake-oss/) | ❌ Write not suitable | delta-rs + Spark | Read works. Write fails (conditional writes not supported). |
| [Apache Iceberg](integrations/iceberg/) | ❌ Write not suitable | REST Catalog | Write fails: S3FileIO cannot handle AP alias for metadata. |
| [Dremio](integrations/dremio/) | 🔲 Planned | Arctic Catalog | — |

> **Key finding**: AWS-native services and open-source engines with path-style S3 access work correctly. Third-party platforms (Snowflake, Databricks) are blocked by session policies that do not recognize S3 Access Point ARN format. Transactional table format writes (Delta, Iceberg, Hudi) are not suitable for this path. See [Compatibility Matrix](docs/en/compatibility-matrix.md) for details.

---

## Use Cases / ユースケース

| Industry | Use Case | Key Pattern | Deployment Considerations |
|----------|----------|-------------|--------------------------|
| [Financial Services](use-cases/financial-data-mesh/) | Data Mesh | Pattern D (Data Sharing) | Segregation of duties, per-domain access points, audit retention (7+ years), DR/BCP |
| [Manufacturing](use-cases/manufacturing-iot-lake/) | IoT Data Lake | Pattern C (ETL Pipeline) | OT/IT boundary separation, edge ingestion via NFS, long-term retention (FabricPool) |
| [Healthcare](use-cases/healthcare-research/) | Research Data | Pattern B (Managed Tables) | De-identification pipeline, VPC-origin AP, read-only access, synthetic test data only, BAA |
| [Media](use-cases/media-asset-analytics/) | Asset Analytics | Pattern A (Read-Only) | Large file handling (5 GB upload limit), CloudFront integration for streaming |

---

## Quick Start / クイックスタート

### Prerequisites

- AWS Account with FSx for NetApp ONTAP
- S3 Access Points enabled on FSx for ONTAP SVM
- AWS CLI v2 configured
- Python 3.12+
- **Important**: Analytics platform and FSx for ONTAP must be in the same AWS region.
  See [Region Design Guide (EN)](docs/en/region-design-guide.md) / [リージョン設計ガイド (JA)](docs/ja/region-design-guide.md)

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

## Documentation / ドキュメント

| Document | 日本語 | English |
|----------|--------|---------|
| Architecture | [アーキテクチャ](docs/ja/architecture.md) | [Architecture](docs/en/architecture.md) |
| Getting Started | [クイックスタート](docs/ja/getting-started.md) | [Getting Started](docs/en/getting-started.md) |
| Region Design Guide | [リージョン設計ガイド](docs/ja/region-design-guide.md) | [Region Design Guide](docs/en/region-design-guide.md) |
| Supported Regions | [対応リージョン](docs/ja/supported-regions.md) | [Supported Regions](docs/en/supported-regions.md) |
| Vendor Comparison | [ベンダー比較](docs/ja/vendor-comparison.md) | [Vendor Comparison](docs/en/vendor-comparison.md) |
| Unstructured Data | [非構造化データ](docs/ja/unstructured-data-access.md) | [Unstructured Data](docs/en/unstructured-data-access.md) |
| Partner Offering | [パートナーオファリング](docs/ja/partner-offering.md) | [Partner Offering](docs/en/partner-offering.md) |
| Compatibility Matrix | [互換性マトリクス](docs/ja/compatibility-matrix.md) | [Compatibility Matrix](docs/en/compatibility-matrix.md) |
| Recovery Semantics | [リカバリセマンティクス](docs/ja/recovery-semantics.md) | [Recovery Semantics](docs/en/recovery-semantics.md) |
| Governance & Compliance | [ガバナンスとコンプライアンス](docs/ja/governance-and-compliance.md) | [Governance & Compliance](docs/en/governance-and-compliance.md) |
| KPI & Validation | [KPI と PoC 検証](docs/ja/kpi-and-validation.md) | [KPI & Validation](docs/en/kpi-and-validation.md) |

---

## License

MIT License - see [LICENSE](LICENSE) for details.

# Iceberg Metadata Catalog for Unstructured Data

🌐 [日本語](README-ja.md) | English

## Overview

An **AI-powered metadata catalog** that makes unstructured files on FSx for ONTAP instantly searchable — without copying data to S3. Uses Apache Iceberg (S3 Tables) as the metadata layer, Bedrock for AI classification, and OpenSearch Serverless NextGen for vector search.

**Key results** (verified 2026-05-31): 40 files cataloged in 30s, AI classification at ~$0.01/file, Athena queries < 2s, full demo in 42 seconds for $0.07.

## Architecture

```
FSx for ONTAP ──S3 Access Point──→ AI Enrichment (Bedrock)
       │                                    │
       │                                    ▼
       │                          S3 Tables (Iceberg)
       │                                    │
       │                          ┌─────────┴─────────┐
       │                          ▼                   ▼
       │                    Athena (SQL)      OpenSearch (kNN)
       │                          │
       │                    Lake Formation (governance)
       │
       └──NFS/SMB──→ Existing applications (unchanged)
```

## Quick Start

```bash
# Check prerequisites first
cd demo/scripts && ./check-prerequisites.sh

# Install dependencies
pip install -r requirements.txt

# Option A: Full demo (requires FSx for ONTAP with S3 Access Point)
cd demo/scripts
./run-demo.sh --ap-alias <your-ap-alias-ext-s3alias>

# Option B: S3-only mode (no FSx required)
# See demo/docs/quickstart-s3-only.md
```

> **Don't have FSx for ONTAP?** Start with [S3-only quickstart](demo/docs/quickstart-s3-only.md).
> **Need infrastructure?** Send [infrastructure-request-template.md](docs/infrastructure-request-template.md) to your platform team.

## Phases (All Verified ✅)

| Phase | Status | Description | Key Evidence |
|-------|:------:|-------------|-------------|
| **Phase 1** | ✅ Verified | S3 Tables + PyIceberg schema + initial scan | 40 files in 3s |
| **Phase 2** | ✅ Verified | FPolicy → SQS → Lambda pipeline | E2E verified, DLQ = 0 |
| **Phase 3** | ✅ Verified | AI enrichment (Bedrock Vision + Titan Embeddings) | invoice classified at 0.95 confidence |
| **Phase 4** | ⚠️ Partial | Cross-platform (Athena ✅, Databricks ⚠️, Snowflake ⚠️) | Tested paths documented |
| **Phase 5** | ✅ Verified | OpenSearch Serverless NextGen (scale-to-zero, kNN) | Score 0.67, cold start 10-30s |
| **Phase 6** | ✅ Verified | PII anonymization (Comprehend EN + Bedrock Claude JA) | 7/7 entities detected |

## Directory Structure

```
integrations/iceberg-metadata-catalog/
├── README.md                              # This file
├── README-ja.md                           # Japanese version
├── requirements.txt                       # Python dependencies (pinned)
├── scripts/
│   ├── create-table-bucket.sh             # S3 Tables setup
│   └── initial-metadata-scan.py           # Initial metadata population
├── lambda/
│   └── metadata-sync-handler/             # FPolicy → SQS → Iceberg sync
├── demo/
│   ├── scripts/                           # Full demo (run-demo.sh + 16 scripts)
│   ├── docs/                              # Demo guide, S3-only quickstart
│   ├── cloudformation/                    # Demo infrastructure stack
│   ├── notebooks/                         # Databricks/Snowflake notebooks
│   └── sample-data/                       # Industry sample data catalog
├── docs/
│   ├── poc-guide.md / poc-guide-ja.md     # PoC deployment guide
│   ├── poc-results-summary.md / -ja.md    # PoC results (1-page summary)
│   └── standards-vs-service-behavior.md   # Iceberg spec vs S3 Tables behavior
├── ops/
│   ├── iceberg-maintenance-runbook.md     # Production maintenance guide
│   └── athena-named-queries/              # Curated SQL views (latest_records, PII coverage)
├── schema/
│   └── extensions/                        # Domain metadata extensions (manufacturing, etc.)
├── use-cases/                             # Industry-specific use cases (20 industries)
│   ├── README.md                          # Use case selection guide
│   ├── _shared/                           # Common schema, prompts, demo framework
│   ├── manufacturing/                     # UC3: CAD, QC, maintenance
│   ├── financial/                         # UC2: IDP, KYC/AML
│   ├── healthcare/                        # UC5: DICOM, PHI
│   ├── ... (20 industries total)          # See use-cases/README.md
│   └── sap-erp/                           # UC19: ERP document management
├── databricks/
│   ├── uc-foreign-iceberg-validation.md   # UC Foreign Catalog validation plan
│   ├── coexistence-roadmap.md             # AWS + Databricks phased integration
│   └── audit-correlation-guide.md         # Cross-platform audit correlation
├── snowflake/
│   ├── glue-rest-vended-credentials-validation.md  # Glue REST credential vending validation
│   ├── external-stage-fsx-s3ap-validation.md       # External Stage with FSx S3 AP
│   ├── path-decision-guide.md                      # Snowflake integration path decision
│   └── troubleshooting-guide.md                    # Troubleshooting guide (EN/JA)
├── lakehouse-tools/
│   └── tool-compatibility-matrix.yaml              # Multi-engine compatibility matrix
├── verification-evidence/
│   ├── evidence-record.yaml               # What was validated vs projected
│   ├── cost-assumptions.yaml              # All pricing assumptions
│   ├── cross-platform-compatibility.yaml  # Tested paths per platform
│   └── 2026-05-31/                        # Detailed test results
└── cloudformation/
    └── metadata-sync-pipeline.yaml        # Production pipeline stack
```

## S3 Tables Access Paths

| Access path | Best for | Governance | Verified |
|---|---|---|:---:|
| S3 Tables REST (`s3tables.<region>.amazonaws.com/iceberg`) | Direct PoC | IAM + S3 Tables | ✅ |
| AWS Glue REST (`glue.<region>.amazonaws.com/iceberg`) | Production | IAM + Lake Formation | ✅ |
| Athena via Glue federated catalog | SQL analytics | Lake Formation | ✅ |

> For production, use the **AWS Glue Iceberg REST endpoint** with Lake Formation. See [docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-tables-integrating-glue-endpoint.html).

## Cross-Platform Status (Tested 2026-05-31, Updated 2026-06-01)

| Platform | Status | Path |
|----------|:------:|------|
| Athena | ✅ | Glue federated catalog |
| PyIceberg | ✅ | S3 Tables REST + Glue REST |
| EMR Spark | ✅ Verified | Glue Iceberg REST via EMR Serverless 7.13.0; SHOW NAMESPACES/TABLES/SELECT all work |
| Databricks SQL Warehouse | ⚠️ | `iceberg_rest` connection type not supported in tested path |
| Databricks UC Audit | ✅ | External engine access fully logged in `system.access.audit` |
| Databricks Spark | ❌ | UC blocks external catalog registration via spark.conf.set; UC Foreign Catalog required |
| Databricks UC Foreign Catalog | 🔄 | Follow-up submitted to support (2026-06-01); required path for governed access |
| Databricks Delta Sharing | ❌ | Sharing server uses same UC credentials; cannot bypass S3 AP session policy |
| Databricks NFS → UC Volume | ❌ | Cloud storage URIs only; NFS/FUSE mount paths not supported |
| Snowflake (Glue REST) | ❌ Blocked | Glue REST does not implement credential vending (`/credentials` returns UnknownOperationException) |
| Snowflake (S3 Tables direct) | ⚠️ | Not a supported catalog type in tested path |
| Snowflake External Stage | ✅ | FSx S3 AP works (LIST, SELECT, COPY, TO_FILE + Cortex AI all verified) |

Details: [cross-platform-compatibility.yaml](verification-evidence/cross-platform-compatibility.yaml)

## Documentation

| Document | EN | JA |
|----------|----|----|
| Architecture | [EN](../../docs/en/iceberg-metadata-catalog.md) | [JA](../../docs/ja/iceberg-metadata-catalog.md) |
| **Industry Use Cases** | [EN](docs/industry-use-cases.md) | [JA](docs/industry-use-cases-ja.md) |
| PoC Results Summary | [EN](docs/poc-results-summary.md) | [JA](docs/poc-results-summary-ja.md) |
| PoC Guide | [EN](docs/poc-guide.md) | [JA](docs/poc-guide-ja.md) |
| Infrastructure Request | [EN](docs/infrastructure-request-template.md) | [JA](docs/infrastructure-request-template-ja.md) |
| Demo Guide | [EN](demo/docs/demo-guide.md) | [JA](demo/docs/demo-guide-ja.md) |
| S3-Only Quickstart | [EN](demo/docs/quickstart-s3-only.md) | [JA](demo/docs/quickstart-s3-only-ja.md) |
| Iceberg Spec vs S3 Tables | [EN](docs/standards-vs-service-behavior.md) | — |
| Maintenance Runbook | [EN](ops/iceberg-maintenance-runbook.md) | — |
| Snowflake Troubleshooting | [EN](snowflake/troubleshooting-guide.md) | [JA](snowflake/troubleshooting-guide-ja.md) |

## Blog Series

- **Part 1**: Architecture & PoC Results — From Hours to Seconds
- **Part 2**: AI Enrichment Pipeline — Bedrock Vision + OpenSearch NextGen
- **Part 3**: Governance & Cross-Platform Access

## Key Constraints

- Use **lowercase** table, namespace, and column names (S3 Tables + Athena requirement)
- Iceberg does not enforce primary-key uniqueness — use `ops/athena-named-queries/latest_records.sql`
- Lake Formation column exclusion grants: observed limitation on S3 Tables federated catalog path
- S3 Tables auto-compaction is service-managed — verify behavior for your retention needs

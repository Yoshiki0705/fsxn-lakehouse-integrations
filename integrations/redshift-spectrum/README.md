# Redshift Spectrum Integration

🌐 **English** | [日本語](docs/ja/README.md)

## Overview

Query data on Amazon FSx for NetApp ONTAP directly from Amazon Redshift Spectrum
using Glue Data Catalog and S3 Access Points. Combines DWH local tables with
external FSxN data in federated queries.

## Architecture

```
Redshift Serverless (DWH)
    │
    ├── Local tables (Redshift-managed storage)
    │
    └── External Schema (Glue Data Catalog)
            │
            └── S3 Access Point (internet origin) ──→ FSx for ONTAP Volume
                                                        ├── sensor_data (Parquet, 10K rows)
                                                        └── sensor_benchmark (Parquet, 5M rows)
```

## Key Points

- **Same pattern as Athena**: Internet-origin S3 AP + Glue Catalog
- **Federated queries**: JOIN local Redshift tables with external FSxN data
- **Predicate pushdown**: Spectrum pushes filters to S3 layer (reduces data scanned)
- **No session policy issues**: AWS-native service, direct IAM role (no third-party intermediary)

## Status: ✅ Functional Verified (2026-05-23)

Verified with Redshift Serverless (8 RPU) + Spectrum on FSx for ONTAP S3 AP (internet-origin).
- COUNT(*) 10K rows: 3.2s
- GROUP BY + AVG: 2.6s
- COUNT(*) 5M rows: 4.3s
- Same pattern as Athena (Glue Catalog + internet-origin AP + IAM role)

## Quick Start

```bash
# 1. Deploy Redshift Serverless + IAM Role
./deploy.sh

# 2. Create external schema and run queries
python scripts/run_spectrum_queries.py

# 3. Cleanup (important — Redshift Serverless costs ~$2.88/hr at 8 RPU)
./scripts/cleanup.sh
```

## Directory Structure

```
integrations/redshift-spectrum/
├── README.md                          ← This file
├── template.yaml                      ← CloudFormation (Redshift Serverless + IAM)
├── deploy.sh                          ← Deployment automation
├── params.example.json                ← Parameter template
├── sql/
│   ├── 01_create_external_schema.sql  ← External schema pointing to Glue Catalog
│   ├── 02_spectrum_queries.sql        ← SELECT, GROUP BY, aggregation queries
│   ├── 03_federated_join.sql          ← JOIN local + external tables
│   └── 04_pushdown_verification.sql   ← SVL_S3QUERY_SUMMARY analysis
├── scripts/
│   ├── run_spectrum_queries.py        ← Query execution + metrics
│   ├── validate_connectivity.py       ← Connectivity validation
│   └── cleanup.sh                     ← Resource cleanup (delete Serverless)
└── tests/results/                     ← Query metrics output
```

## Cost

Redshift Serverless has a minimum of 8 RPU (~$2.88/hr). Delete promptly after verification.

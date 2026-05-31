# Cross-Platform Access Configuration

🌐 [日本語](README-ja.md) | English

## Overview

This directory contains platform-specific configurations for accessing the Iceberg Metadata Catalog from multiple analytics engines. All platforms access the **same underlying metadata** via the Iceberg REST endpoint or Glue Catalog integration.

## Platform Access Paths

```
                    S3 Tables (Iceberg Metadata)
                              │
              ┌───────────────┼───────────────┐
              │               │               │
    Iceberg REST        Glue Catalog    Snowflake Managed
    endpoint            (SageMaker      Iceberg (copy)
              │         Lakehouse)            │
              │               │               │
    ┌─────────┤         ┌─────┤         ┌─────┤
    │         │         │     │         │     │
Databricks  EMR     Athena  Redshift  Snowflake  External
(External   Spark   SQL     Spectrum  (Cortex    engines
 Catalog)                             Search)    (via Horizon)
```

## Quick Reference

| Platform | Access Method | Governance | Setup File |
|----------|-------------|-----------|-----------|
| **Athena** | Glue Catalog (SageMaker Lakehouse) | Lake Formation LF-Tags | `athena-emr/athena-queries.sql` |
| **EMR Spark** | Iceberg REST endpoint (direct) | Lake Formation | `athena-emr/emr-spark-access.py` |
| **Databricks** | External Catalog (Iceberg REST) | Unity Catalog + Lake Formation | `databricks/external-catalog-setup.py` |
| **Snowflake** | Managed Iceberg Table (copy) | Horizon Row Access Policy | `snowflake/managed-iceberg-setup.sql` |
| **Redshift Spectrum** | Glue Catalog | Lake Formation | Same as Athena |

## Governance Enforcement Matrix

| Query Engine | Lake Formation | Horizon Catalog | Unity Catalog |
|-------------|:-:|:-:|:-:|
| Athena | ✅ Enforced | — | — |
| EMR Spark | ✅ Enforced | — | — |
| Redshift Spectrum | ✅ Enforced | — | — |
| Databricks (via External Catalog) | ✅ Enforced | — | ✅ Supplementary |
| Snowflake (internal) | — | ✅ Enforced | — |
| External engines (via Horizon REST) | — | ✅ Enforced | — |

## Key Differences

| Aspect | S3 Tables (Primary) | Snowflake Managed Iceberg |
|--------|--------------------|--------------------------| 
| Data location | S3 Tables table bucket | Customer S3 bucket (Snowflake-managed) |
| Update mechanism | Lambda writes via PyIceberg | COPY INTO / INSERT |
| Latency | Real-time (FPolicy pipeline) | Batch (Task + COPY INTO) |
| Governance | Lake Formation | Horizon Catalog |
| External engine access | Iceberg REST endpoint | Horizon REST Catalog |
| Best for | AWS-native engines | Snowflake + external sharing |

## Prerequisites

### Common
- S3 Tables table bucket created (Phase 1)
- Metadata records populated (Phase 1 or Phase 2)
- AI enrichment completed for target records (Phase 3)

### Athena / EMR
- S3 Tables registered in Glue Catalog via SageMaker Lakehouse
- Lake Formation permissions configured
- Athena workgroup with results location

### Databricks
- Unity Catalog enabled workspace
- IAM role with cross-account s3tables:* permissions
- External Catalog feature enabled (check Databricks account settings)

### Snowflake
- Iceberg Tables feature enabled
- External Volume configured with S3 write access
- Cortex Search available in account region

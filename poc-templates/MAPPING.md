🌐 **English** | [日本語](MAPPING-ja.md)

# PoC Templates ↔ Documentation Mapping

## Purpose

This file maps each PoC template module to the corresponding detailed documentation, demo guides, blog articles, and verification evidence in this repository.

---

## Module → Documentation Map

| PoC Module | Detailed Guide | Demo Guide | Blog Article | Verification Evidence |
|---|---|---|---|---|
| **02-athena-quickstart** | [Athena README](../integrations/athena/README.md) | — | [Part 1: Query NAS Data In Place](https://dev.to/aws-builders/query-nas-data-in-place-with-athena-and-fsx-for-ontap-s3-access-points-3lhh) | [verification-pack/athena-parquet-read/](../verification-pack/athena-parquet-read/) |
| **03-snowflake-integration** | [Snowflake README](../integrations/snowflake/README.md) | [AI Demo Guide](../integrations/snowflake/docs/en/ai-demo-guide.md) | [Part 3: From Access Denied to Working](https://dev.to/aws-builders/snowflake-and-fsx-for-ontap-s3-access-points-from-access-denied-to-working-external-tables-9k8) | [verification-pack/snowflake/](../verification-pack/snowflake/) |
| **04-databricks-integration** | [Databricks README](../integrations/databricks/README.md) | [AI Demo Guide](../integrations/databricks/docs/en/ai-demo-guide.md) | [Part 2: Layer-by-Layer Validation](https://dev.to/aws-builders/databricks-and-fsx-for-ontap-s3-access-points-a-layer-by-layer-validation-of-observed-boundaries-p4d) | [verification-pack/databricks/](../verification-pack/databricks/) |
| **05-emr-spark-etl** | [EMR Spark README](../integrations/emr-spark/README.md) | — | [Part 5: Read-Write ETL](https://dev.to/aws-builders/read-write-etl-on-nas-data-with-emr-serverless-spark-no-cluster-no-copy-hgm) | [verification-pack/emr-spark/](../verification-pack/emr-spark/) |
| **06-duckdb-lambda** | [DuckDB README](../integrations/duckdb/README.md) | — | [Part 4: $0.00001/Query](https://dev.to/aws-builders/serverless-analytics-on-nas-data-for-000001query-duckdb-lambda-x-fsx-for-ontap-2o5o) | [verification-pack/duckdb-local/](../verification-pack/duckdb-local/) |
| **07-governance** | [Governance Guide](../docs/en/governance-and-compliance.md) | — | [Part 6: Enterprise Governance](https://dev.to/aws-builders/redshift-spectrum-lake-formation-enterprise-governance-on-nas-data-2pik) | [verification-pack/redshift-spectrum/](../verification-pack/redshift-spectrum/) |

---

## Cross-Cutting Documentation

| Topic | Document | Relevance to PoC |
|-------|----------|-----------------|
| Compatibility Matrix | [docs/en/compatibility-matrix.md](../docs/en/compatibility-matrix.md) | Which operations work on which engine |
| Vendor Comparison | [docs/en/vendor-comparison.md](../docs/en/vendor-comparison.md) | Engine selection guidance |
| Partner Offering | [docs/en/partner-offering.md](../docs/en/partner-offering.md) | Sales positioning and anti-patterns |
| DataSync Guide | [docs/en/datasync-to-s3-guide.md](../docs/en/datasync-to-s3-guide.md) | Module 04 (Databricks) sync mechanism |
| Unstructured Data | [docs/en/unstructured-data-access.md](../docs/en/unstructured-data-access.md) | Image/PDF/video access patterns |
| Region Design | [docs/en/region-design-guide.md](../docs/en/region-design-guide.md) | Same-region requirement |
| Networking | [docs/en/fsxn-s3ap-networking.md](../docs/en/fsxn-s3ap-networking.md) | VPC/Internet origin, DNS/AD issues |
| Recovery Semantics | [docs/en/recovery-semantics.md](../docs/en/recovery-semantics.md) | Snapshot + table format recovery |

---

## Snowflake-Specific Documentation

| Document | Content | PoC Module |
|----------|---------|-----------|
| [Internal Table Ingestion Guide](../integrations/snowflake/docs/en/internal-table-ingestion-guide.md) | When COPY INTO is required, Dynamic Table, Managed Iceberg | 03 |
| [AI Demo Guide](../integrations/snowflake/docs/en/ai-demo-guide.md) | Cortex AI functions, Vision AI, Cortex Search (RAG) | 03 |
| [Delta Sharing Guide](../integrations/databricks/docs/en/delta-sharing-volume-guide.md) | Cross-platform data sharing patterns | 03 + 04 |

---

## Databricks-Specific Documentation

| Document | Content | PoC Module |
|----------|---------|-----------|
| [AI Demo Guide](../integrations/databricks/docs/en/ai-demo-guide.md) | ai_query, ai_parse_document, Volume Sharing | 04 |
| [Delta Sharing Guide](../integrations/databricks/docs/en/delta-sharing-volume-guide.md) | Pattern A/B/C for FSx data sharing | 04 |
| [DataSync Guide](../docs/en/datasync-to-s3-guide.md) | FSx → S3 sync for UC | 04 |

---

## Script → Source Mapping

| PoC Script | Full Implementation | Notes |
|---|---|---|
| `06-duckdb-lambda/handler.py` | [integrations/duckdb/lambda/handler.py](../integrations/duckdb/lambda/handler.py) | PoC version is simplified; full version has metrics, error handling |
| `06-duckdb-lambda/template.yaml` | [integrations/duckdb/template.yaml](../integrations/duckdb/template.yaml) | PoC version is minimal; full version has all parameters |
| `05-emr-spark-etl/spark-job.py` | — (PoC-specific) | Based on blog Part 5 validation script |
| `04-databricks-integration/datasync-task.yaml` | — (PoC-specific) | Based on [DataSync Guide](../docs/en/datasync-to-s3-guide.md) |
| `07-governance/lakeformation-setup.sh` | — (PoC-specific) | Based on blog Part 6 validation |
| `02-athena-quickstart/sample-queries.sql` | — (PoC-specific) | Based on blog Part 1 validation |
| `03-snowflake-integration/*.sql` | — (PoC-specific) | Based on blog Part 3 validation |

---

## Evidence → PoC Validation Mapping

After running a PoC module, record evidence in the same format as [verification-pack/](../verification-pack/):

```yaml
# Example: verification-pack/<engine>/evidence/<date>/evidence-record.yaml
verification_id: poc-<customer>-<engine>-<date>
date: "YYYY-MM-DD"
engineer: <name>
platform: <engine>
results:
  read_test:
    status: SUCCESS/FAILED
    duration_ms: <value>
    rows: <count>
  write_test:
    status: SUCCESS/FAILED/NOT_TESTED
  governance_test:
    status: SUCCESS/FAILED/NOT_TESTED
conclusion: |
  <summary of findings>
```

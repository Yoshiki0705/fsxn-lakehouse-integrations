# Apache Iceberg Integration

🌐 **English** | [日本語](docs/ja/README.md)

> **Verification Status: ✅ Read Verified / ❌ Write Failed**
> - Iceberg **read** via PyIceberg + S3 Tables REST Catalog: ✅ (881ms scan, 23-field schema, SigV4 auth)
> - Iceberg **write** (CREATE TABLE) on FSx for ONTAP S3 AP: ❌ NullPointerException — S3FileIO cannot handle AP alias for metadata commit
> - For full metadata catalog architecture, see [`integrations/iceberg-metadata-catalog/`](../iceberg-metadata-catalog/)

## Overview

Vendor-neutral Apache Iceberg table management with Amazon FSx for NetApp ONTAP (FSx for ONTAP).
Uses REST Catalog for metadata management, accessible from any Iceberg-compatible engine.

## Architecture

```
Any Engine (Spark/Trino/Flink/Databricks/Snowflake)
    │
    ├── Iceberg REST Catalog (S3 Tables)  ──→  Managed Iceberg tables (metadata)
    │                                              ↓ file_path reference
    └── S3 Access Point ──→ FSx for ONTAP Volume (raw data files)
```

## Verification Results (2026-05-24)

| Operation | Status | Details |
|-----------|:---:|---------|
| PyIceberg + S3 Tables REST endpoint | ✅ | Schema (23 fields), namespace listing, data scan (881ms). SigV4 auth required |
| Iceberg READ (pre-existing table, metadata in Glue) | ✅ | delta-rs/PyIceberg reads Iceberg metadata files via GetObject on S3 AP |
| Iceberg WRITE (CREATE TABLE via Spark + S3FileIO) | ❌ | NullPointerException during metadata commit — S3FileIO cannot resolve AP alias |
| Iceberg WRITE (CREATE TABLE via Spark + S3A) | ❌ | S3A FileSystem does not support AP aliases |
| Glue Catalog database creation | ✅ | `glue:CreateDatabase` works |

### Root Cause (Write Failure)

Iceberg's `S3FileIO` attempts to write metadata files (`metadata.json`) to the warehouse path on FSx for ONTAP S3 AP. The commit phase fails because:

1. S3FileIO does not correctly handle S3 AP alias as bucket name
2. The metadata write requires conditional writes (conflict detection) which return `501 Not Implemented` on FSx for ONTAP S3 AP
3. Same root cause as Delta Lake and Hudi — see [Part 7 (Table Format Boundaries)](../../docs/en/fsx-ontap-to-databricks-unity-catalog-guide.md)

### Recommended Pattern

**Separate metadata and data layers:**

```
Iceberg metadata   →  Standard S3 bucket (or S3 Tables)
Iceberg data files →  FSx for ONTAP S3 AP (read path)
                      OR standard S3 (write path)
```

For full implementation of this pattern, see [`integrations/iceberg-metadata-catalog/`](../iceberg-metadata-catalog/) — the metadata catalog architecture that uses S3 Tables for Iceberg metadata while keeping raw files on FSx for ONTAP.

## Data Format Support

| Format | Read via S3 AP | Write via S3 AP | Notes |
|--------|:---:|:---:|-------|
| Parquet (flat) | ✅ | ✅ | PutObject works for flat files |
| Parquet (Iceberg table) | ✅ | ❌ | Read works; write requires metadata commit |
| Iceberg metadata JSON | ✅ (GetObject) | ❌ | Metadata read works; commit write fails |

## Unstructured Data Support

Apache Iceberg is a table format for structured data. It cannot store or query unstructured data directly. However, Iceberg tables can manage **metadata about unstructured files** with full ACID guarantees, time travel, and schema evolution.

```sql
-- Manage unstructured file metadata in an Iceberg table
CREATE TABLE file_catalog (
    file_path STRING,
    file_type STRING,
    file_size BIGINT,
    last_modified TIMESTAMP,
    classification STRING,
    embedding BINARY,
    tags MAP<STRING, STRING>
) USING iceberg
PARTITIONED BY (file_type, days(last_modified));
```

This is the core pattern implemented in [`integrations/iceberg-metadata-catalog/`](../iceberg-metadata-catalog/).

## ONTAP Value for Iceberg

| Feature | Benefit |
|---------|---------|
| Snapshot | Recover entire Iceberg table state (metadata + data files) |
| FlexClone | Test schema/partition evolution on clone before production |
| Deduplication | Iceberg compaction creates duplicate blocks → dedup saves space |
| FabricPool | Old snapshots/partitions auto-tier to S3 |
| S3 AP | Read path for Iceberg data files without S3 copy |

## Related Documents

| Document | Description |
|----------|-------------|
| [Iceberg Metadata Catalog](../iceberg-metadata-catalog/) | Full implementation: FPolicy + S3 Tables + AI enrichment |
| [Iceberg Metadata Catalog (docs)](../../docs/en/iceberg-metadata-catalog.md) | Architecture deep-dive |
| [Part 7: Table Format Boundaries](../../blog/en/part7-table-format-boundaries.md) | Why Delta/Iceberg/Hudi writes fail on S3 AP |
| [Verification Evidence](../../verification-pack/iceberg/) | Raw test results |

## Evidence

- [`verification-pack/iceberg/evidence/2026-05-24/`](../../verification-pack/iceberg/evidence/2026-05-24/) — Iceberg write failure evidence (NPE)
- [`verification-pack/opensharing-sts-vending/`](../../verification-pack/opensharing-sts-vending/) — Iceberg metadata GetObject confirmed via credential vending

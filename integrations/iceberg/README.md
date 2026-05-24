# Apache Iceberg Integration

🌐 **English** | [日本語](docs/ja/README.md)

## Overview

Vendor-neutral Apache Iceberg table management on Amazon FSx for NetApp ONTAP (FSx for ONTAP).
Uses REST Catalog for metadata management, accessible from any Iceberg-compatible engine.

## Architecture

```
Any Engine (Spark/Trino/Flink/Databricks/Snowflake)
    │
    └── REST Catalog (Lambda/ECS)
            │
            └── S3 Access Point ──→ FSx for ONTAP Volume (Parquet data + Iceberg metadata)
```

## Status: 🚧 Planned

## Planned Content

- [ ] CloudFormation template (REST Catalog on Lambda/ECS)
- [ ] Iceberg REST Catalog configuration
- [ ] Sample table creation scripts
- [ ] Multi-engine access examples (Spark, Trino, Databricks, Snowflake)
- [ ] Documentation (JA/EN)
- [ ] E2E verification tasks

## Unstructured Data Support

| Format | Support | Access Method | Use Case |
|--------|:---:|--------------|----------|
| Images (JPEG, PNG, TIFF) | ❌ | N/A (structured table format) | — |
| Video (MP4, MOV) | ❌ | N/A | — |
| Documents (PDF, DOCX) | ❌ | N/A | — |
| Audio (WAV, MP3) | ❌ | N/A | — |
| Binary / Archives | ❌ | N/A | — |

Apache Iceberg is a table format for structured data (Parquet-based tables). It cannot store or query unstructured data directly. However, Iceberg tables can be used to manage metadata about unstructured files with full ACID guarantees, time travel, and schema evolution.

**Metadata management pattern:**
```sql
-- Manage unstructured file metadata in an Iceberg table
CREATE TABLE file_catalog (
    file_path STRING,
    file_type STRING,
    file_size BIGINT,
    last_modified TIMESTAMP,
    processed BOOLEAN,
    tags MAP<STRING, STRING>
) USING iceberg
PARTITIONED BY (file_type, days(last_modified));

-- Time travel to view past catalog state
SELECT * FROM file_catalog VERSION AS OF 5;
```

## ONTAP Value for Iceberg

| Feature | Benefit |
|---------|---------|
| Snapshot | Recover entire Iceberg table state (metadata + data files) |
| FlexClone | Test schema/partition evolution on clone before production |
| Deduplication | Iceberg compaction creates duplicate blocks → dedup saves space |
| FabricPool | Old snapshots/partitions auto-tier to S3 |

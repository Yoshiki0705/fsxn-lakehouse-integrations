🌐 **English** | [日本語](../ja/unity-catalog-integration.md)

# Unity Catalog Integration Details

## Overview

Databricks Unity Catalog provides a unified governance and access control layer.
By registering FSx for ONTAP as an External Location, Unity Catalog governance features
apply to data stored on FSx for ONTAP.

## Unity Catalog Object Hierarchy

```
Metastore
└── Catalog: fsxn_lakehouse
    ├── Schema: bronze
    │   ├── Table: transactions (External, Parquet)
    │   ├── Table: customers_csv (External, CSV)
    │   └── Table: iot_sensors (External, Parquet, Partitioned)
    ├── Schema: silver
    │   ├── Table: orders (Managed, Delta Lake)
    │   └── Table: products (Managed, Iceberg)
    ├── Schema: gold
    │   └── Table: daily_revenue (Managed, Delta Lake)
    └── Schema: features
        └── Table: customer_features (Managed, Delta Lake)
```

## Storage Credential Flow

```
Databricks Control Plane
    │
    │ AssumeRole (with ExternalId)
    ▼
IAM Role: fsxn-lakehouse-databricks-s3-role
    │
    │ S3 API calls
    ▼
S3 Access Point: fsxn-databricks-ap
    │
    │ VPC-scoped access
    ▼
FSx for NetApp ONTAP Volume
```

### Security Layers

1. **Unity Catalog ACL**: User/group-level table access control
2. **IAM Role**: AWS-level authentication (protected by External ID)
3. **S3 AP Policy**: Access point-level policy
4. **VPC Restriction**: Network-level restriction
5. **ONTAP Export Policy**: Volume-level access control

## External Table vs Managed Table

### External Table (Pattern A: Read-Only)

```sql
CREATE TABLE fsxn_lakehouse.bronze.raw_data
USING PARQUET
LOCATION 's3://<s3ap-alias>/bronze/raw_data/'
```

- Data resides on FSx for ONTAP (not managed by Databricks)
- DROP TABLE does not delete data
- Same data accessible via NFS/SMB
- Ideal for analyzing existing data

### Managed Table (Pattern B: Read-Write)

```sql
CREATE TABLE fsxn_lakehouse.silver.processed_data
USING DELTA
LOCATION 's3://<s3ap-alias>/silver/processed_data/'
```

- Databricks manages data lifecycle
- Delta Lake / Iceberg format
- ACID transaction support
- Time Travel + ONTAP Snapshot combination

## Performance Optimization

### Recommended Settings

| Setting | Value | Reason |
|---------|-------|--------|
| File size | 128MB-256MB | Optimal I/O size for FSx for ONTAP |
| Partitioning | Date-based | Compatible with FabricPool tiering |
| Compression | ZSTD | High ratio + complements ONTAP compression |
| Delta OPTIMIZE | Weekly | Small file consolidation |

### FSx for ONTAP Throughput Considerations

- Adjust cluster size based on FSx for ONTAP throughput capacity
- Limit parallelism for large queries (`spark.sql.shuffle.partitions`)
- Leverage caching to reduce FSx for ONTAP read operations

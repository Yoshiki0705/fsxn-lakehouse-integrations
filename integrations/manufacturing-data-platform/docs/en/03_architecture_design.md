# Architecture Design

🌐 **English** | [日本語](../ja/03_architecture_design.md)

---

## Architecture Decision Records

This design is governed by the following ADRs (see [docs/adr/](../adr/README.md) for details):

| ADR | Decision |
|-----|----------|
| [ADR-001](../adr/ADR-001.md) | Use Kafka as the factory event backbone |
| [ADR-002](../adr/ADR-002.md) | Use ClickHouse for real-time operational analytics |
| [ADR-003](../adr/ADR-003.md) | Use FSx for ONTAP as payload storage for large unstructured data |
| [ADR-004](../adr/ADR-004.md) | Avoid direct dependency on S3 Access Points for Databricks integration |
| [ADR-005](../adr/ADR-005.md) | Use metadata/payload separation for large files |

## Open Design Items (from the Design Analysis)

The following items were identified as **Must Fix** by the
[initial design analysis](07_initial_design_analysis.md) — a structured self-review
against role-based archetype checklists, not a review by external experts — and
will be addressed in the PoC design phase:

| Item | Status | Task |
|------|--------|------|
| ClickHouse deployment model (Cloud / BYOC / self-managed) | Not yet designed | TSK-001 |
| Edge buffering and failure recovery design | Not yet designed | TSK-002 |
| Kafka → ClickHouse connector specification | Not yet designed | TSK-003 |

---

## DES-001: System Architecture Overview

### Component Responsibilities

| Component | Responsibility | Owns |
|-----------|---------------|------|
| Amazon MSK (Kafka) | Event backbone | Message delivery, ordering, replay |
| ClickHouse | Real-time operational analytics | Sub-second queries, time-series aggregation |
| FSx for ONTAP | Payload storage | Documents, images, video, cold data |
| Databricks | Governed analytics & AI | Curated Delta tables, ML/AI workflows |
| Unity Catalog | Data governance | Metadata, permissions, lineage, audit |
| Native Amazon S3 | Delta Lake physical storage | Parquet files, transaction logs |

### DES-002: Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EDGE / FACTORY LAYER                         │
├─────────────────────────────────────────────────────────────────────┤
│  Sensors   Quality Systems   Cameras   PLCs   SCADA   MES           │
│     │           │               │       │      │       │            │
│     └───────────┴───────────────┴───────┴──────┴───────┘            │
│                              │                                       │
│              ┌───────────────┼───────────────┐                      │
│              ↓                               ↓                      │
│     MQTT/Kafka Producer              File Transfer Agent             │
│     (structured events)              (large payloads)                │
└──────────────┬───────────────────────────────┬──────────────────────┘
               │                               │
               ↓                               ↓
┌──────────────────────────┐    ┌──────────────────────────┐
│      Amazon MSK          │    │     FSx for ONTAP        │
│      (Kafka)             │    │     (Payload Store)      │
│                          │    │                          │
│  Topics:                 │    │  Protocols:              │
│  - sensor-data           │    │  - NFS (PLC/SCADA)      │
│  - quality-events        │    │  - SMB (Windows)        │
│  - document-metadata     │    │  - ONTAP S3 (apps)      │
│  - image-metadata        │    │                          │
│  - system-alerts         │    │  Storage:               │
│                          │    │  - /images/             │
│                          │    │  - /videos/             │
│                          │    │  - /documents/          │
│                          │    │  - /clickhouse-cold/    │
└──────────┬───────────────┘    └──────────────────────────┘
           │                               ↑
           ├──────────────────┐            │ (S3-compatible tiering)
           ↓                  ↓            │
┌─────────────────────┐  ┌────────────────────────────────┐
│    ClickHouse       │  │       Databricks               │
│    (Real-Time)      │──┘       (Governed Analytics)     │
│                     │  │                                │
│  Kafka Engine:      │  │  Structured Streaming:         │
│  - Ingests events   │  │  - Reads Kafka topics          │
│  - MergeTree tables │  │  - Writes Delta tables         │
│  - Materialized     │  │  - Exactly-once processing     │
│    views            │  │                                │
│  - S3 cold tier     │  │  Unity Catalog:                │
│    (→ ONTAP S3)     │  │  - Governs Delta tables        │
│                     │  │  - Lineage tracking            │
│  Dashboards:        │  │  - Access control              │
│  - OEE metrics      │  │                                │
│  - Quality trends   │  │  Delta Tables on native S3:    │
│  - Alerts           │  │  - manufacturing.sensor_data   │
│                     │  │  - manufacturing.quality_events│
└─────────────────────┘  │  - manufacturing.payload_refs  │
                         └────────────────────────────────┘
```

### DES-003: Kafka Topic Design

| Topic | Content | Key | Partitions | Retention |
|-------|---------|-----|------------|-----------|
| `factory.sensor-data` | Sensor readings (temp, pressure, vibration) | device_id | 12 | 7 days |
| `factory.quality-events` | Quality inspection results | line_id | 6 | 30 days |
| `factory.document-metadata` | Document upload notifications (metadata only) | document_id | 3 | 30 days |
| `factory.image-metadata` | Image capture notifications (metadata only) | device_id | 6 | 30 days |
| `factory.system-alerts` | System health and alerts | source_system | 3 | 90 days |

### DES-004: Message Schema (Avro/JSON Schema)

```json
{
  "type": "record",
  "name": "QualityEvent",
  "namespace": "factory.quality",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "timestamp", "type": "long", "logicalType": "timestamp-millis"},
    {"name": "device_id", "type": "string"},
    {"name": "line_id", "type": "string"},
    {"name": "event_type", "type": {"type": "enum", "name": "EventType", "symbols": ["INSPECTION", "MEASUREMENT", "DEFECT", "PASS"]}},
    {"name": "measurement_value", "type": ["null", "double"]},
    {"name": "measurement_unit", "type": ["null", "string"]},
    {"name": "pass_fail", "type": ["null", "boolean"]},
    {"name": "payload_uri", "type": ["null", "string"]},
    {"name": "payload_type", "type": ["null", "string"]},
    {"name": "payload_size_bytes", "type": ["null", "long"]},
    {"name": "payload_checksum", "type": ["null", "string"]}
  ]
}
```

### DES-005: ClickHouse Table Design

```sql
-- Real-time sensor data (hot storage)
CREATE TABLE factory.sensor_data (
    event_id String,
    timestamp DateTime64(3),
    device_id LowCardinality(String),
    line_id LowCardinality(String),
    sensor_type LowCardinality(String),
    value Float64,
    unit LowCardinality(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (line_id, device_id, timestamp)
TTL timestamp + INTERVAL 90 DAY TO VOLUME 's3_cold';

-- Quality events
CREATE TABLE factory.quality_events (
    event_id String,
    timestamp DateTime64(3),
    device_id LowCardinality(String),
    line_id LowCardinality(String),
    event_type LowCardinality(String),
    measurement_value Nullable(Float64),
    pass_fail Nullable(UInt8),
    payload_uri Nullable(String),
    payload_type Nullable(String)
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (line_id, event_type, timestamp);
```

### DES-006: Databricks Delta Table Design

```sql
-- Governed sensor data (Unity Catalog managed table)
CREATE TABLE manufacturing_catalog.factory_data.sensor_readings (
    event_id STRING,
    event_timestamp TIMESTAMP,
    device_id STRING,
    line_id STRING,
    sensor_type STRING,
    value DOUBLE,
    unit STRING,
    ingestion_timestamp TIMESTAMP,
    kafka_topic STRING,
    kafka_partition INT,
    kafka_offset BIGINT
)
USING DELTA
PARTITIONED BY (sensor_type, date(event_timestamp))
TBLPROPERTIES ('delta.autoOptimize.optimizeWrite' = 'true');

-- Quality events with payload references
CREATE TABLE manufacturing_catalog.factory_data.quality_events (
    event_id STRING,
    event_timestamp TIMESTAMP,
    device_id STRING,
    line_id STRING,
    event_type STRING,
    measurement_value DOUBLE,
    measurement_unit STRING,
    pass_fail BOOLEAN,
    payload_uri STRING,
    payload_type STRING,
    payload_size_bytes BIGINT,
    payload_checksum STRING,
    ingestion_timestamp TIMESTAMP
)
USING DELTA
PARTITIONED BY (event_type, date(event_timestamp));
```

### DES-007: FSx for ONTAP Storage Design

| Volume | Protocol | Purpose | Capacity |
|--------|----------|---------|----------|
| `/vol_images` | NFS + ONTAP S3 | Quality inspection images | 500 GB |
| `/vol_videos` | NFS + SMB | Process monitoring video | 2 TB |
| `/vol_documents` | SMB + NFS | Quality certificates, reports | 200 GB |
| `/vol_clickhouse_cold` | ONTAP S3 | ClickHouse cold tier data | 1 TB |

**Snapshot Policy:** Hourly (24 retained), Daily (7 retained), Weekly (4 retained)

### DES-008: Network Architecture

```
┌─────────────────────────────────────────────────────┐
│                    VPC (10.0.0.0/16)                 │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ Private Sub  │  │ Private Sub  │                │
│  │ (MSK)        │  │ (ClickHouse) │                │
│  │ 10.0.1.0/24  │  │ 10.0.2.0/24  │                │
│  └──────────────┘  └──────────────┘                │
│                                                     │
│  ┌──────────────┐  ┌──────────────┐                │
│  │ Private Sub  │  │ Private Sub  │                │
│  │ (FSx for ONTAP)  │  │ (Databricks) │                │
│  │ 10.0.3.0/24  │  │ 10.0.4.0/24  │                │
│  └──────────────┘  └──────────────┘                │
│                                                     │
│  VPC Endpoints: S3, STS, Glue Catalog               │
│  VPC Peering: Databricks workspace VPC              │
└─────────────────────────────────────────────────────┘
```

### DES-009: Security Architecture

| Layer | Control |
|-------|---------|
| Network | Private subnets, security groups, VPC endpoints |
| Kafka | SASL/SCRAM + TLS, IAM authentication (MSK) |
| ClickHouse | Password auth, TLS, IP allowlist |
| FSx for ONTAP | Security groups, export policies, CIFS auth |
| Databricks | Unity Catalog RBAC, workspace isolation |
| S3 | Bucket policies, encryption (SSE-S3/SSE-KMS), no public access |
| Secrets | AWS Secrets Manager for credentials |

### DES-010: Streaming Pipeline Design (Databricks)

```python
# Structured Streaming: Kafka → Delta Lake (governed by Unity Catalog)
from pyspark.sql.functions import from_json, col, current_timestamp

# Read from Kafka
kafka_df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "<msk-bootstrap-servers>")
    .option("subscribe", "factory.sensor-data")
    .option("kafka.security.protocol", "SASL_SSL")
    .option("kafka.sasl.mechanism", "AWS_MSK_IAM")
    .option("startingOffsets", "latest")
    .load()
)

# Parse and transform
parsed_df = (
    kafka_df
    .select(
        from_json(col("value").cast("string"), sensor_schema).alias("data"),
        col("topic"),
        col("partition"),
        col("offset"),
        col("timestamp").alias("kafka_timestamp")
    )
    .select("data.*", "topic", "partition", "offset")
    .withColumn("ingestion_timestamp", current_timestamp())
)

# Write to Unity Catalog managed table
(
    parsed_df.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "s3://poc-checkpoints/sensor-data/")
    .toTable("manufacturing_catalog.factory_data.sensor_readings")
)
```

# Research Findings

🌐 **English** | [日本語](../ja/02_research_findings.md)

---

## RES-001: Kafka to Databricks Ingestion

### Status: Confirmed — Production-Ready Pattern

### Findings

1. **Structured Streaming + Delta Lake** is a first-class, production-proven pattern on Databricks. (REF-001, REF-002, REF-003)

2. **Exactly-once semantics** are guaranteed when writing from Kafka to Delta tables. The Delta Lake transaction log provides idempotent writes even with concurrent streams. (REF-002, REF-004)

3. **Unity Catalog governance** is fully supported for streaming workloads. Structured Streaming can write to both managed and external tables registered in Unity Catalog. (REF-001)

4. **Schema evolution** is supported via Delta Lake's schema evolution capabilities (mergeSchema, schema auto-merge).

5. **Checkpointing and recovery**: Structured Streaming uses checkpoints stored on cloud storage (S3) to track progress. On failure, processing resumes from the last committed offset. (REF-004)

6. **Security**: Supports SASL_SSL for Kafka authentication, SSL for encryption in transit. Secret management via Databricks secrets or AWS Secrets Manager. (REF-003)

7. **Amazon MSK integration**: Databricks connects to MSK clusters via IAM authentication or SASL/SCRAM. Private connectivity via VPC peering or AWS PrivateLink. (REF-003)

8. **Confluent Tableflow** (GA Oct 2025) is an alternative managed approach: automatically materializes Kafka topics into Delta tables and registers them with Unity Catalog. Eliminates custom streaming pipeline code. (REF-005, REF-006, REF-007)

### Production Considerations

| Concern | Mitigation |
|---------|-----------|
| Consumer lag | Monitor via CloudWatch (MSK) + Databricks streaming metrics |
| Late-arriving data | Watermark-based processing with configurable thresholds |
| Schema changes | Schema registry + Delta Lake schema evolution |
| Replay | Reset consumer offsets or restart from specific Kafka timestamp |
| Cost | Databricks streaming job cost (DBU) + MSK throughput |

### Confirmed Facts

- Kafka → Structured Streaming → Delta Lake → Unity Catalog is a supported, GA production pattern
- Exactly-once processing is guaranteed
- Works with Amazon MSK (self-managed and serverless)
- Works with Confluent Cloud

### Assumptions

- Network connectivity between MSK and Databricks workspace VPC (requires VPC peering or PrivateLink)
- MSK cluster is in the same region as Databricks workspace

---

## RES-002: ClickHouse to Databricks Integration

### Status: Confirmed — Viable but Secondary Path

### Findings

1. **ClickHouse Spark Connector** is the official integration method. Built on DataSourceV2 API, supports both Catalog API and TableProvider (format-based) access patterns. (REF-010, REF-011)

2. **Databricks-specific guide** exists in ClickHouse documentation, confirming the connector works on Databricks Runtime. (REF-010)

3. **JDBC fallback** is also supported as a simpler but less performant approach. (REF-012)

4. **Read/write support**: The connector supports reading from and writing to ClickHouse from Databricks notebooks and jobs. (REF-011)

5. **Use case**: ClickHouse serves as an operational analytics source. Databricks can periodically pull aggregated/curated data from ClickHouse for enrichment, ML features, or historical analysis.

6. **Not a primary ingestion path**: For this architecture, Kafka is the primary ingestion path to Databricks. ClickHouse-to-Databricks is a secondary path for batch reads of aggregated operational data.

### Integration Patterns

| Pattern | Description | Use Case |
|---------|-------------|----------|
| Spark read from ClickHouse | Databricks job reads ClickHouse tables via Spark connector | Batch import of aggregated metrics |
| JDBC read | Direct JDBC queries from Databricks notebooks | Ad-hoc analysis, small datasets |
| ClickHouse → S3 export → Databricks | ClickHouse exports to S3, Databricks reads from S3 | Decoupled batch transfer |

### Confirmed Facts

- ClickHouse Spark connector works on Databricks (documented by ClickHouse)
- JDBC connectivity is supported
- Read and write operations are both supported
- Connector is open-source and community-maintained

### Assumptions

- Network connectivity between ClickHouse and Databricks (VPC peering or same VPC)
- ClickHouse cluster is accessible from Databricks driver/executor nodes
- Connector version compatibility with Databricks Runtime version

### Open Questions

- Performance characteristics at scale (large table scans from ClickHouse via Spark)
- Whether ClickHouse Spark connector is used in production manufacturing environments

---

## RES-003: Unity Catalog Compatibility

### Status: Confirmed — Critical Limitation Identified

### Key Finding: S3-Compatible Storage NOT Supported

**Unity Catalog external locations only support:**
- Native Amazon S3 (on AWS)
- Azure Data Lake Storage Gen2 (on Azure)
- Google Cloud Storage (on GCP)
- Cloudflare R2 (cross-cloud)

**NOT supported:**
- S3-compatible endpoints (MinIO, ONTAP S3, or other S3-compatible storage)
- Custom S3 endpoints
- Non-standard bucket configurations

(REF-020, REF-021, REF-022)

### Implications for This Architecture

| Aspect | Implication |
|--------|-------------|
| Delta Lake storage | Must use native Amazon S3 |
| FSx for ONTAP role | Cannot serve as Unity Catalog external location |
| Payload references | Delta tables store URIs/paths to FSx for ONTAP payloads, but Delta data itself is on S3 |
| Architecture design | FSx for ONTAP and Unity Catalog are separate systems connected by metadata references |

### Managed Tables vs External Tables

| Type | Storage | Governance | Lifecycle |
|------|---------|------------|-----------|
| Managed table | UC-managed S3 location | Full UC governance | UC manages create/delete |
| External table | User-specified S3 location | UC governs metadata | User manages data lifecycle |
| Streaming table | UC-managed location | Full UC governance + streaming support | Automatic pipeline |

### Streaming Ingestion to Unity Catalog

- Structured Streaming can write to managed tables (recommended for governed data)
- Structured Streaming can write to external tables at external locations
- Streaming tables (DLT) provide additional pipeline management
- All approaches store data on native S3

### Confirmed Facts

- S3-compatible endpoints are NOT supported for Unity Catalog external locations
- This architecture correctly avoids using FSx for ONTAP as a Unity Catalog storage target
- Kafka → Structured Streaming → UC managed/external tables on native S3 is the correct pattern
- FSx for ONTAP S3 Access Points would not help for Unity Catalog integration

### Assumptions

- Databricks workspace deployed in same AWS region as S3 buckets
- IAM roles configured for UC storage credentials

---

## RES-004: FSx for ONTAP Role

### Status: Confirmed — Strong Value for Payload Storage

### What was validated

| Capability | Benefit for This Architecture |
|-----------|-------------------------------|
| Multiprotocol (NFS/SMB/S3) | Edge devices write via NFS/SMB; downstream ML/AI can read via S3 API |
| Snapshot | Point-in-time recovery of payload data; consistent views for ML training |
| SnapMirror | Cross-region DR for payload data |
| FlexClone | Space-efficient copies for testing/development environments |
| ONTAP S3 | ClickHouse cold storage tiering target (S3-compatible) |
| Data protection | Enterprise-grade without additional tooling |

### Architecture Role

FSx for ONTAP serves as the **payload storage layer** — not as a Delta Lake storage target:

```
Edge Devices ─── NFS/SMB ───→ FSx for ONTAP (payloads)
                                     ↑
                              ClickHouse tiering (ONTAP S3)
                                     
Kafka messages contain payload_uri pointing to FSx for ONTAP paths
Delta tables contain payload_uri columns referencing FSx for ONTAP
Databricks does NOT directly access FSx for ONTAP
```

### Trade-offs vs Native Amazon S3

| Factor | FSx for ONTAP | Native S3 |
|--------|--------------|-----------|
| Protocol flexibility | NFS + SMB + S3 | S3 only |
| Latency (file ops) | Low (NFS/SMB) | Higher (S3 API) |
| Data protection | Snapshot, SnapMirror, built-in | Versioning, replication, separate |
| Cost | Higher (provisioned capacity + throughput) | Lower (pay-per-use) |
| Operational complexity | Higher (SVM, volumes, exports) | Lower (buckets, policies) |
| Unity Catalog compatibility | Not compatible as external location | Fully compatible |
| Manufacturing edge compatibility | Excellent (NFS/SMB for PLCs, SCADA) | Limited (S3 SDK required) |

### Confirmed Facts

- FSx for ONTAP S3 Access Points exist but are NOT relevant for Unity Catalog (since UC doesn't support S3-compatible endpoints)
- FSx for ONTAP adds clear value for multiprotocol edge device integration
- ClickHouse supports S3-compatible storage for tiered/cold data (ONTAP S3 is a valid target)
- Snapshot/SnapMirror/FlexClone provide operational data protection not available with S3 alone

### Open Questions

- ClickHouse tiering to ONTAP S3 performance characteristics (needs PoC validation)
- Optimal protocol for edge device payload upload (NFS vs SMB vs ONTAP S3 — depends on edge device capabilities)

---

## RES-005: Unstructured Data Handling

### Status: Confirmed — Metadata-Payload Separation is Standard Pattern

### Recommended Pattern

The metadata-payload separation pattern is well-established in manufacturing data platforms:

1. **Lightweight metadata** (event type, timestamp, device_id, payload_uri, content_type, size, checksum) flows through Kafka
2. **Large payloads** (images, video, documents) are stored directly on FSx for ONTAP
3. **Delta tables** store curated metadata with payload_uri references
4. **Downstream AI/ML** accesses payloads directly from FSx for ONTAP when needed (via NFS mount or S3 API)

### Delta Table Schema Pattern

```sql
CREATE TABLE manufacturing.quality_events (
  event_id STRING,
  timestamp TIMESTAMP,
  device_id STRING,
  line_id STRING,
  event_type STRING,
  -- Structured data
  measurement_value DOUBLE,
  measurement_unit STRING,
  pass_fail BOOLEAN,
  -- Payload reference (not the payload itself)
  payload_uri STRING,        -- e.g., "nfs://svm1/vol1/images/2026/06/07/img_001.png"
  payload_type STRING,       -- e.g., "image/png"
  payload_size_bytes BIGINT,
  payload_checksum STRING,
  -- Metadata
  ingestion_timestamp TIMESTAMP,
  kafka_topic STRING,
  kafka_partition INT,
  kafka_offset BIGINT
)
USING DELTA
PARTITIONED BY (event_type, date(timestamp))
```

### Governance Implications

- **Lineage**: Unity Catalog tracks lineage for structured data in Delta tables. Payload lineage requires custom metadata.
- **Access control**: UC governs Delta table access. Payload access governed separately by FSx for ONTAP permissions.
- **Audit**: UC audit logs track who queried Delta tables. Payload access audit via ONTAP audit logs.

### Confirmed Facts

- Payloads do NOT need to be copied into Delta Lake
- Delta tables can reference external payloads via URI columns
- This is a standard pattern in IoT/manufacturing architectures
- Governance of structured metadata and unstructured payloads are handled by different systems

---

## RES-006: Public Reference Patterns

### Status: Multiple Relevant References Found

### Manufacturing + Kafka + ClickHouse

| Reference | Key Pattern | Relevance |
|-----------|------------|-----------|
| Critical Manufacturing (REF-030) | SQL Server → ClickHouse migration; Kafka-based ingestion; real-time factory floor dashboards | Direct manufacturing reference with Kafka + ClickHouse |
| EMQ Industrial IoT (REF-032) | MQTT → ClickHouse Cloud; 1000+ enterprise customers; high-throughput industrial analytics | Edge/IoT to ClickHouse pattern validation |
| Kafka as Data Historian (REF-033) | Kafka replacing traditional data historians in IIoT; OEE, digital twin concepts | Industry 4.0 architecture context |

### Kafka + Lakehouse/Databricks

| Reference | Key Pattern | Relevance |
|-----------|------------|-----------|
| Confluent Tableflow + Unity Catalog (REF-005) | Kafka topics → Delta tables → UC governance; fully managed | Managed Kafka-to-UC pattern |
| Redpanda + Databricks (REF-007) | Kafka streams → UC-managed Iceberg tables | Streaming to governed lakehouse |
| Databricks Ingestion Reference Architecture (REF-008) | Official reference for batch, CDC, streaming ingestion with UC | Canonical architecture |

### Key Differences from This Architecture

| Public Reference | This Architecture |
|-----------------|-------------------|
| Single analytics engine | Dual: ClickHouse (real-time) + Databricks (governed batch/ML) |
| S3 as primary storage | FSx for ONTAP for payloads + S3 for Delta tables |
| No unstructured payload handling | Explicit metadata/payload separation |
| Generic IoT/streaming | Manufacturing-specific (quality, sensor, OEE) |

### Confirmed Facts

- Kafka + ClickHouse for manufacturing is a proven production pattern
- Kafka → Databricks + Unity Catalog is a proven production pattern
- The combination of all three (Kafka + ClickHouse + Databricks) is architecturally sound but less commonly documented as a single reference architecture
- FSx for ONTAP as a payload store alongside a lakehouse is a novel but defensible pattern

---

## RES-007: ClickHouse Deployment on AWS

### Status: Confirmed — Multiple Viable Options

| Option | Type | Key Characteristics |
|--------|------|-------------------|
| ClickHouse Cloud | Fully managed | Zero ops, auto-scaling, S3 backend, AWS Marketplace |
| ClickHouse BYOC | Managed in customer VPC | Data stays in customer VPC, EKS-based, S3 storage |
| Self-managed (EC2) | Self-operated | Full control, manual scaling, ZooKeeper/Keeper |
| Self-managed (EKS) | Self-operated on K8s | Container-based, Helm charts available |
| AWS Solution (CloudFormation) | AWS-provided template | EC2 + ZooKeeper + ELB reference deployment |

### Recommended for PoC

**ClickHouse Cloud** or **BYOC** for minimal operational overhead. Self-managed on EC2 is acceptable if cost is a primary concern.

### ClickHouse S3 Tiered Storage

ClickHouse supports S3 and S3-compatible storage as a native disk type for tiered/cold data:

- **S3BackedMergeTree**: MergeTree engine variant with S3 as backend storage
- **Tiered storage policies**: Hot data on local SSD, cold data automatically moved to S3
- **S3-compatible support**: MinIO, GCS, Cloudflare R2, and other S3-compatible endpoints confirmed working

**Implication**: ClickHouse can tier cold data to FSx for ONTAP via ONTAP S3 protocol. This provides:
- Unified storage for both ClickHouse cold data and edge payloads
- ONTAP data protection (Snapshot/SnapMirror) for ClickHouse cold tier
- Cost optimization vs EBS for historical analytics data

(REF-042, REF-043)

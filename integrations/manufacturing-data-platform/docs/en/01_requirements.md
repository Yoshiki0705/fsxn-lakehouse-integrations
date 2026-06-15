# Requirements

🌐 **English** | [日本語](../ja/01_requirements.md)

---

## Functional Requirements

### REQ-F001: Edge Event Ingestion

Edge/factory devices must be able to publish structured events (quality logs, sensor readings, status updates) to Kafka topics via MQTT bridge or Kafka producers.

**Acceptance Criteria:**
- Events are published to Kafka with schema and metadata
- Supports at-least-once delivery from edge to Kafka
- Event schema includes timestamp, device_id, event_type, and payload_reference (if applicable)

### REQ-F002: Lightweight Metadata Streaming

Kafka must carry lightweight structured metadata and events. Large payloads (images, video, documents) must NOT flow through Kafka.

**Acceptance Criteria:**
- Kafka messages are bounded in size (≤1 MB recommended)
- Large payloads are stored separately and referenced by URI/path in Kafka messages
- Metadata includes source path, content type, size, and checksum

### REQ-F003: Large Payload Storage

Documents, images, and video from edge devices must be stored on FSx for ONTAP using S3, SMB, or NFS protocols.

**Acceptance Criteria:**
- Payloads are accessible via at least one protocol (NFS, SMB, or ONTAP S3)
- Payloads are identifiable by a stable URI or path
- Storage supports multiprotocol access for different consumers

### REQ-F004: Real-Time Analytics on Structured Data

ClickHouse must consume high-frequency structured data from Kafka and provide sub-second query performance for operational dashboards.

**Acceptance Criteria:**
- ClickHouse ingests from Kafka with low latency (< 5 seconds end-to-end)
- Queries on recent data return in < 1 second
- Supports time-series aggregation and filtering by device, line, or quality metric

### REQ-F005: Governed Data Lake Ingestion

Databricks must consume data from Kafka (and optionally from ClickHouse) and write curated Delta tables governed by Unity Catalog.

**Acceptance Criteria:**
- Structured Streaming reads from Kafka and writes to Delta tables
- Delta tables are registered in Unity Catalog
- Exactly-once processing semantics maintained
- Schema evolution supported

### REQ-F006: Metadata-to-Payload Reference

Delta tables must contain references (URIs/paths) to unstructured payloads stored on FSx for ONTAP, without requiring Databricks to directly access FSx for ONTAP storage.

**Acceptance Criteria:**
- Delta table columns include payload_uri, payload_type, payload_size
- Payload URIs are resolvable by authorized downstream systems
- Databricks does not require direct FSx for ONTAP mount or S3 Access Point

### REQ-F007: No S3 Access Points Dependency

The architecture must function without relying on S3 Access Points for FSx for ONTAP as a Unity Catalog external location or Delta Lake storage target.

**Acceptance Criteria:**
- Unity Catalog external locations point to native Amazon S3 buckets only
- FSx for ONTAP is not registered as a Unity Catalog external location
- All Delta table data resides on native S3

---

## Non-Functional Requirements

### REQ-N001: PoC Feasibility

The architecture must be implementable as an AWS-based PoC with minimum required components.

**Acceptance Criteria:**
- All components deployable in a single AWS region
- Total PoC cost estimable and bounded
- No dependency on private preview or unreleased features

### REQ-N002: Failure Recovery

The system must support checkpointing, replay, and failure recovery for streaming pipelines.

**Acceptance Criteria:**
- Kafka consumer offsets are checkpointed
- Structured Streaming checkpoints are stored durably
- Pipeline can resume from last checkpoint after failure
- Manual replay from specific offset/timestamp is possible

### REQ-N003: Observability

The system must provide operational observability for all components.

**Acceptance Criteria:**
- Kafka: consumer lag, throughput, error rates
- ClickHouse: query latency, ingestion rate, storage utilization
- Databricks: streaming metrics, job status, failure alerts
- FSx for ONTAP: storage capacity, IOPS, throughput

### REQ-N004: Security

The system must implement security controls appropriate for a PoC environment.

**Acceptance Criteria:**
- Kafka: SASL/TLS authentication, encryption in transit
- ClickHouse: authentication, network isolation
- Databricks: Unity Catalog permissions, workspace isolation
- FSx for ONTAP: security groups, export policies, encryption at rest
- All inter-component communication within VPC or via private endpoints

### REQ-N005: Bilingual Documentation

All project documentation must be maintained in both Japanese and English with synchronized content.

**Acceptance Criteria:**
- Every document exists in both languages
- Same stable IDs used across languages
- Changes update both versions simultaneously

### REQ-N006: Public Repository Safety

All content must be safe for a public GitHub repository.

**Acceptance Criteria:**
- No real customer/partner names
- No confidential business context
- Synthetic data only, clearly labeled
- No private URLs or credentials
- Passes confidentiality review checklist

### REQ-N007: Evidence-Based Validation

All technical claims must be backed by reproducible evidence or cited sources.

**Acceptance Criteria:**
- Each claim references a source in docs/references.md
- Assumptions are clearly labeled as assumptions
- Unvalidated items are marked "Needs external validation"
- Hypotheses are distinguished from confirmed facts

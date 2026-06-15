-- Manufacturing Data Platform PoC — Unity Catalog Setup
-- Architecture Reference: ADR-011 (Unity Catalog Permissions Model)
--
-- Run this in a Databricks SQL warehouse or notebook with admin privileges.
-- Prerequisites: Unity Catalog metastore attached to workspace.

-- ============================================================
-- Step 1: Create Catalog
-- ============================================================
CREATE CATALOG IF NOT EXISTS manufacturing_poc
COMMENT 'Manufacturing Data Platform PoC — governed analytics catalog';

-- ============================================================
-- Step 2: Create Schemas (per-factory + cross-factory + system)
-- ============================================================
CREATE SCHEMA IF NOT EXISTS manufacturing_poc.factory_alpha
COMMENT 'Factory Alpha sensor, quality, and equipment data';

CREATE SCHEMA IF NOT EXISTS manufacturing_poc.factory_beta
COMMENT 'Factory Beta sensor, quality, and equipment data';

CREATE SCHEMA IF NOT EXISTS manufacturing_poc.cross_factory
COMMENT 'Cross-factory aggregated views and KPIs';

CREATE SCHEMA IF NOT EXISTS manufacturing_poc._system
COMMENT 'Pipeline metadata, ingestion metrics, payload registry';

-- ============================================================
-- Step 3: Create Delta Tables (per DES-006)
-- ============================================================

-- Sensor readings (Factory Alpha)
CREATE TABLE IF NOT EXISTS manufacturing_poc.factory_alpha.sensor_readings (
    event_id STRING NOT NULL COMMENT 'Deterministic unique event ID',
    event_timestamp TIMESTAMP NOT NULL COMMENT 'Event time from edge device',
    factory_id STRING NOT NULL COMMENT 'Factory identifier',
    device_id STRING NOT NULL COMMENT 'Device that generated the event',
    line_id STRING NOT NULL COMMENT 'Production line ID',
    sensor_type STRING NOT NULL COMMENT 'Sensor type: temperature, humidity, pressure, vibration',
    value DOUBLE NOT NULL COMMENT 'Sensor measurement value',
    unit STRING NOT NULL COMMENT 'Measurement unit',
    ingestion_timestamp TIMESTAMP COMMENT 'Time when record was written to Delta',
    kafka_topic STRING COMMENT 'Source Kafka topic',
    kafka_partition INT COMMENT 'Source Kafka partition',
    kafka_offset BIGINT COMMENT 'Source Kafka offset'
)
USING DELTA
PARTITIONED BY (sensor_type, date(event_timestamp))
COMMENT 'Governed sensor readings from Factory Alpha'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true',
    'delta.deletedFileRetentionDuration' = 'interval 7 days'
);

-- Quality events (Factory Alpha)
CREATE TABLE IF NOT EXISTS manufacturing_poc.factory_alpha.quality_events (
    event_id STRING NOT NULL COMMENT 'Deterministic unique event ID',
    event_timestamp TIMESTAMP NOT NULL COMMENT 'Event time from edge device',
    factory_id STRING NOT NULL COMMENT 'Factory identifier',
    device_id STRING NOT NULL COMMENT 'Device that generated the event',
    line_id STRING NOT NULL COMMENT 'Production line ID',
    event_type STRING NOT NULL COMMENT 'INSPECTION, MEASUREMENT, DEFECT, PASS',
    measurement_value DOUBLE COMMENT 'Measurement value (if applicable)',
    pass_fail BOOLEAN COMMENT 'Pass/fail result',
    payload_uri STRING COMMENT 'URI to payload file on FSx for ONTAP',
    payload_type STRING COMMENT 'MIME type of payload',
    payload_size_bytes BIGINT COMMENT 'Payload file size in bytes',
    payload_checksum STRING COMMENT 'SHA-256 checksum of payload',
    ingestion_timestamp TIMESTAMP COMMENT 'Time when record was written to Delta'
)
USING DELTA
PARTITIONED BY (event_type, date(event_timestamp))
COMMENT 'Governed quality events from Factory Alpha with payload references'
TBLPROPERTIES (
    'delta.autoOptimize.optimizeWrite' = 'true',
    'delta.autoOptimize.autoCompact' = 'true'
);

-- Equipment status (Factory Alpha)
CREATE TABLE IF NOT EXISTS manufacturing_poc.factory_alpha.equipment_status (
    event_id STRING NOT NULL,
    event_timestamp TIMESTAMP NOT NULL,
    factory_id STRING NOT NULL,
    device_id STRING NOT NULL,
    line_id STRING NOT NULL,
    equipment_state STRING NOT NULL COMMENT 'running, stopped, maintenance, warming_up',
    ingestion_timestamp TIMESTAMP
)
USING DELTA
PARTITIONED BY (date(event_timestamp))
COMMENT 'Equipment state changes from Factory Alpha';

-- ============================================================
-- Step 4: Create Factory Beta tables (same schema)
-- ============================================================
CREATE TABLE IF NOT EXISTS manufacturing_poc.factory_beta.sensor_readings
LIKE manufacturing_poc.factory_alpha.sensor_readings;

CREATE TABLE IF NOT EXISTS manufacturing_poc.factory_beta.quality_events
LIKE manufacturing_poc.factory_alpha.quality_events;

CREATE TABLE IF NOT EXISTS manufacturing_poc.factory_beta.equipment_status
LIKE manufacturing_poc.factory_alpha.equipment_status;

-- ============================================================
-- Step 5: System tables
-- ============================================================
CREATE TABLE IF NOT EXISTS manufacturing_poc._system.ingestion_metrics (
    metric_timestamp TIMESTAMP NOT NULL,
    pipeline_name STRING NOT NULL,
    records_processed BIGINT,
    batch_duration_ms BIGINT,
    kafka_lag BIGINT,
    error_count INT,
    checkpoint_offset BIGINT
)
USING DELTA
PARTITIONED BY (date(metric_timestamp))
COMMENT 'Streaming pipeline health metrics';

CREATE TABLE IF NOT EXISTS manufacturing_poc._system.payload_registry (
    payload_uri STRING NOT NULL,
    factory_id STRING NOT NULL,
    registered_at TIMESTAMP NOT NULL,
    content_type STRING,
    size_bytes BIGINT,
    checksum_sha256 STRING,
    verified BOOLEAN DEFAULT false,
    verified_at TIMESTAMP
)
USING DELTA
COMMENT 'Registry of all payload URIs with verification status';

-- ============================================================
-- Step 6: Cross-factory views
-- ============================================================
CREATE VIEW IF NOT EXISTS manufacturing_poc.cross_factory.all_sensor_readings AS
SELECT *, 'factory_alpha' AS source_schema FROM manufacturing_poc.factory_alpha.sensor_readings
UNION ALL
SELECT *, 'factory_beta' AS source_schema FROM manufacturing_poc.factory_beta.sensor_readings;

CREATE VIEW IF NOT EXISTS manufacturing_poc.cross_factory.all_quality_events AS
SELECT *, 'factory_alpha' AS source_schema FROM manufacturing_poc.factory_alpha.quality_events
UNION ALL
SELECT *, 'factory_beta' AS source_schema FROM manufacturing_poc.factory_beta.quality_events;

-- Manufacturing Data Platform PoC — ClickHouse Table Setup
-- Architecture Reference: ADR-009 (Kafka → ClickHouse connector)
-- Architecture Reference: DES-005 (ClickHouse table design)
--
-- Run this on ClickHouse Cloud or Instaclustr-managed ClickHouse.
-- Prerequisites:
--   - Kafka cluster (MSK) accessible from ClickHouse
--   - SASL/SCRAM credentials or IAM auth configured
--
-- Replace ${KAFKA_BOOTSTRAP_SERVERS} with actual MSK bootstrap servers
-- Replace ${KAFKA_USERNAME} and ${KAFKA_PASSWORD} with SCRAM credentials

-- ============================================================
-- Step 1: Create database
-- ============================================================
CREATE DATABASE IF NOT EXISTS factory;

-- ============================================================
-- Step 2: Kafka Engine tables (virtual consumers)
-- ============================================================

-- Sensor data consumer
CREATE TABLE IF NOT EXISTS factory.sensor_data_kafka (
    raw String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = '${KAFKA_BOOTSTRAP_SERVERS}',
    kafka_topic_list = 'factory.sensor-data',
    kafka_group_name = 'clickhouse-sensor-consumer',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 3,
    kafka_max_block_size = 65536,
    kafka_skip_broken_messages = 10,
    kafka_poll_timeout_ms = 1000,
    kafka_thread_per_consumer = 1,
    kafka_security_protocol = 'SASL_SSL',
    kafka_sasl_mechanism = 'SCRAM-SHA-512',
    kafka_sasl_username = '${KAFKA_USERNAME}',
    kafka_sasl_password = '${KAFKA_PASSWORD}';

-- Quality events consumer
CREATE TABLE IF NOT EXISTS factory.quality_events_kafka (
    raw String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = '${KAFKA_BOOTSTRAP_SERVERS}',
    kafka_topic_list = 'factory.quality-events',
    kafka_group_name = 'clickhouse-quality-consumer',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 2,
    kafka_max_block_size = 65536,
    kafka_skip_broken_messages = 10,
    kafka_security_protocol = 'SASL_SSL',
    kafka_sasl_mechanism = 'SCRAM-SHA-512',
    kafka_sasl_username = '${KAFKA_USERNAME}',
    kafka_sasl_password = '${KAFKA_PASSWORD}';

-- System alerts consumer
CREATE TABLE IF NOT EXISTS factory.system_alerts_kafka (
    raw String
)
ENGINE = Kafka
SETTINGS
    kafka_broker_list = '${KAFKA_BOOTSTRAP_SERVERS}',
    kafka_topic_list = 'factory.system-alerts',
    kafka_group_name = 'clickhouse-alerts-consumer',
    kafka_format = 'JSONAsString',
    kafka_num_consumers = 1,
    kafka_skip_broken_messages = 10,
    kafka_security_protocol = 'SASL_SSL',
    kafka_sasl_mechanism = 'SCRAM-SHA-512',
    kafka_sasl_username = '${KAFKA_USERNAME}',
    kafka_sasl_password = '${KAFKA_PASSWORD}';

-- ============================================================
-- Step 3: Destination MergeTree tables (queryable)
-- ============================================================

-- Sensor data (hot storage with TTL tiering)
CREATE TABLE IF NOT EXISTS factory.sensor_data (
    event_id String,
    timestamp DateTime64(3),
    factory_id LowCardinality(String),
    device_id LowCardinality(String),
    line_id LowCardinality(String),
    sensor_type LowCardinality(String),
    value Float64,
    unit LowCardinality(String)
)
ENGINE = ReplacingMergeTree(timestamp)
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (factory_id, line_id, device_id, sensor_type, timestamp, event_id)
TTL timestamp + INTERVAL 90 DAY DELETE
SETTINGS index_granularity = 8192;

-- Quality events (with payload reference)
CREATE TABLE IF NOT EXISTS factory.quality_events (
    event_id String,
    timestamp DateTime64(3),
    factory_id LowCardinality(String),
    device_id LowCardinality(String),
    line_id LowCardinality(String),
    event_type LowCardinality(String),
    measurement_value Nullable(Float64),
    pass_fail Nullable(UInt8),
    payload_reference Nullable(String),
    content_type Nullable(String),
    payload_size_bytes Nullable(UInt64),
    checksum_sha256 Nullable(String)
)
ENGINE = ReplacingMergeTree(timestamp)
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (factory_id, line_id, event_type, timestamp, event_id)
SETTINGS index_granularity = 8192;

-- Equipment status
CREATE TABLE IF NOT EXISTS factory.equipment_status (
    event_id String,
    timestamp DateTime64(3),
    factory_id LowCardinality(String),
    device_id LowCardinality(String),
    line_id LowCardinality(String),
    equipment_state LowCardinality(String)
)
ENGINE = ReplacingMergeTree(timestamp)
PARTITION BY toYYYYMMDD(timestamp)
ORDER BY (factory_id, line_id, device_id, timestamp, event_id)
SETTINGS index_granularity = 8192;

-- Dead letter queue
CREATE TABLE IF NOT EXISTS factory.dead_letter_queue (
    received_at DateTime DEFAULT now(),
    source_topic LowCardinality(String),
    raw_message String,
    error_reason String
)
ENGINE = MergeTree()
ORDER BY received_at
TTL received_at + INTERVAL 30 DAY DELETE;

-- ============================================================
-- Step 4: Materialized Views (auto-transform from Kafka to MergeTree)
-- ============================================================

-- Sensor data MV
CREATE MATERIALIZED VIEW IF NOT EXISTS factory.sensor_data_mv TO factory.sensor_data AS
SELECT
    JSONExtractString(raw, 'event_id') AS event_id,
    fromUnixTimestamp64Milli(toInt64(JSONExtractUInt(raw, 'timestamp'))) AS timestamp,
    JSONExtractString(raw, 'factory_id') AS factory_id,
    JSONExtractString(raw, 'device_id') AS device_id,
    JSONExtractString(raw, 'line_id') AS line_id,
    JSONExtractString(raw, 'sensor_type') AS sensor_type,
    JSONExtractFloat(raw, 'value') AS value,
    JSONExtractString(raw, 'unit') AS unit
FROM factory.sensor_data_kafka
WHERE JSONExtractString(raw, 'event_type') = 'SENSOR_READING';

-- Quality events MV
CREATE MATERIALIZED VIEW IF NOT EXISTS factory.quality_events_mv TO factory.quality_events AS
SELECT
    JSONExtractString(raw, 'event_id') AS event_id,
    fromUnixTimestamp64Milli(toInt64(JSONExtractUInt(raw, 'timestamp'))) AS timestamp,
    JSONExtractString(raw, 'factory_id') AS factory_id,
    JSONExtractString(raw, 'device_id') AS device_id,
    JSONExtractString(raw, 'line_id') AS line_id,
    JSONExtractString(raw, 'event_type') AS event_type,
    JSONExtractFloat(raw, 'measurement_value') AS measurement_value,
    toNullable(toUInt8(JSONExtractBool(raw, 'pass_fail'))) AS pass_fail,
    nullIf(JSONExtractString(raw, 'payload_reference'), '') AS payload_reference,
    nullIf(JSONExtractString(raw, 'content_type'), '') AS content_type,
    JSONExtractUInt(raw, 'payload_size_bytes') AS payload_size_bytes,
    nullIf(JSONExtractString(raw, 'checksum_sha256'), '') AS checksum_sha256
FROM factory.quality_events_kafka;

-- Equipment status MV
CREATE MATERIALIZED VIEW IF NOT EXISTS factory.equipment_status_mv TO factory.equipment_status AS
SELECT
    JSONExtractString(raw, 'event_id') AS event_id,
    fromUnixTimestamp64Milli(toInt64(JSONExtractUInt(raw, 'timestamp'))) AS timestamp,
    JSONExtractString(raw, 'factory_id') AS factory_id,
    JSONExtractString(raw, 'device_id') AS device_id,
    JSONExtractString(raw, 'line_id') AS line_id,
    JSONExtractString(raw, 'equipment_state') AS equipment_state
FROM factory.system_alerts_kafka
WHERE JSONExtractString(raw, 'event_type') = 'EQUIPMENT_STATUS';

-- ============================================================
-- Step 5: Sample queries (verify after data flows)
-- ============================================================

-- Latest sensor readings per device (last 5 minutes)
-- SELECT
--     device_id,
--     sensor_type,
--     avg(value) AS avg_value,
--     max(value) AS max_value,
--     count() AS reading_count
-- FROM factory.sensor_data FINAL
-- WHERE timestamp > now() - INTERVAL 5 MINUTE
-- GROUP BY device_id, sensor_type
-- ORDER BY device_id, sensor_type;

-- Quality events with payload references
-- SELECT
--     event_type,
--     count() AS event_count,
--     countIf(payload_reference != '') AS with_payload,
--     avg(measurement_value) AS avg_measurement
-- FROM factory.quality_events FINAL
-- WHERE timestamp > now() - INTERVAL 1 HOUR
-- GROUP BY event_type;

-- Equipment status distribution
-- SELECT
--     equipment_state,
--     count() AS device_count
-- FROM factory.equipment_status FINAL
-- WHERE timestamp > now() - INTERVAL 1 HOUR
-- GROUP BY equipment_state;

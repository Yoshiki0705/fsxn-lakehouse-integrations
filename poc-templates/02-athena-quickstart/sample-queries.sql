-- FSx for ONTAP S3 Access Points — Athena Quick Start Queries
-- Replace <AP_ALIAS> with your S3 Access Point alias (ending in -ext-s3alias)

-- ============================================================
-- Step 1: Create Glue Database
-- ============================================================
CREATE DATABASE IF NOT EXISTS fsxn_poc;

-- ============================================================
-- Step 2: Create External Table on FSx for ONTAP S3 AP
-- ============================================================
CREATE EXTERNAL TABLE IF NOT EXISTS fsxn_poc.sensor_data (
  timestamp TIMESTAMP,
  device_id STRING,
  sensor_id STRING,
  temperature DOUBLE,
  humidity DOUBLE,
  pressure DOUBLE,
  status STRING,
  location STRING
)
STORED AS PARQUET
LOCATION 's3://<AP_ALIAS>/sensor-data/'
TBLPROPERTIES ('parquet.compression'='SNAPPY');

-- ============================================================
-- Step 3: Validate — Simple count
-- ============================================================
SELECT COUNT(*) AS total_rows FROM fsxn_poc.sensor_data;
-- Expected: 10000 (or your generated row count)

-- ============================================================
-- Step 4: Aggregation query
-- ============================================================
SELECT
  status,
  COUNT(*) AS count,
  ROUND(AVG(temperature), 2) AS avg_temp,
  ROUND(AVG(humidity), 2) AS avg_humidity,
  ROUND(MIN(temperature), 2) AS min_temp,
  ROUND(MAX(temperature), 2) AS max_temp
FROM fsxn_poc.sensor_data
GROUP BY status
ORDER BY count DESC;

-- ============================================================
-- Step 5: Device-level analysis
-- ============================================================
SELECT
  device_id,
  location,
  COUNT(*) AS readings,
  SUM(CASE WHEN status = 'critical' THEN 1 ELSE 0 END) AS critical_count,
  ROUND(AVG(temperature), 2) AS avg_temp
FROM fsxn_poc.sensor_data
GROUP BY device_id, location
ORDER BY critical_count DESC
LIMIT 10;

-- ============================================================
-- Step 6: Time-series analysis
-- ============================================================
SELECT
  DATE_TRUNC('hour', timestamp) AS hour,
  COUNT(*) AS readings,
  ROUND(AVG(temperature), 2) AS avg_temp,
  SUM(CASE WHEN status = 'critical' THEN 1 ELSE 0 END) AS critical_count
FROM fsxn_poc.sensor_data
GROUP BY DATE_TRUNC('hour', timestamp)
ORDER BY hour
LIMIT 24;

-- ============================================================
-- Step 7: CTAS — Write results back to FSx for ONTAP S3 AP (optional)
-- ============================================================
CREATE TABLE fsxn_poc.sensor_summary
WITH (
  external_location = 's3://<AP_ALIAS>/gold/sensor-summary/',
  format = 'PARQUET'
) AS
SELECT
  device_id,
  location,
  status,
  COUNT(*) AS total_readings,
  ROUND(AVG(temperature), 2) AS avg_temp,
  ROUND(AVG(humidity), 2) AS avg_humidity
FROM fsxn_poc.sensor_data
GROUP BY device_id, location, status;

-- Verify write-back
SELECT * FROM fsxn_poc.sensor_summary LIMIT 5;

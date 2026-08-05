-- =============================================================================
-- 04 - External Tables on FSx for ONTAP via S3 Access Point
-- =============================================================================
-- Creates External Tables that query data directly on FSx for NetApp ONTAP
-- via S3 Access Point. Data remains on FSx for ONTAP (no copy into Snowflake).
--
-- Tables Created:
--   TRANSACTIONS   — Financial transactions (Parquet)
--   IOT_SENSORS    — IoT sensor readings (Parquet, partitioned by date)
--   CUSTOMERS_CSV  — Customer master data (CSV)
--   EVENTS_JSON    — Event stream data (JSON)
--
-- Prerequisites:
--   - 01_storage_integration.sql (Storage Integration + trust setup)
--   - 02_external_stage.sql (FSXN_BRONZE_STAGE created)
--   - 03_file_format.sql (PARQUET_FORMAT, CSV_FORMAT, JSON_FORMAT created)
--   - Sample data uploaded to FSx for ONTAP bronze/ path
--
-- Requirements: REQ-2 (External Table queries on Parquet, CSV, JSON)
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA BRONZE;

-- =============================================================================
-- 1. External Table: TRANSACTIONS (Parquet)
-- =============================================================================
-- Source: Parquet files at bronze/transactions/
-- Columns: transaction_id, timestamp, amount, category, merchant, customer_id
-- =============================================================================
CREATE OR REPLACE EXTERNAL TABLE TRANSACTIONS
  WITH LOCATION = @FSXN_BRONZE_STAGE/transactions/
  AUTO_REFRESH = FALSE
  FILE_FORMAT = (FORMAT_NAME = 'BRONZE.PARQUET_FORMAT')
  COMMENT = 'Financial transactions on FSx for ONTAP (Parquet) — REQ-2'
  AS
  SELECT
    VALUE:transaction_id::STRING       AS transaction_id,
    VALUE:timestamp::TIMESTAMP_NTZ     AS transaction_timestamp,
    VALUE:amount::FLOAT                AS amount,
    VALUE:category::STRING             AS category,
    VALUE:merchant::STRING             AS merchant,
    VALUE:customer_id::STRING          AS customer_id,
    METADATA$FILENAME                  AS source_file,
    METADATA$FILE_ROW_NUMBER           AS file_row_number
  FROM @FSXN_BRONZE_STAGE/transactions/ (FILE_FORMAT => 'BRONZE.PARQUET_FORMAT');

-- =============================================================================
-- 2. External Table: IOT_SENSORS (Parquet, Partitioned by Date)
-- =============================================================================
-- Source: Parquet files at bronze/iot-sensors/ with Hive-style partitioning
--         e.g. iot-sensors/date=2024-03-15/data.parquet
-- Columns: sensor_id, timestamp, temperature, humidity, pressure, location
-- Partition: date column derived from file path
-- =============================================================================
CREATE OR REPLACE EXTERNAL TABLE IOT_SENSORS
  WITH LOCATION = @FSXN_BRONZE_STAGE/iot-sensors/
  AUTO_REFRESH = FALSE
  PARTITION BY (PARTITION_DATE)
  FILE_FORMAT = (FORMAT_NAME = 'BRONZE.PARQUET_FORMAT')
  COMMENT = 'IoT sensor data on FSx for ONTAP (Parquet, partitioned by date) — REQ-2'
  AS
  SELECT
    VALUE:sensor_id::STRING            AS sensor_id,
    VALUE:timestamp::TIMESTAMP_NTZ     AS reading_timestamp,
    VALUE:temperature::FLOAT           AS temperature,
    VALUE:humidity::FLOAT              AS humidity,
    VALUE:pressure::FLOAT              AS pressure,
    VALUE:location::STRING             AS sensor_location,
    SPLIT_PART(METADATA$FILENAME, 'date=', 2)::DATE AS partition_date,
    METADATA$FILENAME                  AS source_file
  FROM @FSXN_BRONZE_STAGE/iot-sensors/ (FILE_FORMAT => 'BRONZE.PARQUET_FORMAT');

-- =============================================================================
-- 3. External Table: CUSTOMERS_CSV (CSV)
-- =============================================================================
-- Source: CSV files at bronze/customers/
-- Columns: customer_id, name, email, country, segment, created_at
-- Note: CSV columns are referenced positionally (c1, c2, ...)
-- =============================================================================
CREATE OR REPLACE EXTERNAL TABLE CUSTOMERS_CSV
  WITH LOCATION = @FSXN_BRONZE_STAGE/customers/
  AUTO_REFRESH = FALSE
  FILE_FORMAT = (FORMAT_NAME = 'BRONZE.CSV_FORMAT')
  COMMENT = 'Customer master data on FSx for ONTAP (CSV) — REQ-2'
  AS
  SELECT
    VALUE:c1::STRING                   AS customer_id,
    VALUE:c2::STRING                   AS name,
    VALUE:c3::STRING                   AS email,
    VALUE:c4::STRING                   AS country,
    VALUE:c5::STRING                   AS segment,
    VALUE:c6::TIMESTAMP_NTZ           AS created_at,
    METADATA$FILENAME                  AS source_file
  FROM @FSXN_BRONZE_STAGE/customers/ (FILE_FORMAT => 'BRONZE.CSV_FORMAT');

-- =============================================================================
-- 4. External Table: EVENTS_JSON (JSON)
-- =============================================================================
-- Source: JSON files at bronze/events/
-- Columns: event_id, event_type, timestamp, user_id, payload
-- =============================================================================
CREATE OR REPLACE EXTERNAL TABLE EVENTS_JSON
  WITH LOCATION = @FSXN_BRONZE_STAGE/events/
  AUTO_REFRESH = FALSE
  FILE_FORMAT = (FORMAT_NAME = 'BRONZE.JSON_FORMAT')
  COMMENT = 'Event stream data on FSx for ONTAP (JSON) — REQ-2'
  AS
  SELECT
    VALUE:event_id::STRING             AS event_id,
    VALUE:event_type::STRING           AS event_type,
    VALUE:timestamp::TIMESTAMP_NTZ     AS event_timestamp,
    VALUE:user_id::STRING              AS user_id,
    VALUE:payload::VARIANT             AS payload,
    METADATA$FILENAME                  AS source_file
  FROM @FSXN_BRONZE_STAGE/events/ (FILE_FORMAT => 'BRONZE.JSON_FORMAT');

-- =============================================================================
-- 5. Partition Metadata Refresh
-- =============================================================================
-- Since AUTO_REFRESH = FALSE (FSx for ONTAP S3 AP does not support S3 Event Notifications),
-- metadata must be refreshed manually after new files are added.
-- =============================================================================

-- Record start time for refresh latency measurement
-- ⏱ METRIC: REFRESH_START_TIME = CURRENT_TIMESTAMP()
ALTER EXTERNAL TABLE TRANSACTIONS REFRESH;
-- ⏱ METRIC: Record REFRESH duration (typically 5-30 seconds depending on file count)

ALTER EXTERNAL TABLE IOT_SENSORS REFRESH;
ALTER EXTERNAL TABLE CUSTOMERS_CSV REFRESH;
ALTER EXTERNAL TABLE EVENTS_JSON REFRESH;

-- =============================================================================
-- 6. Row Count Validation
-- =============================================================================
-- Verify data is accessible through each External Table.
-- ⏱ METRIC: Record query_time and rows_produced for each COUNT query.
-- =============================================================================

-- ⏱ METRIC: TRANSACTIONS_COUNT query — start timer
SELECT 'TRANSACTIONS' AS table_name, COUNT(*) AS row_count FROM TRANSACTIONS;
-- ⏱ METRIC: Record query_id from LAST_QUERY_ID() for performance analysis

-- ⏱ METRIC: IOT_SENSORS_COUNT query — start timer
SELECT 'IOT_SENSORS' AS table_name, COUNT(*) AS row_count FROM IOT_SENSORS;
-- ⏱ METRIC: Record query_id

-- ⏱ METRIC: CUSTOMERS_CSV_COUNT query — start timer
SELECT 'CUSTOMERS_CSV' AS table_name, COUNT(*) AS row_count FROM CUSTOMERS_CSV;
-- ⏱ METRIC: Record query_id

-- ⏱ METRIC: EVENTS_JSON_COUNT query — start timer
SELECT 'EVENTS_JSON' AS table_name, COUNT(*) AS row_count FROM EVENTS_JSON;
-- ⏱ METRIC: Record query_id

-- =============================================================================
-- 7. Analytical Queries — Aggregation & GROUP BY
-- =============================================================================
-- Demonstrates analytical query capability on External Tables.
-- These queries push down predicates and aggregations to the scan layer.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 7.1 Transaction Revenue by Category
-- ---------------------------------------------------------------------------
-- ⏱ METRIC: TRANSACTIONS_ANALYTICS query — record query_time, bytes_scanned
SELECT
    category,
    COUNT(*)           AS transaction_count,
    SUM(amount)        AS total_amount,
    AVG(amount)        AS avg_amount,
    MIN(amount)        AS min_amount,
    MAX(amount)        AS max_amount
FROM TRANSACTIONS
GROUP BY category
ORDER BY total_amount DESC;
-- ⏱ METRIC: Use QUERY_HISTORY to capture bytes_scanned, compilation_time, execution_time

-- ---------------------------------------------------------------------------
-- 7.2 IoT Sensors — Partition Pruning Query (date filter)
-- ---------------------------------------------------------------------------
-- This query demonstrates partition pruning: only files in the date=2024-03-15
-- partition are scanned, significantly reducing I/O for large datasets.
-- ⏱ METRIC: IOT_PARTITION_QUERY — record partitions_scanned, bytes_scanned
SELECT
    sensor_id,
    reading_timestamp,
    temperature,
    humidity,
    pressure,
    sensor_location
FROM IOT_SENSORS
WHERE partition_date = '2024-03-15'
ORDER BY reading_timestamp
LIMIT 100;
-- ⏱ METRIC: Compare bytes_scanned with full-table scan to show partition benefit

-- ---------------------------------------------------------------------------
-- 7.3 IoT Sensors — Aggregation by Location
-- ---------------------------------------------------------------------------
-- ⏱ METRIC: IOT_ANALYTICS query — record query_time
SELECT
    sensor_location,
    COUNT(*)                AS reading_count,
    AVG(temperature)        AS avg_temperature,
    AVG(humidity)           AS avg_humidity,
    AVG(pressure)           AS avg_pressure
FROM IOT_SENSORS
GROUP BY sensor_location
ORDER BY reading_count DESC;

-- ---------------------------------------------------------------------------
-- 7.4 Customers by Country and Segment
-- ---------------------------------------------------------------------------
-- ⏱ METRIC: CUSTOMERS_ANALYTICS query — record query_time
SELECT
    country,
    segment,
    COUNT(*) AS customer_count
FROM CUSTOMERS_CSV
GROUP BY country, segment
ORDER BY customer_count DESC;

-- ---------------------------------------------------------------------------
-- 7.5 Events by Type (JSON)
-- ---------------------------------------------------------------------------
-- ⏱ METRIC: EVENTS_ANALYTICS query — record query_time
SELECT
    event_type,
    COUNT(*)                                    AS event_count,
    MIN(event_timestamp)                        AS first_event,
    MAX(event_timestamp)                        AS last_event
FROM EVENTS_JSON
GROUP BY event_type
ORDER BY event_count DESC;

-- =============================================================================
-- 8. Performance Metrics Collection
-- =============================================================================
-- Query QUERY_HISTORY to capture performance metrics for the above queries.
-- Run this after executing the analytical queries above.
-- =============================================================================

-- Retrieve performance metrics for recent queries on External Tables
SELECT
    query_id,
    query_text,
    execution_status,
    total_elapsed_time   AS elapsed_ms,
    bytes_scanned,
    rows_produced,
    compilation_time     AS compile_ms,
    execution_time       AS exec_ms,
    partitions_scanned,
    partitions_total
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
    RESULT_LIMIT => 20,
    END_TIME_RANGE_START => DATEADD('minute', -10, CURRENT_TIMESTAMP())
))
WHERE query_text ILIKE '%TRANSACTIONS%'
   OR query_text ILIKE '%IOT_SENSORS%'
   OR query_text ILIKE '%CUSTOMERS_CSV%'
   OR query_text ILIKE '%EVENTS_JSON%'
ORDER BY start_time DESC;

-- =============================================================================
-- TROUBLESHOOTING
-- =============================================================================
-- If External Table queries return 0 rows:
--   1. Run ALTER EXTERNAL TABLE <name> REFRESH; to update metadata
--   2. Verify files exist: LIST @FSXN_BRONZE_STAGE/transactions/;
--   3. Check file format matches data: SELECT $1 FROM @FSXN_BRONZE_STAGE/transactions/ LIMIT 5;
--
-- If partition pruning is not working (IOT_SENSORS):
--   1. Verify file path contains 'date=YYYY-MM-DD' pattern
--   2. Check: SELECT DISTINCT partition_date FROM IOT_SENSORS;
--   3. Ensure WHERE clause uses partition_date (not reading_timestamp)
--
-- If query is slow:
--   1. Check warehouse size (MEDIUM recommended for External Tables)
--   2. Verify bytes_scanned in QUERY_HISTORY — large scans indicate no pruning
--   3. Consider partitioning strategy for frequently filtered columns
-- =============================================================================

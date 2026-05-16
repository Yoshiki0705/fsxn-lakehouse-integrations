-- =============================================================================
-- 04 - External Tables on FSxN
-- =============================================================================
-- Creates External Tables that query data directly on FSx for NetApp ONTAP
-- via S3 Access Point. Data remains on FSxN (no copy into Snowflake).
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;

-- =============================================================================
-- External Table: Transactions (Parquet)
-- =============================================================================
USE SCHEMA BRONZE;

CREATE OR REPLACE EXTERNAL TABLE TRANSACTIONS
  WITH LOCATION = @FSXN_BRONZE_STAGE/transactions/
  AUTO_REFRESH = FALSE  -- Set TRUE with SNS notification for auto-refresh
  FILE_FORMAT = (FORMAT_NAME = 'FSXN_LAKEHOUSE.PUBLIC.PARQUET_FORMAT')
  COMMENT = 'Financial transactions on FSxN (Parquet)'
  AS
  SELECT
    VALUE:transaction_id::STRING AS transaction_id,
    VALUE:timestamp::TIMESTAMP_NTZ AS transaction_timestamp,
    VALUE:account_id::STRING AS account_id,
    VALUE:amount::FLOAT AS amount,
    VALUE:currency::STRING AS currency,
    VALUE:category::STRING AS category,
    VALUE:status::STRING AS status,
    METADATA$FILENAME AS source_file,
    METADATA$FILE_ROW_NUMBER AS file_row_number
  FROM @FSXN_BRONZE_STAGE/transactions/ (FILE_FORMAT => 'FSXN_LAKEHOUSE.PUBLIC.PARQUET_FORMAT');

-- =============================================================================
-- External Table: IoT Sensors (Parquet, Partitioned)
-- =============================================================================
CREATE OR REPLACE EXTERNAL TABLE IOT_SENSORS
  WITH LOCATION = @FSXN_BRONZE_STAGE/iot-sensors/
  AUTO_REFRESH = FALSE
  PARTITION BY (PARTITION_DATE)
  FILE_FORMAT = (FORMAT_NAME = 'FSXN_LAKEHOUSE.PUBLIC.PARQUET_FORMAT')
  COMMENT = 'IoT sensor data on FSxN (Parquet, partitioned by date)'
  AS
  SELECT
    VALUE:sensor_id::STRING AS sensor_id,
    VALUE:timestamp::TIMESTAMP_NTZ AS reading_timestamp,
    VALUE:temperature::FLOAT AS temperature,
    VALUE:humidity::FLOAT AS humidity,
    VALUE:pressure::FLOAT AS pressure,
    VALUE:vibration::FLOAT AS vibration,
    VALUE:location::STRING AS plant_location,
    SPLIT_PART(METADATA$FILENAME, 'date=', 2)::DATE AS partition_date,
    METADATA$FILENAME AS source_file
  FROM @FSXN_BRONZE_STAGE/iot-sensors/ (FILE_FORMAT => 'FSXN_LAKEHOUSE.PUBLIC.PARQUET_FORMAT');

-- =============================================================================
-- External Table: Customers (CSV)
-- =============================================================================
CREATE OR REPLACE EXTERNAL TABLE CUSTOMERS_CSV
  WITH LOCATION = @FSXN_BRONZE_STAGE/customers/
  AUTO_REFRESH = FALSE
  FILE_FORMAT = (FORMAT_NAME = 'FSXN_LAKEHOUSE.PUBLIC.CSV_FORMAT')
  COMMENT = 'Customer data on FSxN (CSV)'
  AS
  SELECT
    VALUE:c1::STRING AS customer_id,
    VALUE:c2::STRING AS name,
    VALUE:c3::STRING AS email,
    VALUE:c4::STRING AS country,
    VALUE:c5::TIMESTAMP_NTZ AS created_at,
    METADATA$FILENAME AS source_file
  FROM @FSXN_BRONZE_STAGE/customers/ (FILE_FORMAT => 'FSXN_LAKEHOUSE.PUBLIC.CSV_FORMAT');

-- =============================================================================
-- External Table: Events (JSON)
-- =============================================================================
CREATE OR REPLACE EXTERNAL TABLE EVENTS_JSON
  WITH LOCATION = @FSXN_BRONZE_STAGE/events/
  AUTO_REFRESH = FALSE
  FILE_FORMAT = (FORMAT_NAME = 'FSXN_LAKEHOUSE.PUBLIC.JSON_FORMAT')
  COMMENT = 'Event stream data on FSxN (JSON)'
  AS
  SELECT
    VALUE:event_id::STRING AS event_id,
    VALUE:event_type::STRING AS event_type,
    VALUE:timestamp::TIMESTAMP_NTZ AS event_timestamp,
    VALUE:user_id::STRING AS user_id,
    VALUE:payload::VARIANT AS payload,
    METADATA$FILENAME AS source_file
  FROM @FSXN_BRONZE_STAGE/events/ (FILE_FORMAT => 'FSXN_LAKEHOUSE.PUBLIC.JSON_FORMAT');

-- =============================================================================
-- Validate External Tables
-- =============================================================================

-- Check table metadata
SELECT * FROM TRANSACTIONS LIMIT 10;
SELECT * FROM IOT_SENSORS LIMIT 10;
SELECT * FROM CUSTOMERS_CSV LIMIT 10;
SELECT * FROM EVENTS_JSON LIMIT 10;

-- Check partition metadata
SELECT DISTINCT partition_date FROM IOT_SENSORS ORDER BY partition_date;

-- Refresh metadata manually (if AUTO_REFRESH = FALSE)
ALTER EXTERNAL TABLE TRANSACTIONS REFRESH;
ALTER EXTERNAL TABLE IOT_SENSORS REFRESH;

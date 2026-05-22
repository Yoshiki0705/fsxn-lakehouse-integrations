-- =============================================================================
-- 03 - File Format Definitions
-- =============================================================================
-- Defines reusable file formats for External Tables and Snowpipe ingestion.
-- All formats are created in the BRONZE schema since that is where raw data
-- lands from FSxN via S3 Access Point.
--
-- Format → External Table mapping:
--   PARQUET_FORMAT  → TRANSACTIONS, IOT_SENSORS (04_external_table.sql)
--   CSV_FORMAT      → CUSTOMERS_CSV (04_external_table.sql)
--   JSON_FORMAT     → EVENTS_JSON (04_external_table.sql)
--   NDJSON_FORMAT   → FSXN_EVENTS_PIPE / Snowpipe ingestion (06_snowpipe.sql)
--
-- Requirements: REQ-2 (External Table queries on structured data)
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;

-- =============================================================================
-- PARQUET_FORMAT
-- =============================================================================
-- Used by: TRANSACTIONS External Table, IOT_SENSORS External Table
-- Parquet is the recommended columnar format for analytics workloads.
-- SNAPPY compression provides a good balance of speed and compression ratio,
-- and is the default output of most Spark/Pandas writers.
-- =============================================================================
CREATE OR REPLACE FILE FORMAT BRONZE.PARQUET_FORMAT
  TYPE = PARQUET
  COMPRESSION = SNAPPY
  COMMENT = 'Parquet format (Snappy) — used by TRANSACTIONS and IOT_SENSORS External Tables';

-- =============================================================================
-- CSV_FORMAT
-- =============================================================================
-- Used by: CUSTOMERS_CSV External Table
-- Handles standard CSV exports with a header row. FIELD_OPTIONALLY_ENCLOSED_BY
-- ensures quoted fields with commas are parsed correctly. NULL_IF maps empty
-- strings and literal 'NULL' to SQL NULL values.
-- =============================================================================
CREATE OR REPLACE FILE FORMAT BRONZE.CSV_FORMAT
  TYPE = CSV
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  NULL_IF = ('', 'NULL')
  COMMENT = 'CSV format (header skip, quoted fields) — used by CUSTOMERS_CSV External Table';

-- =============================================================================
-- JSON_FORMAT
-- =============================================================================
-- Used by: EVENTS_JSON External Table
-- STRIP_OUTER_ARRAY = FALSE because each file contains a JSON array wrapper
-- that we want to preserve (Snowflake auto-expands arrays in External Tables).
-- COMPRESSION = NONE since FSxN stores uncompressed JSON files written via NFS.
-- =============================================================================
CREATE OR REPLACE FILE FORMAT BRONZE.JSON_FORMAT
  TYPE = JSON
  STRIP_OUTER_ARRAY = FALSE
  COMPRESSION = NONE
  COMMENT = 'JSON format (no array strip, uncompressed) — used by EVENTS_JSON External Table';

-- =============================================================================
-- NDJSON_FORMAT
-- =============================================================================
-- Used by: Snowpipe FSXN_EVENTS_PIPE (06_snowpipe.sql)
-- Newline-delimited JSON (JSON Lines) where each line is a separate JSON object.
-- STRIP_OUTER_ARRAY = FALSE because there is no array wrapper — each line is
-- an independent record. This is the standard format for streaming/append
-- workloads where new events are appended as individual lines.
-- =============================================================================
CREATE OR REPLACE FILE FORMAT BRONZE.NDJSON_FORMAT
  TYPE = JSON
  STRIP_OUTER_ARRAY = FALSE
  COMMENT = 'NDJSON (JSON Lines) format — used by Snowpipe for streaming event ingestion';

-- =============================================================================
-- Verification
-- =============================================================================
SHOW FILE FORMATS IN SCHEMA BRONZE;

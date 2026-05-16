-- =============================================================================
-- 03 - File Format Definitions
-- =============================================================================
-- Defines reusable file formats for Parquet, CSV, JSON, and other formats
-- used with FSxN External Stages.
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA PUBLIC;

-- =============================================================================
-- Parquet Format (recommended for analytics)
-- =============================================================================
CREATE OR REPLACE FILE FORMAT PARQUET_FORMAT
  TYPE = PARQUET
  COMPRESSION = AUTO
  BINARY_AS_TEXT = FALSE
  COMMENT = 'Parquet format for columnar analytics data on FSxN';

-- =============================================================================
-- CSV Format (legacy data ingestion)
-- =============================================================================
CREATE OR REPLACE FILE FORMAT CSV_FORMAT
  TYPE = CSV
  COMPRESSION = AUTO
  FIELD_DELIMITER = ','
  RECORD_DELIMITER = '\n'
  SKIP_HEADER = 1
  FIELD_OPTIONALLY_ENCLOSED_BY = '"'
  TRIM_SPACE = TRUE
  NULL_IF = ('NULL', 'null', '')
  ERROR_ON_COLUMN_COUNT_MISMATCH = FALSE
  COMMENT = 'CSV format for legacy data on FSxN';

-- =============================================================================
-- JSON Format (semi-structured data)
-- =============================================================================
CREATE OR REPLACE FILE FORMAT JSON_FORMAT
  TYPE = JSON
  COMPRESSION = AUTO
  STRIP_OUTER_ARRAY = TRUE
  STRIP_NULL_VALUES = FALSE
  COMMENT = 'JSON format for semi-structured data on FSxN';

-- =============================================================================
-- NDJSON Format (newline-delimited JSON / JSON Lines)
-- =============================================================================
CREATE OR REPLACE FILE FORMAT NDJSON_FORMAT
  TYPE = JSON
  COMPRESSION = AUTO
  STRIP_OUTER_ARRAY = FALSE
  STRIP_NULL_VALUES = FALSE
  COMMENT = 'NDJSON (JSON Lines) format for streaming data on FSxN';

-- =============================================================================
-- ORC Format
-- =============================================================================
CREATE OR REPLACE FILE FORMAT ORC_FORMAT
  TYPE = ORC
  TRIM_SPACE = TRUE
  COMMENT = 'ORC format for Hive-compatible data on FSxN';

-- =============================================================================
-- Avro Format
-- =============================================================================
CREATE OR REPLACE FILE FORMAT AVRO_FORMAT
  TYPE = AVRO
  TRIM_SPACE = TRUE
  COMMENT = 'Avro format for schema-evolution data on FSxN';

-- =============================================================================
-- Verify formats
-- =============================================================================
SHOW FILE FORMATS IN DATABASE FSXN_LAKEHOUSE;

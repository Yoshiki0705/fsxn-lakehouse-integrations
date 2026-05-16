-- =============================================================================
-- 06 - Snowpipe Auto-Ingest from FSxN
-- =============================================================================
-- Configures Snowpipe for automatic data ingestion when new files appear
-- on FSx for NetApp ONTAP via S3 Access Point.
--
-- Note: Snowpipe with FSxN requires SNS notification setup because
-- FSxN S3 does not natively support S3 Event Notifications.
-- Workaround: Use a Lambda function to detect new files and publish to SNS.
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA BRONZE;

-- =============================================================================
-- Target Table for Snowpipe
-- =============================================================================
CREATE OR REPLACE TABLE RAW_EVENTS (
  event_id STRING,
  event_type STRING,
  event_timestamp TIMESTAMP_NTZ,
  user_id STRING,
  payload VARIANT,
  source_file STRING,
  ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
COMMENT = 'Raw events ingested via Snowpipe from FSxN';

-- =============================================================================
-- Snowpipe Definition
-- =============================================================================
CREATE OR REPLACE PIPE FSXN_EVENTS_PIPE
  AUTO_INGEST = TRUE
  -- AWS_SNS_TOPIC = '<SnowpipeSNSTopicArn from CloudFormation>'
  COMMENT = 'Auto-ingest events from FSxN bronze layer'
  AS
  COPY INTO RAW_EVENTS (event_id, event_type, event_timestamp, user_id, payload, source_file)
  FROM (
    SELECT
      $1:event_id::STRING,
      $1:event_type::STRING,
      $1:timestamp::TIMESTAMP_NTZ,
      $1:user_id::STRING,
      $1:payload::VARIANT,
      METADATA$FILENAME
    FROM @FSXN_BRONZE_STAGE/events/
  )
  FILE_FORMAT = (FORMAT_NAME = 'FSXN_LAKEHOUSE.PUBLIC.JSON_FORMAT')
  ON_ERROR = 'CONTINUE';

-- =============================================================================
-- Get Snowpipe notification channel (for SNS subscription)
-- =============================================================================
SHOW PIPES LIKE 'FSXN_EVENTS_PIPE';
-- Note the 'notification_channel' value → Use to subscribe SNS topic

-- =============================================================================
-- Manual Pipe Refresh (for testing without SNS)
-- =============================================================================
-- ALTER PIPE FSXN_EVENTS_PIPE REFRESH;

-- =============================================================================
-- Monitor Pipe Status
-- =============================================================================
SELECT SYSTEM$PIPE_STATUS('FSXN_EVENTS_PIPE');

-- Check copy history
SELECT *
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
  TABLE_NAME => 'RAW_EVENTS',
  START_TIME => DATEADD('hour', -24, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;

-- =============================================================================
-- Snowpipe + FSxN Architecture Notes
-- =============================================================================
-- Since FSxN S3 protocol does not support native S3 Event Notifications,
-- use one of these patterns for auto-ingest:
--
-- Pattern A: Lambda Polling (Simple)
--   Lambda (scheduled) → List new files on S3 AP → Publish to SNS → Snowpipe
--
-- Pattern B: ONTAP FPolicy (Advanced)
--   ONTAP FPolicy → Detect file create → Lambda → SNS → Snowpipe
--
-- Pattern C: Manual Refresh (Development)
--   ALTER PIPE FSXN_EVENTS_PIPE REFRESH;
--
-- Recommended: Pattern A for production, Pattern C for development

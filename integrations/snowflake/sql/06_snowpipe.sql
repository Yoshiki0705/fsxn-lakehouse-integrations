-- =============================================================================
-- 06 - Snowpipe Auto-Ingest (FPolicy Event-Driven)
-- =============================================================================
-- Configures Snowpipe for automatic data ingestion when new files appear
-- on FSx for NetApp ONTAP via S3 Access Point.
--
-- Requirements: REQ-4 (Snowpipe auto-ingest, FPolicy event-driven)
--
-- =============================================================================
-- FPolicy → SQS → Lambda → SNS → Snowpipe Flow
-- =============================================================================
--
-- FSxN S3 Access Point does NOT support native S3 Event Notifications.
-- Instead, we use ONTAP FPolicy for real-time file event detection:
--
--   1. NFS Client writes a file to FSxN volume (e.g., /bronze/events/new.json)
--   2. ONTAP FPolicy (asynchronous mode) detects the file create operation
--   3. FPolicy Server (ECS Fargate) receives the event notification
--   4. Fargate enqueues the event to SQS (event buffer / decoupling)
--   5. Lambda (Bridge) consumes from SQS, transforms to S3 Event format
--   6. Lambda publishes the S3-compatible event to SNS Topic
--   7. SNS delivers to Snowflake's SQS queue (notification_channel)
--   8. Snowpipe triggers COPY INTO from the S3 Access Point path
--
-- Latency comparison:
--   - Lambda Polling (legacy):  5-7 minutes (polling interval + COPY time)
--   - FPolicy (event-driven):   <30 seconds (event detection + pipeline + COPY)
--   - Improvement:              90%+ latency reduction
--
-- Architecture diagram:
--
--   NFS Client ──▶ ONTAP FPolicy ──▶ Fargate ──▶ SQS ──▶ Lambda ──▶ SNS
--                                                                      │
--                                                                      ▼
--                                                              Snowflake SQS
--                                                              (Snowpipe)
--                                                                      │
--                                                                      ▼
--                                                              COPY INTO
--                                                              RAW_EVENTS
--
-- Key constraints:
--   - FPolicy requires NFSv4.1 or NFSv3 (NFSv4.2 not supported for monitoring)
--   - Fargate task IP is used directly (NLB incompatible with FPolicy binary protocol)
--   - IP Updater Lambda handles Fargate task restarts automatically
--   - FPolicy mode must be 'asynchronous' to avoid blocking application I/O
--
-- =============================================================================

USE DATABASE FSXN_LAKEHOUSE;
USE SCHEMA BRONZE;

-- =============================================================================
-- 1. Target Table for Snowpipe Ingestion
-- =============================================================================
-- RAW_EVENTS stores all events ingested via Snowpipe from the FSxN bronze layer.
-- The payload column (VARIANT) allows flexible schema for different event types.
-- ingested_at tracks when each record was loaded by Snowpipe.
-- =============================================================================

CREATE OR REPLACE TABLE RAW_EVENTS (
    event_id        STRING        COMMENT 'Unique event identifier',
    event_type      STRING        COMMENT 'Event category (e.g., page_view, purchase, login)',
    timestamp       TIMESTAMP_NTZ COMMENT 'Event timestamp from source system',
    user_id         STRING        COMMENT 'User who triggered the event',
    payload         VARIANT       COMMENT 'Full event payload as semi-structured JSON',
    ingested_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP() COMMENT 'Snowpipe ingestion timestamp'
)
COMMENT = 'Raw events ingested via Snowpipe from FSxN bronze layer (FPolicy event-driven)';

-- =============================================================================
-- 2. Snowpipe Definition (AUTO_INGEST = TRUE)
-- =============================================================================
-- The pipe monitors the SNS topic for new file notifications.
-- AWS_SNS_TOPIC receives messages from the Lambda Bridge that transforms
-- FPolicy events into S3 Event-compatible format.
--
-- MATCH_BY_COLUMN_NAME = 'CASE_INSENSITIVE' allows the COPY to map JSON keys
-- to table columns by name, regardless of case differences between the source
-- JSON field names and the Snowflake column names.
-- =============================================================================

CREATE OR REPLACE PIPE FSXN_EVENTS_PIPE
    AUTO_INGEST = TRUE
    AWS_SNS_TOPIC = '<SNS_TOPIC_ARN>'  -- Replace with fpolicy-routing stack output: SnowpipeSNSTopicArn
    COMMENT = 'Auto-ingest events from FSxN bronze layer via FPolicy → SQS → Lambda → SNS pipeline'
AS
COPY INTO RAW_EVENTS
FROM @FSXN_BRONZE_STAGE/events/
FILE_FORMAT = (FORMAT_NAME = BRONZE.NDJSON_FORMAT)
MATCH_BY_COLUMN_NAME = 'CASE_INSENSITIVE'
ON_ERROR = 'CONTINUE';

-- =============================================================================
-- 3. Show Pipes — Retrieve notification_channel (SQS ARN)
-- =============================================================================
-- After pipe creation, SHOW PIPES returns the notification_channel column.
-- This is the Snowflake-managed SQS queue ARN that must be subscribed to
-- the SNS topic (from fpolicy-routing stack) for auto-ingest to work.
--
-- Steps after running SHOW PIPES:
--   1. Copy the notification_channel value (SQS ARN)
--   2. Subscribe this SQS ARN to the SNS topic in the fpolicy-routing stack
--   3. The SNS subscription enables message delivery to Snowpipe
-- =============================================================================

SHOW PIPES LIKE 'FSXN_EVENTS_PIPE';

-- Expected output includes:
--   notification_channel = arn:aws:sqs:<region>:<snowflake-account>:sf-snowpipe-...
-- Use this ARN to create an SNS subscription in the fpolicy-routing stack.

-- =============================================================================
-- 4. Resume Pipe Execution
-- =============================================================================
-- Pipes are created in a paused state by default when using AUTO_INGEST.
-- Resume the pipe to begin processing incoming notifications.
-- =============================================================================

ALTER PIPE FSXN_EVENTS_PIPE SET PIPE_EXECUTION_PAUSED = FALSE;

-- =============================================================================
-- 5. Pipe Status Check
-- =============================================================================

SELECT SYSTEM$PIPE_STATUS('FSXN_EVENTS_PIPE');

-- Expected output (when running):
-- {"executionState":"RUNNING","pendingFileCount":0,...}

-- =============================================================================
-- 6. COPY_HISTORY — Verify Ingestion Activity
-- =============================================================================
-- Query the last 24 hours of copy history to confirm Snowpipe is loading files.
-- This is the primary verification query for REQ-4 acceptance criteria.
-- =============================================================================

SELECT *
FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(
    TABLE_NAME => 'RAW_EVENTS',
    START_TIME => DATEADD(hours, -24, CURRENT_TIMESTAMP())
))
ORDER BY LAST_LOAD_TIME DESC;

-- =============================================================================
-- 7. Verification Query — Confirm Data in Target Table
-- =============================================================================
-- After Snowpipe processes files, verify that events appear in RAW_EVENTS.
-- Records should appear within <30 seconds of file creation on FSxN (FPolicy mode)
-- or within 5-7 minutes (Lambda polling legacy mode).
-- =============================================================================

SELECT *
FROM RAW_EVENTS
ORDER BY ingested_at DESC
LIMIT 10;

-- =============================================================================
-- Manual Pipe Refresh (for development/testing without SNS)
-- =============================================================================
-- Use this command to manually trigger Snowpipe to scan for new files
-- without waiting for an SNS notification. Useful during initial setup.
-- =============================================================================

-- ALTER PIPE FSXN_EVENTS_PIPE REFRESH;

-- =============================================================================
-- Troubleshooting
-- =============================================================================
-- If COPY_HISTORY is empty after file upload:
--   1. Check SYSTEM$PIPE_STATUS — ensure executionState is RUNNING
--   2. Verify SNS subscription exists (notification_channel → SNS topic)
--   3. Check Lambda Bridge CloudWatch logs for errors
--   4. Verify FPolicy is connected: `fpolicy show-engine` on ONTAP CLI
--   5. Confirm file format matches: NDJSON (one JSON object per line)
--   6. Try manual refresh: ALTER PIPE FSXN_EVENTS_PIPE REFRESH;
--
-- If pipe is paused unexpectedly:
--   ALTER PIPE FSXN_EVENTS_PIPE SET PIPE_EXECUTION_PAUSED = FALSE;
--
-- To pause pipe (maintenance):
--   ALTER PIPE FSXN_EVENTS_PIPE SET PIPE_EXECUTION_PAUSED = TRUE;
-- =============================================================================

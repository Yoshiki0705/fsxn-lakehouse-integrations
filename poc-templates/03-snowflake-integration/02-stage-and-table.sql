-- FSx for ONTAP S3 Access Points — Snowflake Stage + External Table
-- Step 2: Stage and External Table creation
--
-- Replace:
--   <AP_ALIAS> with your S3 Access Point alias
--   <REGION> with your AWS region (e.g., ap-northeast-1)
--   <ACCOUNT_ID> with your AWS account ID
--   <AP_NAME> with your access point name

-- ============================================================
-- 1. Create Stage WITH AWS_ACCESS_POINT_ARN (critical!)
-- ============================================================
CREATE OR REPLACE STAGE fsxn_poc_stage
  STORAGE_INTEGRATION = fsxn_poc_integration
  URL = 's3://<AP_ALIAS>/'
  AWS_ACCESS_POINT_ARN = 'arn:aws:s3:<REGION>:<ACCOUNT_ID>:accesspoint/<AP_NAME>'
  FILE_FORMAT = (TYPE = PARQUET);

-- ============================================================
-- 2. Verify: LIST should show files
-- ============================================================
LIST @fsxn_poc_stage/sensor-data/;

-- ============================================================
-- 3. Verify: SELECT should return data (requires AWS_ACCESS_POINT_ARN!)
-- ============================================================
SELECT $1 FROM @fsxn_poc_stage/sensor-data/sensor_data.parquet LIMIT 5;

-- ============================================================
-- 4. Create External Table
-- ============================================================
CREATE OR REPLACE EXTERNAL TABLE fsxn_poc_sensor_ext
  LOCATION = @fsxn_poc_stage/sensor-data/
  FILE_FORMAT = (TYPE = PARQUET)
  AUTO_REFRESH = FALSE;

-- ============================================================
-- 5. Query External Table
-- ============================================================
SELECT
  VALUE:status::STRING AS status,
  COUNT(*) AS count,
  ROUND(AVG(VALUE:temperature::FLOAT), 2) AS avg_temp
FROM fsxn_poc_sensor_ext
GROUP BY VALUE:status::STRING
ORDER BY count DESC;

-- ============================================================
-- 6. Enable Directory Table (file catalog)
-- ============================================================
ALTER STAGE fsxn_poc_stage SET DIRECTORY = (ENABLE = TRUE);
ALTER STAGE fsxn_poc_stage REFRESH;

SELECT RELATIVE_PATH, SIZE, LAST_MODIFIED
FROM DIRECTORY(@fsxn_poc_stage)
ORDER BY LAST_MODIFIED DESC
LIMIT 20;

-- ============================================================
-- 7. Apply Governance Tag
-- ============================================================
CREATE TAG IF NOT EXISTS sensitivity ALLOWED_VALUES 'public', 'internal', 'confidential';
ALTER TABLE fsxn_poc_sensor_ext SET TAG sensitivity = 'internal';
SELECT SYSTEM$GET_TAG('sensitivity', 'fsxn_poc_sensor_ext', 'TABLE');

-- ============================================================
-- Next: Run 03-cortex-ai-demo.sql for AI functions
-- ============================================================

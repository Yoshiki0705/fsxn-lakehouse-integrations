-- FSx for ONTAP S3 Access Points — Snowflake Cortex AI Demo
-- Step 3: AI functions on FSx data (zero-copy, no COPY INTO needed)
--
-- Prerequisites: 02-stage-and-table.sql completed successfully

-- ============================================================
-- 1. CORTEX.SUMMARIZE — Text summarization (zero-copy)
-- ============================================================
SELECT
  VALUE:device_id::STRING AS device_id,
  VALUE:status::STRING AS status,
  SNOWFLAKE.CORTEX.SUMMARIZE(
    'Device ' || VALUE:device_id::STRING || ' reported ' || VALUE:status::STRING ||
    ' status with temperature ' || VALUE:temperature::STRING || '°C and humidity ' ||
    VALUE:humidity::STRING || '%'
  ) AS ai_summary
FROM fsxn_poc_sensor_ext
WHERE VALUE:status::STRING = 'critical'
LIMIT 3;

-- ============================================================
-- 2. CORTEX.SENTIMENT — Sentiment analysis (zero-copy)
-- ============================================================
SELECT
  VALUE:device_id::STRING AS device_id,
  VALUE:status::STRING AS status,
  SNOWFLAKE.CORTEX.SENTIMENT(
    'The sensor reading shows ' || VALUE:status::STRING || ' condition with temperature at ' ||
    VALUE:temperature::STRING || ' degrees'
  ) AS sentiment_score
FROM fsxn_poc_sensor_ext
LIMIT 5;

-- ============================================================
-- 3. CORTEX.COMPLETE — AI analysis (zero-copy)
-- ============================================================
SELECT
  VALUE:device_id::STRING AS device_id,
  SNOWFLAKE.CORTEX.COMPLETE('mistral-large2',
    'Analyze this IoT sensor reading and identify if there are any anomalies. ' ||
    'Temperature: ' || VALUE:temperature::STRING || '°C, ' ||
    'Humidity: ' || VALUE:humidity::STRING || '%, ' ||
    'Pressure: ' || VALUE:pressure::STRING || ' hPa, ' ||
    'Status: ' || VALUE:status::STRING
  ) AS ai_analysis
FROM fsxn_poc_sensor_ext
WHERE VALUE:status::STRING = 'critical'
LIMIT 1;

-- ============================================================
-- 4. CORTEX.TRANSLATE — Multi-language (zero-copy)
-- ============================================================
SELECT
  SNOWFLAKE.CORTEX.TRANSLATE(
    'Critical temperature detected at device ' || VALUE:device_id::STRING,
    'en', 'ja'
  ) AS japanese_alert
FROM fsxn_poc_sensor_ext
WHERE VALUE:status::STRING = 'critical'
LIMIT 3;

-- ============================================================
-- 5. PARSE_DOCUMENT — OCR on images (zero-copy, if images exist)
-- ============================================================
-- Uncomment if you have image/PDF files on the stage:
-- SELECT SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
--   @fsxn_poc_stage,
--   'documents/sample.png',
--   {'mode': 'OCR'}
-- ) AS ocr_result;

-- ============================================================
-- 6. GET_PRESIGNED_URL — File download URL (for unstructured data)
-- ============================================================
SELECT
  RELATIVE_PATH,
  SIZE,
  GET_PRESIGNED_URL(@fsxn_poc_stage, RELATIVE_PATH, 3600) AS download_url
FROM DIRECTORY(@fsxn_poc_stage)
LIMIT 5;

-- ============================================================
-- Summary: What works on FSx S3 AP External Table (zero-copy)
-- ============================================================
-- ✅ CORTEX.SUMMARIZE — Text summarization
-- ✅ CORTEX.TRANSLATE — Multi-language translation
-- ✅ CORTEX.SENTIMENT — Sentiment scoring
-- ✅ CORTEX.COMPLETE (text) — AI analysis
-- ✅ CORTEX.EXTRACT_ANSWER — Information extraction
-- ✅ PARSE_DOCUMENT — OCR on images/PDFs
-- ✅ GET_PRESIGNED_URL — File download URLs
-- ✅ BUILD_SCOPED_FILE_URL — Governed file access
--
-- ❌ CORTEX.COMPLETE (multimodal/vision) — Requires COPY FILES to internal stage
-- ❌ Cortex Search Service — Requires COPY INTO internal table
--
-- For Vision AI and Cortex Search, see 04-dynamic-table.sql

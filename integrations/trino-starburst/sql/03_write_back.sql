-- Write-back test: CTAS to FSx for ONTAP via S3 AP
-- This tests PutObject (flat Parquet write) — expected to WORK

-- Create output schema
CREATE SCHEMA IF NOT EXISTS fsxn.analytics_output
WITH (location = 's3://<FSX_S3_AP_ALIAS>/trino-output/');

-- CTAS: Write aggregated results back to FSx for ONTAP
CREATE TABLE fsxn.analytics_output.hourly_summary
WITH (format = 'PARQUET')
AS
SELECT
    date_trunc('hour', timestamp) AS hour,
    status,
    COUNT(*) AS reading_count,
    AVG(temperature) AS avg_temperature,
    AVG(humidity) AS avg_humidity,
    AVG(pressure) AS avg_pressure
FROM fsxn.sensor_data.readings
GROUP BY date_trunc('hour', timestamp), status;

-- Verify write-back
SELECT * FROM fsxn.analytics_output.hourly_summary LIMIT 10;

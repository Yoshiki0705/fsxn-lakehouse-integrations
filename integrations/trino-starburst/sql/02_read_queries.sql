-- Verification queries for FSx for ONTAP S3 AP via Trino
-- Run these after creating the schema and table

-- 1. Basic count
SELECT COUNT(*) AS total_rows FROM fsxn.sensor_data.readings;

-- 2. Group by aggregation
SELECT
    status,
    COUNT(*) AS count,
    AVG(temperature) AS avg_temp,
    MIN(temperature) AS min_temp,
    MAX(temperature) AS max_temp
FROM fsxn.sensor_data.readings
GROUP BY status;

-- 3. Time-based aggregation
SELECT
    date_trunc('hour', timestamp) AS hour,
    COUNT(*) AS readings,
    AVG(temperature) AS avg_temp
FROM fsxn.sensor_data.readings
GROUP BY date_trunc('hour', timestamp)
ORDER BY hour
LIMIT 24;

-- 4. Window function
SELECT
    device_id,
    temperature,
    AVG(temperature) OVER (
        PARTITION BY device_id
        ORDER BY timestamp
        ROWS BETWEEN 5 PRECEDING AND CURRENT ROW
    ) AS moving_avg
FROM fsxn.sensor_data.readings
LIMIT 100;

-- 5. Predicate pushdown verification
-- Trino should push the WHERE clause to S3 (Parquet predicate pushdown)
SELECT COUNT(*) FROM fsxn.sensor_data.readings
WHERE status = 'normal' AND temperature > 25.0;

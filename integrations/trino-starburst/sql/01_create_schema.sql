-- Create schema pointing to FSx for ONTAP S3 AP
-- Replace <FSX_S3_AP_ALIAS> with your actual alias
CREATE SCHEMA IF NOT EXISTS fsxn.sensor_data
WITH (location = 's3://<FSX_S3_AP_ALIAS>/sensor-data/');

-- Create table on existing Parquet files
CREATE TABLE IF NOT EXISTS fsxn.sensor_data.readings (
    device_id VARCHAR,
    timestamp TIMESTAMP,
    temperature DOUBLE,
    humidity DOUBLE,
    pressure DOUBLE,
    status VARCHAR
)
WITH (
    external_location = 's3://<FSX_S3_AP_ALIAS>/sensor-data/',
    format = 'PARQUET'
);

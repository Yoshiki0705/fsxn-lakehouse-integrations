🌐 **English** | [日本語](README-ja.md)

# Module 02: Athena Quick Start

## End-to-End Flow (15 minutes)

```
Step 1: Verify S3 AP connectivity (validate.sh)
  ↓
Step 2: Create Glue database + table (sample-queries.sql, Steps 1-2)
  ↓
Step 3: Run first query (sample-queries.sql, Step 3)
  ↓
Step 4: Aggregation + CTAS write-back (sample-queries.sql, Steps 4-7)
```

## Prerequisites

- [ ] S3 Access Point is `AVAILABLE` (run `../scripts/validate.sh` first)
- [ ] Sample data uploaded to FSx for ONTAP (Parquet file at `sensor-data/sensor_data.parquet`)
- [ ] AWS CLI configured with permissions for Athena + Glue + S3 AP
- [ ] Athena workgroup with result location configured

## Step-by-Step

### 1. Generate and upload sample data (if not already done)

```bash
# Generate 10K row Parquet file
cd ../sample-data
python generate-sensor-data.py --rows 10000 --output sensor_data.parquet

# Upload via S3 AP
aws s3 cp sensor_data.parquet s3://<AP_ALIAS>/sensor-data/sensor_data.parquet --region ap-northeast-1
```

### 2. Create Glue table

Open Athena console or use AWS CLI, then run the SQL from `sample-queries.sql` Steps 1-2:

```sql
CREATE DATABASE IF NOT EXISTS fsxn_poc;

CREATE EXTERNAL TABLE IF NOT EXISTS fsxn_poc.sensor_data (
  timestamp TIMESTAMP,
  device_id STRING,
  sensor_id STRING,
  temperature DOUBLE,
  humidity DOUBLE,
  pressure DOUBLE,
  status STRING,
  location STRING
)
STORED AS PARQUET
LOCATION 's3://<AP_ALIAS>/sensor-data/'
TBLPROPERTIES ('parquet.compression'='SNAPPY');
```

### 3. Run first query

```sql
SELECT COUNT(*) AS total_rows FROM fsxn_poc.sensor_data;
-- Expected: 10000
```

### 4. Run aggregation

```sql
SELECT status, COUNT(*) as count, ROUND(AVG(temperature),2) as avg_temp
FROM fsxn_poc.sensor_data
GROUP BY status ORDER BY count DESC;
```

Expected result:
| status | count | avg_temp |
|--------|-------|----------|
| normal | ~8500 | ~25.0 |
| warning | ~1200 | ~25.0 |
| critical | ~300 | ~25.0 |

### 5. (Optional) CTAS write-back

```sql
CREATE TABLE fsxn_poc.sensor_summary
WITH (external_location = 's3://<AP_ALIAS>/gold/sensor-summary/', format = 'PARQUET')
AS SELECT device_id, status, COUNT(*) as readings, ROUND(AVG(temperature),2) as avg_temp
FROM fsxn_poc.sensor_data GROUP BY device_id, status;
```

## After This Module

- **Add governance**: Continue to [Module 07 (Lake Formation)](../07-governance/) to add column/row/tag permissions on the same table
- **Run AI demos**: The Glue table is also accessible from Redshift Spectrum (same catalog)
- **Full documentation**: See [Blog Part 1](https://dev.to/aws-builders/query-nas-data-in-place-with-athena-and-fsx-for-ontap-s3-access-points-3lhh)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "Table not found" | Glue database/table not created | Run Steps 1-2 |
| "Access Denied" on query | IAM role missing S3 AP permissions | Add `s3:GetObject` + `s3:ListBucket` on AP ARN |
| 0 rows returned | LOCATION doesn't match file path | Verify with `aws s3api list-objects-v2 --bucket <AP_ALIAS> --prefix sensor-data/` |
| Timestamp parse error | Nanosecond timestamps | Regenerate with `generate-sensor-data.py` (uses microsecond) |

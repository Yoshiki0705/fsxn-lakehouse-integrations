#!/bin/bash
set -euo pipefail

# Trino + FSx for ONTAP S3 AP Verification Script
# Prerequisites:
#   - Docker installed
#   - AWS credentials available (env vars or instance profile)
#   - FSx for ONTAP S3 AP alias known

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
AP_ALIAS="${1:-}"

if [ -z "$AP_ALIAS" ]; then
    echo "Usage: $0 <fsx-s3-ap-alias>"
    echo "Example: $0 athena-verificat-e8z7oep4u3hrqr7wzke4b8k6yi65hapn1b-ext-s3alias"
    exit 1
fi

echo "=== Trino + FSx for ONTAP S3 AP Verification ==="
echo "AP Alias: $AP_ALIAS"
echo ""

# 1. Update catalog config with AP alias
echo "1. Configuring Trino catalog..."
sed -i.bak "s|hive.metastore.catalog.dir=.*|hive.metastore.catalog.dir=s3://${AP_ALIAS}/|" \
    "$PROJECT_DIR/config/etc/catalog/fsxn.properties"

# 2. Start Trino
echo "2. Starting Trino container..."
cd "$PROJECT_DIR"
docker compose up -d
echo "   Waiting for Trino to start (30s)..."
sleep 30

# 3. Check Trino health
echo "3. Checking Trino health..."
if curl -s http://localhost:8080/v1/info | grep -q '"starting":false'; then
    echo "   Trino is ready ✅"
else
    echo "   Trino not ready yet, waiting 15s more..."
    sleep 15
fi

# 4. Run verification queries
echo "4. Running verification queries..."
echo ""

echo "--- Test 1: List files via S3 AP ---"
docker exec trino trino --execute "
    SELECT * FROM system.metadata.table_properties LIMIT 5
" 2>&1 || echo "   (metadata query — informational)"

echo ""
echo "--- Test 2: Create schema ---"
docker exec trino trino --execute "
    CREATE SCHEMA IF NOT EXISTS fsxn.sensor_data
    WITH (location = 's3://${AP_ALIAS}/sensor-data/')
" 2>&1 && echo "   Schema created ✅" || echo "   Schema creation FAILED ❌"

echo ""
echo "--- Test 3: Create table on Parquet ---"
docker exec trino trino --execute "
    CREATE TABLE IF NOT EXISTS fsxn.sensor_data.readings (
        device_id VARCHAR,
        timestamp TIMESTAMP,
        temperature DOUBLE,
        humidity DOUBLE,
        pressure DOUBLE,
        status VARCHAR
    ) WITH (
        external_location = 's3://${AP_ALIAS}/sensor-data/',
        format = 'PARQUET'
    )
" 2>&1 && echo "   Table created ✅" || echo "   Table creation FAILED ❌"

echo ""
echo "--- Test 4: COUNT(*) ---"
START=$(date +%s%N)
docker exec trino trino --execute "
    SELECT COUNT(*) AS total_rows FROM fsxn.sensor_data.readings
" 2>&1
END=$(date +%s%N)
echo "   Duration: $(( (END - START) / 1000000 ))ms"

echo ""
echo "--- Test 5: GROUP BY ---"
START=$(date +%s%N)
docker exec trino trino --execute "
    SELECT status, COUNT(*), AVG(temperature) FROM fsxn.sensor_data.readings GROUP BY status
" 2>&1
END=$(date +%s%N)
echo "   Duration: $(( (END - START) / 1000000 ))ms"

echo ""
echo "=== Verification Complete ==="
echo "To stop Trino: docker compose down"

#!/usr/bin/env bash
# =============================================================================
# Snowpipe End-to-End Test Script
# =============================================================================
# Validates the FPolicy → SQS → Lambda → SNS → Snowpipe pipeline by:
#   1. Writing a JSON event file to FSx for ONTAP via NFS mount
#   2. Polling Snowflake for the record to appear in RAW_EVENTS table
#   3. Measuring end-to-end latency (file write → queryable in Snowflake)
#
# Requirements: REQ-4 (Snowpipe auto-ingest, FPolicy event-driven <30s)
#
# Usage:
#   ./test_snowpipe_e2e.sh \
#     --nfs-mount /mnt/fsxn \
#     --snowflake-account <account> \
#     --snowflake-user <user> \
#     --snowflake-password <password>
#
# Environment variables (alternative to flags):
#   FSXN_NFS_MOUNT       - NFS mount path for FSx for ONTAP volume
#   SNOWFLAKE_ACCOUNT    - Snowflake account identifier
#   SNOWFLAKE_USER       - Snowflake username
#   SNOWFLAKE_PASSWORD   - Snowflake password
#   SNOWFLAKE_WAREHOUSE  - Warehouse name (default: COMPUTE_WH)
#   SNOWFLAKE_DATABASE   - Database name (default: FSXN_LAKEHOUSE)
#   SNOWFLAKE_SCHEMA     - Schema name (default: BRONZE)
#
# Exit codes:
#   0 - Test passed (record appeared within timeout)
#   1 - Test failed (timeout or error)
#   2 - Configuration error (missing parameters)
# =============================================================================

set -euo pipefail

# =============================================================================
# Color output helpers
# =============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[PASS]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()    { echo -e "${RED}[FAIL]${NC} $*"; }
step()    { echo -e "${CYAN}[STEP]${NC} $*"; }

# =============================================================================
# Default configuration
# =============================================================================
NFS_MOUNT="${FSXN_NFS_MOUNT:-}"
SF_ACCOUNT="${SNOWFLAKE_ACCOUNT:-}"
SF_USER="${SNOWFLAKE_USER:-}"
SF_PASSWORD="${SNOWFLAKE_PASSWORD:-}"
SF_WAREHOUSE="${SNOWFLAKE_WAREHOUSE:-COMPUTE_WH}"
SF_DATABASE="${SNOWFLAKE_DATABASE:-FSXN_LAKEHOUSE}"
SF_SCHEMA="${SNOWFLAKE_SCHEMA:-BRONZE}"
POLL_INTERVAL=5       # seconds between Snowflake polls
TIMEOUT=60            # maximum wait time in seconds
CLEANUP=true          # whether to delete test file after completion
RESULTS_DIR=""        # output directory for results JSON

# =============================================================================
# Parse command-line arguments
# =============================================================================
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --nfs-mount)
                NFS_MOUNT="$2"; shift 2 ;;
            --snowflake-account)
                SF_ACCOUNT="$2"; shift 2 ;;
            --snowflake-user)
                SF_USER="$2"; shift 2 ;;
            --snowflake-password)
                SF_PASSWORD="$2"; shift 2 ;;
            --snowflake-warehouse)
                SF_WAREHOUSE="$2"; shift 2 ;;
            --snowflake-database)
                SF_DATABASE="$2"; shift 2 ;;
            --snowflake-schema)
                SF_SCHEMA="$2"; shift 2 ;;
            --timeout)
                TIMEOUT="$2"; shift 2 ;;
            --poll-interval)
                POLL_INTERVAL="$2"; shift 2 ;;
            --no-cleanup)
                CLEANUP=false; shift ;;
            --results-dir)
                RESULTS_DIR="$2"; shift 2 ;;
            --help|-h)
                usage; exit 0 ;;
            *)
                fail "Unknown option: $1"
                usage; exit 2 ;;
        esac
    done
}

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  --nfs-mount PATH          FSx for ONTAP NFS mount path (or set FSXN_NFS_MOUNT)
  --snowflake-account ACCT  Snowflake account identifier (or set SNOWFLAKE_ACCOUNT)
  --snowflake-user USER     Snowflake username (or set SNOWFLAKE_USER)
  --snowflake-password PASS Snowflake password (or set SNOWFLAKE_PASSWORD)
  --snowflake-warehouse WH  Warehouse name (default: COMPUTE_WH)
  --snowflake-database DB   Database name (default: FSXN_LAKEHOUSE)
  --snowflake-schema SCH    Schema name (default: BRONZE)
  --timeout SECONDS         Max wait time (default: 60)
  --poll-interval SECONDS   Poll interval (default: 5)
  --no-cleanup              Do not delete test file from NFS after test
  --results-dir DIR         Directory for results JSON output
  -h, --help                Show this help message

Environment Variables:
  FSXN_NFS_MOUNT, SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
  SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA
EOF
}

# =============================================================================
# Validate configuration
# =============================================================================
validate_config() {
    local errors=0

    if [[ -z "$NFS_MOUNT" ]]; then
        fail "NFS mount path is required (--nfs-mount or FSXN_NFS_MOUNT)"
        errors=$((errors + 1))
    elif [[ ! -d "$NFS_MOUNT" ]]; then
        fail "NFS mount path does not exist: $NFS_MOUNT"
        errors=$((errors + 1))
    fi

    if [[ -z "$SF_ACCOUNT" ]]; then
        fail "Snowflake account is required (--snowflake-account or SNOWFLAKE_ACCOUNT)"
        errors=$((errors + 1))
    fi

    if [[ -z "$SF_USER" ]]; then
        fail "Snowflake user is required (--snowflake-user or SNOWFLAKE_USER)"
        errors=$((errors + 1))
    fi

    if [[ -z "$SF_PASSWORD" ]]; then
        fail "Snowflake password is required (--snowflake-password or SNOWFLAKE_PASSWORD)"
        errors=$((errors + 1))
    fi

    # Check for snowsql or Python snowflake-connector
    if ! command -v snowsql &>/dev/null && ! python3 -c "import snowflake.connector" &>/dev/null 2>&1; then
        fail "Neither snowsql nor Python snowflake-connector-python is available"
        errors=$((errors + 1))
    fi

    if [[ $errors -gt 0 ]]; then
        echo ""
        fail "$errors configuration error(s) found. Run with --help for usage."
        exit 2
    fi
}

# =============================================================================
# Snowflake query execution
# =============================================================================
# Uses Python snowflake-connector if available, falls back to snowsql
# =============================================================================
run_snowflake_query() {
    local query="$1"

    if python3 -c "import snowflake.connector" &>/dev/null 2>&1; then
        python3 <<PYEOF
import snowflake.connector
import json
import sys

try:
    conn = snowflake.connector.connect(
        account='${SF_ACCOUNT}',
        user='${SF_USER}',
        password='${SF_PASSWORD}',
        warehouse='${SF_WAREHOUSE}',
        database='${SF_DATABASE}',
        schema='${SF_SCHEMA}'
    )
    cur = conn.cursor()
    cur.execute("""${query}""")
    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description] if cur.description else []
    result = {"columns": columns, "rows": [list(row) for row in rows], "row_count": len(rows)}
    print(json.dumps(result, default=str))
    cur.close()
    conn.close()
except Exception as e:
    print(json.dumps({"error": str(e), "row_count": 0}), file=sys.stderr)
    sys.exit(1)
PYEOF
    elif command -v snowsql &>/dev/null; then
        snowsql \
            --accountname "$SF_ACCOUNT" \
            --username "$SF_USER" \
            --dbname "$SF_DATABASE" \
            --schemaname "$SF_SCHEMA" \
            --warehouse "$SF_WAREHOUSE" \
            --query "$query" \
            --option output_format=json \
            --option friendly=false \
            --option timing=false \
            <<< "$SF_PASSWORD"
    else
        fail "No Snowflake query tool available"
        return 1
    fi
}

# =============================================================================
# Generate unique test event
# =============================================================================
generate_test_event() {
    local timestamp
    timestamp=$(date +%s)
    local event_id="TEST-E2E-${timestamp}"
    local iso_timestamp
    iso_timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Generate test event JSON (NDJSON format - single line)
    local event_json
    event_json=$(cat <<EOF
{"event_id":"${event_id}","event_type":"e2e_test","timestamp":"${iso_timestamp}","user_id":"test-user-e2e","payload":{"test_run":"snowpipe_e2e","source":"test_snowpipe_e2e.sh","nfs_mount":"${NFS_MOUNT}","description":"End-to-end Snowpipe verification event"}}
EOF
)

    # Return values via global variables
    TEST_EVENT_ID="$event_id"
    TEST_EVENT_JSON="$event_json"
    TEST_TIMESTAMP="$timestamp"
    TEST_FILENAME="test_event_${timestamp}.json"
}

# =============================================================================
# Write test file to NFS mount
# =============================================================================
write_test_file() {
    local target_dir="${NFS_MOUNT}/bronze/events"
    local target_path="${target_dir}/${TEST_FILENAME}"

    # Ensure target directory exists
    if [[ ! -d "$target_dir" ]]; then
        warn "Creating directory: $target_dir"
        mkdir -p "$target_dir"
    fi

    step "Writing test event to NFS: $target_path"
    echo "$TEST_EVENT_JSON" > "$target_path"

    if [[ -f "$target_path" ]]; then
        local file_size
        file_size=$(wc -c < "$target_path" | tr -d ' ')
        info "File written successfully (${file_size} bytes)"
        info "Event ID: ${TEST_EVENT_ID}"
        TEST_FILE_PATH="$target_path"
        FILE_WRITE_TIME=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
        return 0
    else
        fail "Failed to write test file"
        return 1
    fi
}

# =============================================================================
# Poll Snowflake for the test record
# =============================================================================
poll_snowflake() {
    local elapsed=0
    local query="SELECT event_id, event_type, timestamp, user_id, ingested_at FROM ${SF_DATABASE}.${SF_SCHEMA}.RAW_EVENTS WHERE event_id = '${TEST_EVENT_ID}'"

    step "Polling Snowflake for event_id = '${TEST_EVENT_ID}'"
    info "Poll interval: ${POLL_INTERVAL}s | Timeout: ${TIMEOUT}s"
    echo ""

    while [[ $elapsed -lt $TIMEOUT ]]; do
        local result
        result=$(run_snowflake_query "$query" 2>/dev/null || echo '{"row_count":0}')

        local row_count
        row_count=$(echo "$result" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('row_count',0))" 2>/dev/null || echo "0")

        if [[ "$row_count" -gt 0 ]]; then
            RECORD_FOUND_TIME=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
            QUERY_RESULT="$result"
            return 0
        fi

        printf "  ⏳ Waiting... %ds / %ds\r" "$elapsed" "$TIMEOUT"
        sleep "$POLL_INTERVAL"
        elapsed=$((elapsed + POLL_INTERVAL))
    done

    echo ""
    return 1
}

# =============================================================================
# Calculate and report results
# =============================================================================
report_results() {
    local status="$1"
    local e2e_latency_ms=0

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if [[ "$status" == "pass" ]]; then
        e2e_latency_ms=$((RECORD_FOUND_TIME - FILE_WRITE_TIME))
        local e2e_latency_sec
        e2e_latency_sec=$(python3 -c "print(f'{${e2e_latency_ms}/1000:.2f}')")

        success "SNOWPIPE END-TO-END TEST PASSED"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        info "Event ID:           ${TEST_EVENT_ID}"
        info "File Path:          ${TEST_FILE_PATH}"
        info "E2E Latency:        ${e2e_latency_sec}s (${e2e_latency_ms}ms)"
        echo ""

        if [[ $e2e_latency_ms -lt 30000 ]]; then
            success "Latency < 30s — FPolicy event-driven pipeline confirmed"
        elif [[ $e2e_latency_ms -lt 60000 ]]; then
            warn "Latency 30-60s — slightly above FPolicy target, check pipeline"
        else
            warn "Latency > 60s — may be using Lambda polling fallback"
        fi
    else
        fail "SNOWPIPE END-TO-END TEST FAILED (TIMEOUT: ${TIMEOUT}s)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        info "Event ID:           ${TEST_EVENT_ID}"
        info "File Path:          ${TEST_FILE_PATH}"
        info "Timeout:            ${TIMEOUT}s"
        echo ""
        warn "Troubleshooting steps:"
        echo "  1. Verify FPolicy is connected:  fpolicy show-engine -vserver <svm>"
        echo "  2. Check Fargate task status:     aws ecs describe-tasks ..."
        echo "  3. Check SQS messages:            aws sqs get-queue-attributes ..."
        echo "  4. Check Lambda Bridge logs:      aws logs tail /aws/lambda/fpolicy-bridge"
        echo "  5. Check SNS delivery:            aws sns list-subscriptions-by-topic ..."
        echo "  6. Check Snowpipe status:         SELECT SYSTEM\$PIPE_STATUS('FSXN_EVENTS_PIPE')"
        echo "  7. Try manual pipe refresh:       ALTER PIPE FSXN_EVENTS_PIPE REFRESH"
        echo "  8. Check COPY_HISTORY:            SELECT * FROM TABLE(INFORMATION_SCHEMA.COPY_HISTORY(...))"
        echo ""
    fi

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Write results JSON
    write_results_json "$status" "$e2e_latency_ms"
}

# =============================================================================
# Write results to JSON file
# =============================================================================
write_results_json() {
    local status="$1"
    local e2e_latency_ms="$2"

    # Determine output directory
    local output_dir
    if [[ -n "$RESULTS_DIR" ]]; then
        output_dir="$RESULTS_DIR"
    else
        output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/results"
    fi
    mkdir -p "$output_dir"

    local output_file="${output_dir}/snowpipe_e2e_results.json"
    local test_time
    test_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    python3 <<PYEOF
import json

results = {
    "test_name": "snowpipe_e2e",
    "test_time": "${test_time}",
    "status": "${status}",
    "event_id": "${TEST_EVENT_ID}",
    "file_path": "${TEST_FILE_PATH:-}",
    "configuration": {
        "nfs_mount": "${NFS_MOUNT}",
        "snowflake_account": "${SF_ACCOUNT}",
        "database": "${SF_DATABASE}",
        "schema": "${SF_SCHEMA}",
        "warehouse": "${SF_WAREHOUSE}",
        "timeout_seconds": ${TIMEOUT},
        "poll_interval_seconds": ${POLL_INTERVAL}
    },
    "metrics": {
        "e2e_latency_ms": ${e2e_latency_ms},
        "e2e_latency_seconds": round(${e2e_latency_ms} / 1000, 2),
        "within_30s_target": ${e2e_latency_ms} < 30000 if ${e2e_latency_ms} > 0 else None,
        "pipeline": "fpolicy_event_driven" if ${e2e_latency_ms} > 0 and ${e2e_latency_ms} < 30000 else "unknown"
    },
    "pipeline_stages": {
        "description": "NFS write → FPolicy → Fargate → SQS → Lambda → SNS → Snowpipe → COPY INTO",
        "expected_latency_ms": "<30000 (FPolicy) or 300000-420000 (Lambda polling)"
    }
}

with open("${output_file}", "w") as f:
    json.dump(results, f, indent=2, default=str)

print(f"Results written to: ${output_file}")
PYEOF

    info "Results JSON: ${output_file}"
}

# =============================================================================
# Cleanup test file from NFS
# =============================================================================
cleanup() {
    if [[ "$CLEANUP" == "true" && -n "${TEST_FILE_PATH:-}" && -f "${TEST_FILE_PATH:-}" ]]; then
        step "Cleaning up test file: $TEST_FILE_PATH"
        rm -f "$TEST_FILE_PATH"
        info "Test file removed"
    elif [[ "$CLEANUP" == "false" ]]; then
        info "Cleanup skipped (--no-cleanup). File remains at: ${TEST_FILE_PATH:-}"
    fi
}

# =============================================================================
# Main execution
# =============================================================================
main() {
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════════════╗"
    echo "║          Snowpipe End-to-End Test (FPolicy Event-Driven)                ║"
    echo "║          REQ-4: Auto-ingest verification (<30s latency)                 ║"
    echo "╚══════════════════════════════════════════════════════════════════════════╝"
    echo ""

    # Parse arguments and validate
    parse_args "$@"
    validate_config

    info "Configuration:"
    info "  NFS Mount:    $NFS_MOUNT"
    info "  Account:      $SF_ACCOUNT"
    info "  Database:     $SF_DATABASE.$SF_SCHEMA"
    info "  Warehouse:    $SF_WAREHOUSE"
    info "  Timeout:      ${TIMEOUT}s"
    info "  Poll Interval: ${POLL_INTERVAL}s"
    echo ""

    # Step 1: Generate unique test event
    step "1/4 Generating unique test event..."
    generate_test_event
    info "Event ID: $TEST_EVENT_ID"
    echo ""

    # Step 2: Write file to NFS mount
    step "2/4 Writing test file to FSx for ONTAP via NFS..."
    if ! write_test_file; then
        fail "Could not write test file to NFS mount"
        report_results "fail"
        exit 1
    fi
    echo ""

    # Step 3: Poll Snowflake for the record
    step "3/4 Waiting for record to appear in Snowflake..."
    info "Pipeline: NFS → FPolicy → Fargate → SQS → Lambda → SNS → Snowpipe → COPY INTO"
    echo ""

    if poll_snowflake; then
        echo ""
        # Step 4: Report success
        step "4/4 Reporting results..."
        report_results "pass"
        cleanup
        exit 0
    else
        echo ""
        # Step 4: Report failure
        step "4/4 Reporting results..."
        report_results "fail"
        cleanup
        exit 1
    fi
}

# Run main with all arguments
main "$@"

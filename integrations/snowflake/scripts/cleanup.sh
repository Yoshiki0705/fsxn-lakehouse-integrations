#!/bin/bash
# =============================================================================
# Snowflake Integration - Resource Cleanup Script
# =============================================================================
# Cleans up test resources created during the Snowflake integration verification.
# Supports two modes:
#   - soft:  Pauses/disables resources (reversible)
#   - hard:  Deletes/drops resources (irreversible)
#
# Usage:
#   ./scripts/cleanup.sh --mode <soft|hard> [OPTIONS]
#
# Required:
#   --mode <soft|hard>        Cleanup mode (soft=pause, hard=delete)
#
# Optional:
#   --stack-name <name>       CloudFormation stack name (default: from params.json)
#   --region <region>         AWS region (default: from params.json or ap-northeast-1)
#   --nfs-mount <path>        NFS mount path for FSxN (default: /mnt/fsxn)
#   --snowflake-account <id>  Snowflake account identifier (for snowsql)
#   --profile <profile>       AWS CLI profile
#   --dry-run                 Show what would be done without executing
#   --skip-snowflake          Skip Snowflake cleanup
#   --skip-aws                Skip AWS cleanup
#   --skip-fsxn               Skip FSxN file cleanup
#   --help                    Show this help message
#
# Examples:
#   # Preview what would be cleaned (dry-run)
#   ./scripts/cleanup.sh --mode hard --dry-run
#
#   # Soft cleanup — pause pipes, disable rules (reversible)
#   ./scripts/cleanup.sh --mode soft
#
#   # Hard cleanup — drop all test resources
#   ./scripts/cleanup.sh --mode hard --nfs-mount /mnt/fsxn
#
# Requirements: REQ-1 through REQ-7
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INTEGRATION_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PARAMS_FILE="${INTEGRATION_DIR}/params.json"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING:${NC} $1"; }
error(){ echo -e "${RED}[$(date +'%H:%M:%S')] ERROR:${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"; }
dry()  { echo -e "${CYAN}[DRY-RUN]${NC} $1"; }

# Counters for summary
CLEANED_SNOWFLAKE=0
CLEANED_AWS=0
CLEANED_FSXN=0
SKIPPED=0
ERRORS=0

# Safe increment (avoids bash arithmetic exit code issue when value is 0)
inc() { eval "$1=\$(( $1 + 1 ))"; }

# =============================================================================
# CLI Argument Parsing
# =============================================================================
MODE=""
STACK_NAME=""
REGION=""
NFS_MOUNT="/mnt/fsxn"
SNOWFLAKE_ACCOUNT=""
PROFILE=""
DRY_RUN=false
SKIP_SNOWFLAKE=false
SKIP_AWS=false
SKIP_FSXN=false

show_help() {
    cat << 'EOF'
Usage:
  ./scripts/cleanup.sh --mode <soft|hard> [OPTIONS]

Required:
  --mode <soft|hard>        Cleanup mode
                            soft  = Pause Snowpipe, disable EventBridge rules (reversible)
                            hard  = Drop pipes/tables/shares, delete stacks, remove files

Optional:
  --stack-name <name>       CloudFormation stack name (default: from params.json)
  --region <region>         AWS region (default: from params.json or ap-northeast-1)
  --nfs-mount <path>        NFS mount path for FSxN (default: /mnt/fsxn)
  --snowflake-account <id>  Snowflake account identifier (for snowsql connection)
  --profile <profile>       AWS CLI profile
  --dry-run                 Show what would be done without executing
  --skip-snowflake          Skip Snowflake resource cleanup
  --skip-aws                Skip AWS resource cleanup
  --skip-fsxn               Skip FSxN file cleanup
  --help                    Show this help message

Modes:
  soft (reversible):
    - Snowflake: Pause Snowpipe (PIPE_EXECUTION_PAUSED = TRUE)
    - AWS: Disable EventBridge rules
    - FSxN: No action (files preserved)

  hard (irreversible):
    - Snowflake: Drop pipes, external tables, Iceberg tables, shares
    - AWS: Delete CloudFormation stacks (fpolicy-server, fpolicy-ingestion, fpolicy-routing)
    - FSxN: Remove temp/test files (_validation_test/, test_event_*.json)

Examples:
  # Preview cleanup actions
  ./scripts/cleanup.sh --mode hard --dry-run

  # Soft cleanup (pause only)
  ./scripts/cleanup.sh --mode soft

  # Full hard cleanup with custom NFS mount
  ./scripts/cleanup.sh --mode hard --nfs-mount /mnt/fsxn --region ap-northeast-1
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --stack-name)
            STACK_NAME="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --nfs-mount)
            NFS_MOUNT="$2"
            shift 2
            ;;
        --snowflake-account)
            SNOWFLAKE_ACCOUNT="$2"
            shift 2
            ;;
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-snowflake)
            SKIP_SNOWFLAKE=true
            shift
            ;;
        --skip-aws)
            SKIP_AWS=true
            shift
            ;;
        --skip-fsxn)
            SKIP_FSXN=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        *)
            error "Unknown option: $1. Use --help for usage."
            ;;
    esac
done

# =============================================================================
# Input Validation
# =============================================================================
if [[ -z "${MODE}" ]]; then
    error "Missing required argument: --mode <soft|hard>\n  Use --help for usage."
fi

if [[ "${MODE}" != "soft" && "${MODE}" != "hard" ]]; then
    error "Invalid mode: '${MODE}'. Must be 'soft' or 'hard'."
fi

# =============================================================================
# Load Defaults from params.json
# =============================================================================
if [[ -f "${PARAMS_FILE}" ]]; then
    if [[ -z "${STACK_NAME}" ]]; then
        STACK_NAME=$(jq -r '.StackName // ""' "${PARAMS_FILE}")
    fi
    if [[ -z "${REGION}" ]]; then
        REGION=$(jq -r '.Region // ""' "${PARAMS_FILE}")
    fi
fi

STACK_NAME="${STACK_NAME:-fsxn-snowflake}"
REGION="${REGION:-${AWS_DEFAULT_REGION:-ap-northeast-1}}"

# Build AWS CLI options
AWS_OPTS="--region ${REGION}"
if [[ -n "${PROFILE}" ]]; then
    AWS_OPTS="${AWS_OPTS} --profile ${PROFILE}"
fi

# Helper: Run AWS CLI with common options
aws_cmd() {
    aws ${AWS_OPTS} "$@"
}

# Helper: Execute or dry-run a command
run_cmd() {
    local description="$1"
    shift
    if [[ "${DRY_RUN}" == true ]]; then
        dry "Would execute: $*"
        dry "  → ${description}"
    else
        log "  ${description}"
        if "$@" 2>/dev/null; then
            return 0
        else
            return 1
        fi
    fi
}

# =============================================================================
# Banner
# =============================================================================
echo ""
log "═══════════════════════════════════════════════════════════════"
log " FSxN × Snowflake Integration — Resource Cleanup"
log "═══════════════════════════════════════════════════════════════"
echo ""
info "  Mode:        ${MODE}"
info "  Stack Name:  ${STACK_NAME}"
info "  Region:      ${REGION}"
info "  NFS Mount:   ${NFS_MOUNT}"
info "  Dry Run:     ${DRY_RUN}"
echo ""

if [[ "${MODE}" == "hard" && "${DRY_RUN}" != true ]]; then
    warn "═══════════════════════════════════════════════════════════════"
    warn " HARD MODE: This will permanently delete resources!"
    warn " Press Ctrl+C within 5 seconds to abort..."
    warn "═══════════════════════════════════════════════════════════════"
    sleep 5
    echo ""
fi

# =============================================================================
# Phase 1: Snowflake Cleanup
# =============================================================================
cleanup_snowflake() {
    echo ""
    log "───────────────────────────────────────────────────────────────"
    log "Phase 1: Snowflake Resource Cleanup"
    log "───────────────────────────────────────────────────────────────"

    # Build snowsql connection options
    local SNOWSQL_OPTS=""
    if [[ -n "${SNOWFLAKE_ACCOUNT}" ]]; then
        SNOWSQL_OPTS="--accountname ${SNOWFLAKE_ACCOUNT}"
    fi

    # Check if snowsql is available
    if ! command -v snowsql >/dev/null 2>&1; then
        warn "snowsql not found. Generating SQL commands for manual execution."
        _generate_snowflake_sql
        return
    fi

    if [[ "${MODE}" == "soft" ]]; then
        _snowflake_soft_cleanup "${SNOWSQL_OPTS}"
    else
        _snowflake_hard_cleanup "${SNOWSQL_OPTS}"
    fi
}

_generate_snowflake_sql() {
    local SQL_FILE="${INTEGRATION_DIR}/scripts/_cleanup_generated.sql"

    info "  Generating cleanup SQL to: ${SQL_FILE}"

    if [[ "${MODE}" == "soft" ]]; then
        local SQL_CONTENT="-- Snowflake Soft Cleanup (Pause Resources)
-- Generated: $(date -u +'%Y-%m-%dT%H:%M:%SZ')
-- Mode: soft (reversible)

USE DATABASE FSXN_LAKEHOUSE;

-- Pause Snowpipe
ALTER PIPE BRONZE.FSXN_EVENTS_PIPE SET PIPE_EXECUTION_PAUSED = TRUE;

-- Verify pipe is paused
SHOW PIPES;

SELECT 'Soft cleanup complete — pipes paused' AS status;
"
    else
        local SQL_CONTENT="-- Snowflake Hard Cleanup (Drop Resources)
-- Generated: $(date -u +'%Y-%m-%dT%H:%M:%SZ')
-- Mode: hard (irreversible)
-- WARNING: This will permanently delete all test resources!

USE DATABASE FSXN_LAKEHOUSE;

-- 1. Drop Snowpipe (REQ-4)
DROP PIPE IF EXISTS BRONZE.FSXN_EVENTS_PIPE;

-- 2. Drop External Tables (REQ-2)
DROP TABLE IF EXISTS BRONZE.TRANSACTIONS;
DROP TABLE IF EXISTS BRONZE.IOT_SENSORS;
DROP TABLE IF EXISTS BRONZE.CUSTOMERS_CSV;
DROP TABLE IF EXISTS BRONZE.EVENTS_JSON;

-- 3. Drop Iceberg Tables (REQ-3)
DROP ICEBERG TABLE IF EXISTS SILVER.PRODUCTS_ICEBERG;

-- 4. Drop Shares (REQ-5)
DROP SHARE IF EXISTS FSXN_LAKEHOUSE_SHARE;

-- 5. Drop Secure Views (REQ-5)
DROP VIEW IF EXISTS GOLD.DAILY_REVENUE_SHARED;

-- 6. Drop Media Views and Tables (REQ-6, REQ-7)
DROP VIEW IF EXISTS MEDIA.MEDIA_CATALOG;
DROP TABLE IF EXISTS MEDIA.ENRICHED_MEDIA_CATALOG;

-- 7. Drop Stages (REQ-1)
DROP STAGE IF EXISTS BRONZE.FSXN_BRONZE_STAGE;
DROP STAGE IF EXISTS SILVER.FSXN_SILVER_STAGE;
DROP STAGE IF EXISTS GOLD.FSXN_GOLD_STAGE;
DROP STAGE IF EXISTS MEDIA.FSXN_MEDIA_STAGE;

-- 8. Drop File Formats (REQ-2)
DROP FILE FORMAT IF EXISTS BRONZE.PARQUET_FORMAT;
DROP FILE FORMAT IF EXISTS BRONZE.CSV_FORMAT;
DROP FILE FORMAT IF EXISTS BRONZE.JSON_FORMAT;

-- 9. Drop Schemas
DROP SCHEMA IF EXISTS BRONZE;
DROP SCHEMA IF EXISTS SILVER;
DROP SCHEMA IF EXISTS GOLD;
DROP SCHEMA IF EXISTS MEDIA;

-- 10. Drop Database
DROP DATABASE IF EXISTS FSXN_LAKEHOUSE;

-- 11. Drop Storage Integration (REQ-1)
DROP STORAGE INTEGRATION IF EXISTS FSXN_STORAGE_INTEGRATION;

SELECT 'Hard cleanup complete — all resources dropped' AS status;
"
    fi

    if [[ "${DRY_RUN}" == true ]]; then
        dry "Would generate SQL file: ${SQL_FILE}"
        echo ""
        echo "${SQL_CONTENT}"
    else
        echo "${SQL_CONTENT}" > "${SQL_FILE}"
        log "  SQL file generated: ${SQL_FILE}"
        info "  Execute manually: snowsql -f ${SQL_FILE}"
        inc CLEANED_SNOWFLAKE
    fi
}

_snowflake_soft_cleanup() {
    local SNOWSQL_OPTS="$1"
    local SQL="
USE DATABASE FSXN_LAKEHOUSE;
ALTER PIPE BRONZE.FSXN_EVENTS_PIPE SET PIPE_EXECUTION_PAUSED = TRUE;
"
    if [[ "${DRY_RUN}" == true ]]; then
        dry "Would pause Snowpipe: ALTER PIPE SET PIPE_EXECUTION_PAUSED = TRUE"
    else
        log "  Pausing Snowpipe..."
        echo "${SQL}" | snowsql ${SNOWSQL_OPTS} -o exit_on_error=true 2>/dev/null && {
            log "  ✓ Snowpipe paused"
            inc CLEANED_SNOWFLAKE
        } || {
            warn "  Failed to pause Snowpipe (may not exist or already paused)"
            inc SKIPPED
        }
    fi
}

_snowflake_hard_cleanup() {
    local SNOWSQL_OPTS="$1"
    local SQL="
USE DATABASE FSXN_LAKEHOUSE;

-- Drop Snowpipe (REQ-4)
DROP PIPE IF EXISTS BRONZE.FSXN_EVENTS_PIPE;

-- Drop External Tables (REQ-2)
DROP TABLE IF EXISTS BRONZE.TRANSACTIONS;
DROP TABLE IF EXISTS BRONZE.IOT_SENSORS;
DROP TABLE IF EXISTS BRONZE.CUSTOMERS_CSV;
DROP TABLE IF EXISTS BRONZE.EVENTS_JSON;

-- Drop Iceberg Tables (REQ-3)
DROP ICEBERG TABLE IF EXISTS SILVER.PRODUCTS_ICEBERG;

-- Drop Shares (REQ-5)
DROP SHARE IF EXISTS FSXN_LAKEHOUSE_SHARE;

-- Drop Secure Views (REQ-5)
DROP VIEW IF EXISTS GOLD.DAILY_REVENUE_SHARED;

-- Drop Media Views and Tables (REQ-6, REQ-7)
DROP VIEW IF EXISTS MEDIA.MEDIA_CATALOG;
DROP TABLE IF EXISTS MEDIA.ENRICHED_MEDIA_CATALOG;

-- Drop Stages (REQ-1)
DROP STAGE IF EXISTS BRONZE.FSXN_BRONZE_STAGE;
DROP STAGE IF EXISTS SILVER.FSXN_SILVER_STAGE;
DROP STAGE IF EXISTS GOLD.FSXN_GOLD_STAGE;
DROP STAGE IF EXISTS MEDIA.FSXN_MEDIA_STAGE;

-- Drop File Formats (REQ-2)
DROP FILE FORMAT IF EXISTS BRONZE.PARQUET_FORMAT;
DROP FILE FORMAT IF EXISTS BRONZE.CSV_FORMAT;
DROP FILE FORMAT IF EXISTS BRONZE.JSON_FORMAT;

-- Drop Schemas
DROP SCHEMA IF EXISTS BRONZE;
DROP SCHEMA IF EXISTS SILVER;
DROP SCHEMA IF EXISTS GOLD;
DROP SCHEMA IF EXISTS MEDIA;

-- Drop Database
DROP DATABASE IF EXISTS FSXN_LAKEHOUSE;

-- Drop Storage Integration (REQ-1)
DROP STORAGE INTEGRATION IF EXISTS FSXN_STORAGE_INTEGRATION;
"
    if [[ "${DRY_RUN}" == true ]]; then
        dry "Would drop: Snowpipe FSXN_EVENTS_PIPE"
        dry "Would drop: External Tables (TRANSACTIONS, IOT_SENSORS, CUSTOMERS_CSV, EVENTS_JSON)"
        dry "Would drop: Iceberg Table PRODUCTS_ICEBERG"
        dry "Would drop: Share FSXN_LAKEHOUSE_SHARE"
        dry "Would drop: Secure View DAILY_REVENUE_SHARED"
        dry "Would drop: Media Views/Tables (MEDIA_CATALOG, ENRICHED_MEDIA_CATALOG)"
        dry "Would drop: All Stages (BRONZE, SILVER, GOLD, MEDIA)"
        dry "Would drop: File Formats (PARQUET, CSV, JSON)"
        dry "Would drop: Schemas (BRONZE, SILVER, GOLD, MEDIA)"
        dry "Would drop: Database FSXN_LAKEHOUSE"
        dry "Would drop: Storage Integration FSXN_STORAGE_INTEGRATION"
    else
        log "  Dropping all Snowflake resources..."
        echo "${SQL}" | snowsql ${SNOWSQL_OPTS} -o exit_on_error=false 2>/dev/null && {
            log "  ✓ All Snowflake resources dropped"
            CLEANED_SNOWFLAKE=$((CLEANED_SNOWFLAKE + 12))
        } || {
            warn "  Some Snowflake resources may have failed to drop"
            # Still generate SQL for manual cleanup
            _generate_snowflake_sql
            inc ERRORS
        }
    fi
}

# =============================================================================
# Phase 2: AWS Cleanup
# =============================================================================
cleanup_aws() {
    echo ""
    log "───────────────────────────────────────────────────────────────"
    log "Phase 2: AWS Resource Cleanup"
    log "───────────────────────────────────────────────────────────────"

    # Check AWS CLI availability
    if ! command -v aws >/dev/null 2>&1; then
        warn "AWS CLI not found. Skipping AWS cleanup."
        return
    fi

    if [[ "${MODE}" == "soft" ]]; then
        _aws_soft_cleanup
    else
        _aws_hard_cleanup
    fi
}

_aws_soft_cleanup() {
    log "  Disabling EventBridge rules..."

    # Find and disable EventBridge rules related to this integration
    local RULES
    RULES=$(aws_cmd events list-rules \
        --name-prefix "fsxn" \
        --query 'Rules[].Name' \
        --output text 2>/dev/null || echo "")

    if [[ -z "${RULES}" ]]; then
        # Try alternate prefix
        RULES=$(aws_cmd events list-rules \
            --name-prefix "fpolicy" \
            --query 'Rules[].Name' \
            --output text 2>/dev/null || echo "")
    fi

    if [[ -z "${RULES}" ]]; then
        info "  No EventBridge rules found to disable."
        inc SKIPPED
        return
    fi

    for RULE in ${RULES}; do
        if [[ "${DRY_RUN}" == true ]]; then
            dry "Would disable EventBridge rule: ${RULE}"
        else
            aws_cmd events disable-rule --name "${RULE}" 2>/dev/null && {
                log "  ✓ Disabled rule: ${RULE}"
                inc CLEANED_AWS
            } || {
                warn "  Failed to disable rule: ${RULE}"
                inc ERRORS
            }
        fi
    done
}

_aws_hard_cleanup() {
    # 1. Disable and delete EventBridge rules
    log "  Cleaning up EventBridge rules..."
    local RULES
    RULES=$(aws_cmd events list-rules \
        --name-prefix "fsxn" \
        --query 'Rules[].Name' \
        --output text 2>/dev/null || echo "")

    # Also check fpolicy-prefixed rules
    local FPOLICY_RULES
    FPOLICY_RULES=$(aws_cmd events list-rules \
        --name-prefix "fpolicy" \
        --query 'Rules[].Name' \
        --output text 2>/dev/null || echo "")

    RULES="${RULES} ${FPOLICY_RULES}"
    RULES=$(echo "${RULES}" | xargs)  # trim whitespace

    if [[ -n "${RULES}" ]]; then
        for RULE in ${RULES}; do
            if [[ "${DRY_RUN}" == true ]]; then
                dry "Would delete EventBridge rule: ${RULE}"
            else
                # Remove targets first
                local TARGETS
                TARGETS=$(aws_cmd events list-targets-by-rule \
                    --rule "${RULE}" \
                    --query 'Targets[].Id' \
                    --output text 2>/dev/null || echo "")

                if [[ -n "${TARGETS}" ]]; then
                    local TARGET_IDS
                    TARGET_IDS=$(echo "${TARGETS}" | tr '\t' ' ')
                    aws_cmd events remove-targets --rule "${RULE}" --ids ${TARGET_IDS} 2>/dev/null || true
                fi

                aws_cmd events delete-rule --name "${RULE}" 2>/dev/null && {
                    log "  ✓ Deleted rule: ${RULE}"
                    inc CLEANED_AWS
                } || {
                    warn "  Failed to delete rule: ${RULE}"
                    inc ERRORS
                }
            fi
        done
    else
        info "  No EventBridge rules found."
    fi

    # 2. Delete FPolicy-related CloudFormation stacks
    log "  Deleting FPolicy CloudFormation stacks..."
    local FPOLICY_STACKS=("fpolicy-server" "fpolicy-ingestion" "fpolicy-routing")

    for STACK in "${FPOLICY_STACKS[@]}"; do
        local STACK_STATUS
        STACK_STATUS=$(aws_cmd cloudformation describe-stacks \
            --stack-name "${STACK}" \
            --query 'Stacks[0].StackStatus' \
            --output text 2>/dev/null || echo "DOES_NOT_EXIST")

        if [[ "${STACK_STATUS}" == "DOES_NOT_EXIST" ]]; then
            info "  Stack '${STACK}' does not exist — skipping."
            inc SKIPPED
            continue
        fi

        if [[ "${DRY_RUN}" == true ]]; then
            dry "Would delete CloudFormation stack: ${STACK} (status: ${STACK_STATUS})"
        else
            log "  Deleting stack: ${STACK} (status: ${STACK_STATUS})..."
            aws_cmd cloudformation delete-stack --stack-name "${STACK}" 2>/dev/null && {
                log "  ✓ Delete initiated: ${STACK}"
                inc CLEANED_AWS
            } || {
                warn "  Failed to delete stack: ${STACK}"
                inc ERRORS
            }
        fi
    done

    # 3. Wait for stack deletions (non-blocking in dry-run)
    if [[ "${DRY_RUN}" != true ]]; then
        log "  Waiting for stack deletions to complete..."
        for STACK in "${FPOLICY_STACKS[@]}"; do
            aws_cmd cloudformation wait stack-delete-complete \
                --stack-name "${STACK}" 2>/dev/null || true
        done
        log "  ✓ Stack deletions complete (or stacks did not exist)."
    fi
}

# =============================================================================
# Phase 3: FSxN File Cleanup
# =============================================================================
cleanup_fsxn() {
    echo ""
    log "───────────────────────────────────────────────────────────────"
    log "Phase 3: FSxN File Cleanup"
    log "───────────────────────────────────────────────────────────────"

    if [[ "${MODE}" == "soft" ]]; then
        info "  Soft mode — no FSxN files removed."
        info "  Files are preserved for re-use."
        inc SKIPPED
        return
    fi

    # Hard mode: remove temp/test files
    if [[ ! -d "${NFS_MOUNT}" ]]; then
        warn "NFS mount not found: ${NFS_MOUNT}"
        warn "Skipping FSxN file cleanup. Verify --nfs-mount path."
        inc SKIPPED
        return
    fi

    log "  Scanning for test/temp files in: ${NFS_MOUNT}"

    # Define patterns to clean up
    local CLEANUP_PATTERNS=(
        "_validation_test"
        "test_event_*.json"
        "_snowpipe_test"
        ".cleanup_marker"
        "_test_*"
    )

    for PATTERN in "${CLEANUP_PATTERNS[@]}"; do
        local FOUND
        FOUND=$(find "${NFS_MOUNT}" -name "${PATTERN}" -maxdepth 3 2>/dev/null || echo "")

        if [[ -z "${FOUND}" ]]; then
            continue
        fi

        while IFS= read -r FILE; do
            if [[ -z "${FILE}" ]]; then
                continue
            fi

            if [[ "${DRY_RUN}" == true ]]; then
                dry "Would remove: ${FILE}"
            else
                if [[ -d "${FILE}" ]]; then
                    rm -rf "${FILE}" && {
                        log "  ✓ Removed directory: ${FILE}"
                        inc CLEANED_FSXN
                    } || {
                        warn "  Failed to remove: ${FILE}"
                        inc ERRORS
                    }
                else
                    rm -f "${FILE}" && {
                        log "  ✓ Removed file: ${FILE}"
                        inc CLEANED_FSXN
                    } || {
                        warn "  Failed to remove: ${FILE}"
                        inc ERRORS
                    }
                fi
            fi
        done <<< "${FOUND}"
    done

    # Clean up specific test directories if they exist
    local TEST_DIRS=(
        "${NFS_MOUNT}/bronze/_validation_test"
        "${NFS_MOUNT}/silver/_validation_test"
        "${NFS_MOUNT}/gold/_validation_test"
        "${NFS_MOUNT}/media/_validation_test"
    )

    for DIR in "${TEST_DIRS[@]}"; do
        if [[ -d "${DIR}" ]]; then
            if [[ "${DRY_RUN}" == true ]]; then
                dry "Would remove directory: ${DIR}"
            else
                rm -rf "${DIR}" && {
                    log "  ✓ Removed: ${DIR}"
                    inc CLEANED_FSXN
                } || {
                    warn "  Failed to remove: ${DIR}"
                    inc ERRORS
                }
            fi
        fi
    done

    if [[ ${CLEANED_FSXN} -eq 0 && "${DRY_RUN}" != true ]]; then
        info "  No test/temp files found to clean up."
    fi
}

# =============================================================================
# Execute Cleanup Phases
# =============================================================================
if [[ "${SKIP_SNOWFLAKE}" != true ]]; then
    cleanup_snowflake
else
    info "Skipping Snowflake cleanup (--skip-snowflake)"
fi

if [[ "${SKIP_AWS}" != true ]]; then
    cleanup_aws
else
    info "Skipping AWS cleanup (--skip-aws)"
fi

if [[ "${SKIP_FSXN}" != true ]]; then
    cleanup_fsxn
else
    info "Skipping FSxN cleanup (--skip-fsxn)"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
log "═══════════════════════════════════════════════════════════════"
log " Cleanup Summary"
log "═══════════════════════════════════════════════════════════════"
echo ""
info "  Mode:                ${MODE}"
info "  Dry Run:             ${DRY_RUN}"
echo ""
info "  Snowflake cleaned:   ${CLEANED_SNOWFLAKE} resource(s)"
info "  AWS cleaned:         ${CLEANED_AWS} resource(s)"
info "  FSxN cleaned:        ${CLEANED_FSXN} file(s)/dir(s)"
info "  Skipped:             ${SKIPPED}"
info "  Errors:              ${ERRORS}"
echo ""

if [[ ${ERRORS} -gt 0 ]]; then
    warn "Some operations failed. Review warnings above."
fi

if [[ "${DRY_RUN}" == true ]]; then
    echo ""
    info "  This was a dry run. No changes were made."
    info "  Remove --dry-run to execute the cleanup."
fi

echo ""
log "═══════════════════════════════════════════════════════════════"

# Exit with error code if there were failures
if [[ ${ERRORS} -gt 0 ]]; then
    exit 1
fi

exit 0

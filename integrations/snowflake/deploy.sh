#!/bin/bash
# =============================================================================
# Snowflake Integration - Deployment Script
# =============================================================================
# Orchestrates the full deployment of FSxN × S3 AP × Snowflake integration.
#
# Usage:
#   ./deploy.sh [--region <region>] [--env <environment>]
#
# Prerequisites:
#   - AWS CLI v2 configured
#   - SnowSQL CLI configured
#   - FSxN base infrastructure deployed
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
ENVIRONMENT="${1:-dev}"
STACK_NAME="fsxn-snowflake-${ENVIRONMENT}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING:${NC} $1"; }
error() { echo -e "${RED}[$(date +'%H:%M:%S')] ERROR:${NC} $1"; exit 1; }

# =============================================================================
# Pre-flight Checks
# =============================================================================
log "Running pre-flight checks..."
command -v aws >/dev/null 2>&1 || error "AWS CLI not found"

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text 2>/dev/null) || \
    error "AWS credentials not configured"
log "AWS Account: ${AWS_ACCOUNT_ID}, Region: ${REGION}"

# =============================================================================
# Phase 1: Deploy CloudFormation (S3 AP + IAM Role)
# =============================================================================
log "Phase 1: Deploying CloudFormation stack..."

if [ ! -f "${SCRIPT_DIR}/params.json" ]; then
    warn "params.json not found. Copy from params.example.json and fill in values."
    error "Missing params.json"
fi

aws cloudformation deploy \
    --template-file "${SCRIPT_DIR}/template.yaml" \
    --stack-name "${STACK_NAME}" \
    --parameter-overrides file://${SCRIPT_DIR}/params.json \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "${REGION}" \
    --tags \
        Project=fsxn-lakehouse-integrations \
        Integration=snowflake \
        Environment="${ENVIRONMENT}"

# Get outputs
S3_AP_ALIAS=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].Outputs[?OutputKey==`S3AccessPointAlias`].OutputValue' \
    --output text --region "${REGION}")

IAM_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].Outputs[?OutputKey==`SnowflakeRoleArn`].OutputValue' \
    --output text --region "${REGION}")

log "S3 AP Alias: ${S3_AP_ALIAS}"
log "IAM Role ARN: ${IAM_ROLE_ARN}"

# =============================================================================
# Phase 2: Validate S3 AP Connectivity
# =============================================================================
log "Phase 2: Validating S3 AP connectivity..."

python "${PROJECT_ROOT}/shared/scripts/validate-access.py" \
    --access-point-alias "${S3_AP_ALIAS}" \
    --region "${REGION}" || warn "Connectivity test had issues"

# =============================================================================
# Phase 3: Generate Snowflake SQL with actual values
# =============================================================================
log "Phase 3: Generating Snowflake SQL scripts with actual values..."

SQL_OUTPUT_DIR="${SCRIPT_DIR}/sql/generated"
mkdir -p "${SQL_OUTPUT_DIR}"

# Generate storage integration SQL with actual values
cat > "${SQL_OUTPUT_DIR}/01_create_integration.sql" << EOF
-- Auto-generated: $(date)
-- S3 AP Alias: ${S3_AP_ALIAS}
-- IAM Role: ${IAM_ROLE_ARN}

CREATE OR REPLACE STORAGE INTEGRATION fsxn_storage_integration
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'S3'
  ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = '${IAM_ROLE_ARN}'
  STORAGE_ALLOWED_LOCATIONS = (
    's3://${S3_AP_ALIAS}/',
    's3://${S3_AP_ALIAS}/bronze/',
    's3://${S3_AP_ALIAS}/silver/',
    's3://${S3_AP_ALIAS}/gold/',
    's3://${S3_AP_ALIAS}/media/'
  );

-- Run this to get trust policy values:
DESCRIBE INTEGRATION fsxn_storage_integration;

-- Note STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID
-- Then update CloudFormation stack with these values.
EOF

log "Generated SQL: ${SQL_OUTPUT_DIR}/01_create_integration.sql"

# =============================================================================
# Phase 4: Instructions
# =============================================================================
log ""
log "=========================================="
log "Deployment Summary"
log "=========================================="
log "  Stack:        ${STACK_NAME}"
log "  S3 AP Alias:  ${S3_AP_ALIAS}"
log "  IAM Role:     ${IAM_ROLE_ARN}"
log ""
log "Next Steps:"
log "  1. Run in Snowflake: ${SQL_OUTPUT_DIR}/01_create_integration.sql"
log "  2. Run: DESCRIBE INTEGRATION fsxn_storage_integration;"
log "  3. Note STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID"
log "  4. Update CloudFormation: SnowflakeAccountId + SnowflakeExternalId"
log "  5. Run SQL scripts 02-09 in order"
log "  6. (Optional) Deploy Snowpipe Lambda: snowpipe-lambda/template.yaml"
log "=========================================="

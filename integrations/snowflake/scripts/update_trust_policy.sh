#!/bin/bash
# =============================================================================
# Snowflake Integration - Phase 2: Trust Policy Update Script
# =============================================================================
# Updates the CloudFormation stack with actual Snowflake trust information
# obtained from DESCRIBE INTEGRATION output.
#
# This script completes the two-phase setup:
#   Phase 1 (deploy.sh): Deploy with own-account trust placeholder
#   Phase 2 (this script): Update with Snowflake's actual IAM User ARN + External ID
#
# Usage:
#   ./scripts/update_trust_policy.sh [OPTIONS]
#
# Required Options:
#   --snowflake-arn <arn>    STORAGE_AWS_IAM_USER_ARN from DESCRIBE INTEGRATION
#   --external-id <id>      STORAGE_AWS_EXTERNAL_ID from DESCRIBE INTEGRATION
#
# Optional:
#   --stack-name <name>     CloudFormation stack name (default: from params.json)
#   --region <region>       AWS region (default: from params.json or ap-northeast-1)
#   --profile <profile>     AWS CLI profile (default: none / environment default)
#   --help                  Show this help message
#
# Example:
#   ./scripts/update_trust_policy.sh \
#     --snowflake-arn "arn:aws:iam::123456789012:user/abc1-b-self1234" \
#     --external-id "XX12345_SFCRole=2_abcdefghijk="
#
# Prerequisites:
#   - Phase 1 deployment completed (deploy.sh)
#   - DESCRIBE INTEGRATION executed in Snowflake
#   - AWS CLI v2 with permissions to update CloudFormation stacks
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
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[$(date +'%H:%M:%S')] WARNING:${NC} $1"; }
error(){ echo -e "${RED}[$(date +'%H:%M:%S')] ERROR:${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"; }

# =============================================================================
# CLI Argument Parsing
# =============================================================================
SNOWFLAKE_ARN=""
EXTERNAL_ID=""
STACK_NAME=""
REGION=""
PROFILE=""

show_help() {
    cat << 'EOF'
Usage:
  ./scripts/update_trust_policy.sh [OPTIONS]

Required Options:
  --snowflake-arn <arn>    STORAGE_AWS_IAM_USER_ARN from DESCRIBE INTEGRATION
  --external-id <id>      STORAGE_AWS_EXTERNAL_ID from DESCRIBE INTEGRATION

Optional:
  --stack-name <name>     CloudFormation stack name (default: from params.json)
  --region <region>       AWS region (default: from params.json or ap-northeast-1)
  --profile <profile>     AWS CLI profile (default: none / environment default)
  --help                  Show this help message

Example:
  ./scripts/update_trust_policy.sh \
    --snowflake-arn "arn:aws:iam::123456789012:user/abc1-b-self1234" \
    --external-id "XX12345_SFCRole=2_abcdefghijk="

How to get these values:
  1. Run in Snowflake: DESCRIBE INTEGRATION fsxn_storage_integration;
  2. Copy STORAGE_AWS_IAM_USER_ARN  → use as --snowflake-arn
  3. Copy STORAGE_AWS_EXTERNAL_ID   → use as --external-id
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --snowflake-arn)
            SNOWFLAKE_ARN="$2"
            shift 2
            ;;
        --external-id)
            EXTERNAL_ID="$2"
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
        --profile)
            PROFILE="$2"
            shift 2
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
log "Validating inputs..."

# Validate required arguments
if [[ -z "${SNOWFLAKE_ARN}" ]]; then
    error "Missing required argument: --snowflake-arn\n  Use --help for usage."
fi

if [[ -z "${EXTERNAL_ID}" ]]; then
    error "Missing required argument: --external-id\n  Use --help for usage."
fi

# Validate ARN format: arn:aws:iam::<account-id>:user/<username>
ARN_REGEX='^arn:aws:iam::[0-9]{12}:(user|role)/[a-zA-Z0-9_+=,.@\-]+$'
if [[ ! "${SNOWFLAKE_ARN}" =~ ${ARN_REGEX} ]]; then
    error "Invalid ARN format: ${SNOWFLAKE_ARN}\n  Expected: arn:aws:iam::<12-digit-account-id>:user/<username>\n  Example:  arn:aws:iam::123456789012:user/abc1-b-self1234"
fi

# Validate External ID is non-empty and reasonable length
if [[ ${#EXTERNAL_ID} -lt 2 ]]; then
    error "External ID is too short (${#EXTERNAL_ID} chars). Expected a value like: XX12345_SFCRole=2_abcdefghijk="
fi

# Extract AWS Account ID from the Snowflake ARN
SNOWFLAKE_ACCOUNT_ID=$(echo "${SNOWFLAKE_ARN}" | awk -F: '{print $5}')

if [[ -z "${SNOWFLAKE_ACCOUNT_ID}" || ${#SNOWFLAKE_ACCOUNT_ID} -ne 12 ]]; then
    error "Failed to extract 12-digit AWS Account ID from ARN: ${SNOWFLAKE_ARN}"
fi

log "  Snowflake ARN:        ${SNOWFLAKE_ARN}"
log "  Extracted Account ID: ${SNOWFLAKE_ACCOUNT_ID}"
log "  External ID:          ${EXTERNAL_ID}"

# =============================================================================
# Load Defaults from params.json
# =============================================================================
if [[ -f "${PARAMS_FILE}" ]]; then
    log "Loading defaults from params.json..."

    if [[ -z "${STACK_NAME}" ]]; then
        STACK_NAME=$(jq -r '.StackName // ""' "${PARAMS_FILE}")
    fi
    if [[ -z "${REGION}" ]]; then
        REGION=$(jq -r '.Region // ""' "${PARAMS_FILE}")
    fi
else
    warn "params.json not found at ${PARAMS_FILE}"
fi

# Apply final defaults
STACK_NAME="${STACK_NAME:-fsxn-snowflake}"
REGION="${REGION:-${AWS_DEFAULT_REGION:-ap-northeast-1}}"

info "  Stack Name: ${STACK_NAME}"
info "  Region:     ${REGION}"

# =============================================================================
# Pre-flight Checks
# =============================================================================
log "Running pre-flight checks..."

command -v aws >/dev/null 2>&1 || error "AWS CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
command -v jq >/dev/null 2>&1  || error "jq not found. Install: brew install jq (macOS) or apt-get install jq (Linux)"

# Build AWS CLI options
AWS_OPTS="--region ${REGION}"
if [[ -n "${PROFILE}" ]]; then
    AWS_OPTS="${AWS_OPTS} --profile ${PROFILE}"
fi

# Helper: Run AWS CLI with common options
aws_cmd() {
    aws ${AWS_OPTS} "$@"
}

# Verify AWS credentials
AWS_IDENTITY=$(aws_cmd sts get-caller-identity --query 'Arn' --output text 2>/dev/null) || \
    error "AWS credentials not configured or expired. Run: aws configure"
log "  AWS Identity: ${AWS_IDENTITY}"

# Verify stack exists
STACK_STATUS=$(aws_cmd cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null) || \
    error "Stack '${STACK_NAME}' not found in region '${REGION}'. Run deploy.sh first."

log "  Stack Status: ${STACK_STATUS}"

# Ensure stack is in a stable state
case "${STACK_STATUS}" in
    CREATE_COMPLETE|UPDATE_COMPLETE|UPDATE_ROLLBACK_COMPLETE)
        log "  Stack is in a stable state — ready for update."
        ;;
    *_IN_PROGRESS)
        error "Stack is currently in progress (${STACK_STATUS}). Wait for it to complete."
        ;;
    *FAILED*|*ROLLBACK*)
        warn "Stack is in state: ${STACK_STATUS}. Attempting update anyway..."
        ;;
    *)
        warn "Unexpected stack status: ${STACK_STATUS}. Proceeding with caution."
        ;;
esac

# =============================================================================
# Update CloudFormation Stack with Snowflake Trust Info
# =============================================================================
echo ""
log "═══════════════════════════════════════════════════════════════"
log "Phase 2: Updating trust policy with Snowflake account info"
log "═══════════════════════════════════════════════════════════════"
echo ""
info "  SnowflakeAccountId:  ${SNOWFLAKE_ACCOUNT_ID}"
info "  SnowflakeExternalId: ${EXTERNAL_ID}"
echo ""

log "Running aws cloudformation update-stack..."

aws_cmd cloudformation update-stack \
    --stack-name "${STACK_NAME}" \
    --use-previous-template \
    --parameters \
        "ParameterKey=SnowflakeAccountId,ParameterValue=${SNOWFLAKE_ACCOUNT_ID}" \
        "ParameterKey=SnowflakeExternalId,ParameterValue=${EXTERNAL_ID}" \
        "ParameterKey=EnvironmentName,UsePreviousValue=true" \
        "ParameterKey=S3AccessPointArn,UsePreviousValue=true" \
        "ParameterKey=S3AccessPointAlias,UsePreviousValue=true" \
        "ParameterKey=EnableSnowpipe,UsePreviousValue=true" \
        "ParameterKey=SnowflakeSqsArn,UsePreviousValue=true" \
    --capabilities CAPABILITY_NAMED_IAM \
    || error "CloudFormation update-stack failed. Check AWS Console for details."

log "Stack update initiated. Waiting for completion..."

# =============================================================================
# Wait for Stack Update to Complete
# =============================================================================
aws_cmd cloudformation wait stack-update-complete \
    --stack-name "${STACK_NAME}" \
    || error "Stack update failed or timed out. Check CloudFormation events:\n  aws cloudformation describe-stack-events --stack-name ${STACK_NAME} --region ${REGION}"

log "Stack update completed successfully!"

# =============================================================================
# Verify Updated Trust Policy Phase
# =============================================================================
TRUST_POLICY_PHASE=$(aws_cmd cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].Outputs[?OutputKey==`TrustPolicyPhase`].OutputValue' \
    --output text 2>/dev/null || echo "unknown")

log "  Trust Policy Phase: ${TRUST_POLICY_PHASE}"

# =============================================================================
# Update params.json with Snowflake Trust Info
# =============================================================================
if [[ -f "${PARAMS_FILE}" ]]; then
    log "Updating params.json with Snowflake trust info..."

    UPDATED_PARAMS=$(jq \
        --arg account_id "${SNOWFLAKE_ACCOUNT_ID}" \
        --arg external_id "${EXTERNAL_ID}" \
        --arg phase "${TRUST_POLICY_PHASE}" \
        '.SnowflakeAccountId = $account_id |
         .SnowflakeExternalId = $external_id |
         .TrustPolicyPhase = $phase' \
        "${PARAMS_FILE}")

    echo "${UPDATED_PARAMS}" > "${PARAMS_FILE}"
    log "Updated: ${PARAMS_FILE}"
else
    warn "params.json not found — skipping local config update."
fi

# =============================================================================
# Summary & Next Steps
# =============================================================================
echo ""
log "═══════════════════════════════════════════════════════════════"
log " Phase 2 Complete — Trust Policy Updated"
log "═══════════════════════════════════════════════════════════════"
echo ""
info "  Stack:               ${STACK_NAME}"
info "  Region:              ${REGION}"
info "  Snowflake Account:   ${SNOWFLAKE_ACCOUNT_ID}"
info "  External ID:         ${EXTERNAL_ID}"
info "  Trust Policy Phase:  ${TRUST_POLICY_PHASE}"
echo ""
log "═══════════════════════════════════════════════════════════════"
log " Next Steps: Re-validate Storage Integration in Snowflake"
log "═══════════════════════════════════════════════════════════════"
echo ""
info "  1. Run in Snowflake to verify the integration is now valid:"
echo ""
echo "     -- Check integration status"
echo "     DESCRIBE INTEGRATION fsxn_storage_integration;"
echo ""
echo "     -- Test stage access (should list files)"
echo "     LIST @FSXN_LAKEHOUSE.BRONZE.FSXN_BRONZE_STAGE;"
echo ""
info "  2. If LIST returns files, the two-phase setup is complete!"
echo ""
info "  3. If you see access errors, verify:"
info "     - The S3 Access Point policy allows the IAM Role"
info "     - The FSx for ONTAP SVM S3 bucket is accessible"
info "     - The IAM Role trust policy has the correct External ID"
echo ""
info "  4. Continue with External Stages and Tables:"
echo "     snowsql -f sql/02_external_stage.sql"
echo ""
log "═══════════════════════════════════════════════════════════════"

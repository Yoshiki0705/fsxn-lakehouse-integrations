#!/bin/bash
# =============================================================================
# Snowflake Integration - Deployment Script
# =============================================================================
# Deploys CloudFormation stack (IAM Role for Snowflake Storage Integration).
#
# IMPORTANT: FSx for ONTAP S3 Access Points are created SEPARATELY via:
#   aws fsx create-and-attach-s3-access-point --name <name> --type ONTAP \
#     --ontap-configuration VolumeId=<vol-id>,FileSystemIdentity='{...}'
#
# This script deploys ONLY the IAM Role with two-phase trust setup:
#   Phase 1 (this script): Deploy with own-account trust placeholder
#   Phase 2 (after DESCRIBE INTEGRATION): Update with Snowflake trust info
#     → Use scripts/update_trust_policy.sh for Phase 2
#
# Usage:
#   ./deploy.sh [OPTIONS]
#
# Options:
#   --stack-name <name>   CloudFormation stack name (default: fsxn-snowflake)
#   --region <region>     AWS region (default: ap-northeast-1 or AWS_DEFAULT_REGION)
#   --profile <profile>   AWS CLI profile (default: none / environment default)
#   --help                Show this help message
#
# Prerequisites:
#   - AWS CLI v2 configured with appropriate permissions
#   - params.json with S3AccessPointArn filled in (copy from params.example.json)
#   - FSx for ONTAP S3 Access Point already created via aws fsx CLI
# =============================================================================

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/params.json"
PARAMS_EXAMPLE="${SCRIPT_DIR}/params.example.json"
TEMPLATE_FILE="${SCRIPT_DIR}/template.yaml"

# Defaults
STACK_NAME="fsxn-snowflake"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
PROFILE=""

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
show_help() {
    cat << 'EOF'
Usage:
  ./deploy.sh [OPTIONS]

Options:
  --stack-name <name>   CloudFormation stack name (default: fsxn-snowflake)
  --region <region>     AWS region (default: ap-northeast-1 or AWS_DEFAULT_REGION)
  --profile <profile>   AWS CLI profile (default: none / environment default)
  --help                Show this help message

Examples:
  ./deploy.sh
  ./deploy.sh --stack-name my-stack --region us-east-1
  ./deploy.sh --profile my-aws-profile

Prerequisites:
  1. Create FSx for ONTAP S3 Access Point first:
     aws fsx create-and-attach-s3-access-point --name snowflake-test --type ONTAP \
       --ontap-configuration 'VolumeId=fsvol-xxx,FileSystemIdentity={Type=UNIX,UnixUser={Name=root}}'

  2. Copy params.example.json to params.json and set S3AccessPointArn
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
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

# Build AWS CLI options
AWS_OPTS="--region ${REGION}"
if [[ -n "${PROFILE}" ]]; then
    AWS_OPTS="${AWS_OPTS} --profile ${PROFILE}"
fi

# =============================================================================
# Helper: Run AWS CLI with common options
# =============================================================================
aws_cmd() {
    aws ${AWS_OPTS} "$@"
}

# =============================================================================
# Pre-flight Checks
# =============================================================================
log "Running pre-flight checks..."

command -v aws >/dev/null 2>&1 || error "AWS CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
command -v jq >/dev/null 2>&1  || error "jq not found. Install: brew install jq (macOS) or apt-get install jq (Linux)"

# Verify AWS credentials
AWS_ACCOUNT_ID=$(aws_cmd sts get-caller-identity --query 'Account' --output text 2>/dev/null) || \
    error "AWS credentials not configured. Run: aws configure"
AWS_IDENTITY=$(aws_cmd sts get-caller-identity --query 'Arn' --output text 2>/dev/null)

log "AWS Account: ${AWS_ACCOUNT_ID}"
log "Identity:    ${AWS_IDENTITY}"
log "Region:      ${REGION}"
log "Stack Name:  ${STACK_NAME}"

# Verify template exists
[[ -f "${TEMPLATE_FILE}" ]] || error "Template not found: ${TEMPLATE_FILE}"

# =============================================================================
# Load Parameters
# =============================================================================
if [[ ! -f "${PARAMS_FILE}" ]]; then
    warn "params.json not found. Creating from params.example.json..."
    if [[ -f "${PARAMS_EXAMPLE}" ]]; then
        cp "${PARAMS_EXAMPLE}" "${PARAMS_FILE}"
        warn "Created ${PARAMS_FILE} — please edit S3AccessPointArn before re-running."
        warn "  vi ${PARAMS_FILE}"
        error "params.json needs configuration. Set S3AccessPointArn at minimum."
    else
        error "Neither params.json nor params.example.json found."
    fi
fi

# Read parameters from params.json (aligned with new template)
ENVIRONMENT_NAME=$(jq -r '.EnvironmentName // "fsxn-lakehouse"' "${PARAMS_FILE}")
S3_AP_ARN=$(jq -r '.S3AccessPointArn // ""' "${PARAMS_FILE}")
S3_AP_ALIAS=$(jq -r '.S3AccessPointAlias // ""' "${PARAMS_FILE}")
SNOWFLAKE_ACCOUNT_ID=$(jq -r '.SnowflakeAccountId // ""' "${PARAMS_FILE}")
SNOWFLAKE_EXTERNAL_ID=$(jq -r '.SnowflakeExternalId // "snowflake-placeholder"' "${PARAMS_FILE}")
ENABLE_SNOWPIPE=$(jq -r '.EnableSnowpipe // "false"' "${PARAMS_FILE}")
SNOWFLAKE_SQS_ARN=$(jq -r '.SnowflakeSqsArn // ""' "${PARAMS_FILE}")

# Validate required parameters
[[ -n "${S3_AP_ARN}" && "${S3_AP_ARN}" != "<"* ]] || \
    error "S3AccessPointArn not configured in params.json.\n  Set the ARN of your existing FSx for ONTAP S3 Access Point.\n  Example: arn:aws:s3:ap-northeast-1:123456789012:accesspoint/snowflake-test\n\n  Create one first with:\n    aws fsx create-and-attach-s3-access-point --name <name> --type ONTAP \\\\\n      --ontap-configuration VolumeId=<vol-id>,FileSystemIdentity='{Type=UNIX,UnixUser={Name=root}}'"

log "Parameters loaded from params.json"
info "  EnvironmentName:     ${ENVIRONMENT_NAME}"
info "  S3AccessPointArn:    ${S3_AP_ARN}"
info "  S3AccessPointAlias:  ${S3_AP_ALIAS:-'(will be populated from outputs)'}"
info "  EnableSnowpipe:      ${ENABLE_SNOWPIPE}"

if [[ -z "${SNOWFLAKE_ACCOUNT_ID}" ]]; then
    info "  SnowflakeAccountId:  (empty — Phase 1 own-account trust)"
else
    info "  SnowflakeAccountId:  ${SNOWFLAKE_ACCOUNT_ID}"
fi

# =============================================================================
# Deploy CloudFormation Stack
# =============================================================================
echo ""
log "═══════════════════════════════════════════════════════════════"
if [[ -z "${SNOWFLAKE_ACCOUNT_ID}" ]]; then
    log "Phase 1: Deploying IAM Role (own-account trust placeholder)"
else
    log "Phase 2: Updating IAM Role (Snowflake cross-account trust)"
fi
log "═══════════════════════════════════════════════════════════════"

# Check if stack already exists
STACK_STATUS=$(aws_cmd cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>/dev/null || echo "DOES_NOT_EXIST")

if [[ "${STACK_STATUS}" == "DOES_NOT_EXIST" ]]; then
    log "Creating new stack: ${STACK_NAME}"
else
    log "Updating existing stack: ${STACK_NAME} (current status: ${STACK_STATUS})"
fi

# Deploy stack
aws_cmd cloudformation deploy \
    --template-file "${TEMPLATE_FILE}" \
    --stack-name "${STACK_NAME}" \
    --parameter-overrides \
        "EnvironmentName=${ENVIRONMENT_NAME}" \
        "S3AccessPointArn=${S3_AP_ARN}" \
        "S3AccessPointAlias=${S3_AP_ALIAS}" \
        "SnowflakeAccountId=${SNOWFLAKE_ACCOUNT_ID}" \
        "SnowflakeExternalId=${SNOWFLAKE_EXTERNAL_ID}" \
        "EnableSnowpipe=${ENABLE_SNOWPIPE}" \
        "SnowflakeSqsArn=${SNOWFLAKE_SQS_ARN}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --tags \
        "Project=fsxn-lakehouse-integrations" \
        "Integration=snowflake" \
        "Environment=${ENVIRONMENT_NAME}" \
    --no-fail-on-empty-changeset \
    || error "CloudFormation deployment failed. Check AWS Console for details."

log "Stack deployment complete."

# =============================================================================
# Capture Stack Outputs
# =============================================================================
echo ""
log "═══════════════════════════════════════════════════════════════"
log "Capturing stack outputs..."
log "═══════════════════════════════════════════════════════════════"

# Get all outputs in one call
STACK_OUTPUTS=$(aws_cmd cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].Outputs' \
    --output json)

# Extract individual outputs
IAM_ROLE_ARN=$(echo "${STACK_OUTPUTS}" | jq -r '.[] | select(.OutputKey=="IAMRoleArn") | .OutputValue // ""')
STORAGE_ALLOWED_LOCATIONS=$(echo "${STACK_OUTPUTS}" | jq -r '.[] | select(.OutputKey=="StorageAllowedLocations") | .OutputValue // ""')
TRUST_POLICY_PHASE=$(echo "${STACK_OUTPUTS}" | jq -r '.[] | select(.OutputKey=="TrustPolicyPhase") | .OutputValue // ""')
OUTPUT_AP_ALIAS=$(echo "${STACK_OUTPUTS}" | jq -r '.[] | select(.OutputKey=="S3AccessPointAlias") | .OutputValue // ""')

# Validate outputs were captured
[[ -n "${IAM_ROLE_ARN}" ]] || error "Failed to capture IAMRoleArn from stack outputs"

log "  IAMRoleArn:               ${IAM_ROLE_ARN}"
log "  S3AccessPointAlias:       ${OUTPUT_AP_ALIAS}"
log "  StorageAllowedLocations:  ${STORAGE_ALLOWED_LOCATIONS}"
log "  TrustPolicyPhase:         ${TRUST_POLICY_PHASE}"

# =============================================================================
# Write Outputs to params.json
# =============================================================================
log "Writing outputs to params.json..."

UPDATED_PARAMS=$(jq \
    --arg role "${IAM_ROLE_ARN}" \
    --arg locations "${STORAGE_ALLOWED_LOCATIONS}" \
    --arg stack "${STACK_NAME}" \
    --arg region "${REGION}" \
    --arg phase "${TRUST_POLICY_PHASE}" \
    '.IAMRoleArn = $role |
     .StorageAllowedLocations = $locations |
     .StackName = $stack |
     .Region = $region |
     .TrustPolicyPhase = $phase' \
    "${PARAMS_FILE}")

echo "${UPDATED_PARAMS}" > "${PARAMS_FILE}"
log "Updated: ${PARAMS_FILE}"

# =============================================================================
# Deployment Summary & Next Steps
# =============================================================================
echo ""
log "═══════════════════════════════════════════════════════════════"
log " Deployment Summary"
log "═══════════════════════════════════════════════════════════════"
echo ""
info "  Stack Name:              ${STACK_NAME}"
info "  Region:                  ${REGION}"
info "  Trust Policy Phase:      ${TRUST_POLICY_PHASE}"
echo ""
info "  ┌─────────────────────────────────────────────────────────┐"
info "  │ IAM Role                                                │"
info "  │   ARN: ${IAM_ROLE_ARN}"
info "  │                                                         │"
info "  │ S3 Access Point (pre-existing)                          │"
info "  │   ARN:   ${S3_AP_ARN}"
info "  │   Alias: ${OUTPUT_AP_ALIAS}"
info "  │                                                         │"
info "  │ Storage Allowed Locations (for Snowflake):              │"
info "  │   ${STORAGE_ALLOWED_LOCATIONS}"
info "  └─────────────────────────────────────────────────────────┘"

if [[ -z "${SNOWFLAKE_ACCOUNT_ID}" ]]; then
    echo ""
    log "═══════════════════════════════════════════════════════════════"
    log " Next Steps: Create Storage Integration in Snowflake"
    log "═══════════════════════════════════════════════════════════════"
    echo ""
    info "  1. Run in Snowflake (SnowSQL or Worksheet):"
    echo ""
    echo "     CREATE OR REPLACE STORAGE INTEGRATION fsxn_storage_integration"
    echo "       TYPE = EXTERNAL_STAGE"
    echo "       STORAGE_PROVIDER = 'S3'"
    echo "       ENABLED = TRUE"
    echo "       STORAGE_AWS_ROLE_ARN = '${IAM_ROLE_ARN}'"
    echo "       STORAGE_ALLOWED_LOCATIONS = ("
    echo "         '${STORAGE_ALLOWED_LOCATIONS}'"
    echo "       );"
    echo ""
    info "  2. Get Snowflake trust info:"
    echo ""
    echo "     DESCRIBE INTEGRATION fsxn_storage_integration;"
    echo ""
    info "  3. Note these values from the output:"
    info "     - STORAGE_AWS_IAM_USER_ARN  → extract AWS Account ID"
    info "     - STORAGE_AWS_EXTERNAL_ID   → SnowflakeExternalId"
    echo ""
    info "  4. Run the trust policy update script:"
    echo "     ./scripts/update_trust_policy.sh \\"
    echo "       --snowflake-arn <STORAGE_AWS_IAM_USER_ARN> \\"
    echo "       --external-id <STORAGE_AWS_EXTERNAL_ID>"
    echo ""
else
    echo ""
    log "═══════════════════════════════════════════════════════════════"
    log " Phase 2 Complete — Snowflake Trust Configured"
    log "═══════════════════════════════════════════════════════════════"
    echo ""
    info "  Snowflake can now assume the IAM Role with External ID."
    info "  Verify in Snowflake:"
    echo ""
    echo "     DESCRIBE INTEGRATION fsxn_storage_integration;"
    echo "     LIST @<your_stage>;"
    echo ""
fi

log "═══════════════════════════════════════════════════════════════"

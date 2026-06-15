#!/bin/bash
# =============================================================================
# Databricks Integration - Deployment Script
# =============================================================================
# Orchestrates the full deployment of FSxN × S3 AP × Databricks integration.
# Run this script after configuring parameters in params.example.json.
#
# Usage:
#   ./deploy.sh [--region <region>] [--env <environment>]
#
# Prerequisites:
#   - AWS CLI v2 configured
#   - Terraform 1.5+ installed
#   - Databricks CLI configured
#   - FSxN base infrastructure deployed (shared/cloudformation/)
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
ENVIRONMENT="${1:-dev}"
STACK_NAME="fsxn-databricks-${ENVIRONMENT}"

# Colors
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
command -v terraform >/dev/null 2>&1 || error "Terraform not found"

# Verify AWS credentials
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text 2>/dev/null) || \
    error "AWS credentials not configured"
log "AWS Account: ${AWS_ACCOUNT_ID}"
log "Region: ${REGION}"

# =============================================================================
# Phase 1: Deploy CloudFormation (S3 AP + IAM Role)
# =============================================================================
log "Phase 1: Deploying CloudFormation stack..."

if [ ! -f "${SCRIPT_DIR}/params.json" ]; then
    warn "params.json not found. Copy from params.example.json and fill in values."
    warn "  cp ${SCRIPT_DIR}/params.example.json ${SCRIPT_DIR}/params.json"
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
        Integration=databricks \
        Environment="${ENVIRONMENT}"

# Get outputs
S3_AP_ALIAS=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].Outputs[?OutputKey==`S3AccessPointAlias`].OutputValue' \
    --output text --region "${REGION}")

IAM_ROLE_ARN=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].Outputs[?OutputKey==`DatabricksRoleArn`].OutputValue' \
    --output text --region "${REGION}")

S3_AP_ARN=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].Outputs[?OutputKey==`S3AccessPointArn`].OutputValue' \
    --output text --region "${REGION}")

log "S3 AP Alias: ${S3_AP_ALIAS}"
log "IAM Role ARN: ${IAM_ROLE_ARN}"
log "S3 AP ARN: ${S3_AP_ARN}"

# =============================================================================
# Phase 2: Validate S3 AP Connectivity
# =============================================================================
log "Phase 2: Validating S3 AP connectivity..."

python "${PROJECT_ROOT}/shared/scripts/validate-access.py" \
    --access-point-alias "${S3_AP_ALIAS}" \
    --region "${REGION}" \
    --skip-write || warn "Write test failed (may need data on volume first)"

# =============================================================================
# Phase 3: Deploy Terraform (Databricks Unity Catalog)
# =============================================================================
log "Phase 3: Deploying Terraform (Unity Catalog resources)..."

if [ -f "${SCRIPT_DIR}/terraform/terraform.tfvars" ]; then
    cd "${SCRIPT_DIR}/terraform"
    terraform init -upgrade
    terraform plan \
        -var="s3_access_point_alias=${S3_AP_ALIAS}" \
        -var="s3_access_point_arn=${S3_AP_ARN}" \
        -var="iam_role_arn=${IAM_ROLE_ARN}" \
        -out=tfplan

    log "Terraform plan created. Review and apply:"
    log "  cd ${SCRIPT_DIR}/terraform && terraform apply tfplan"
else
    warn "terraform.tfvars not found. Skipping Terraform deployment."
    warn "  cp ${SCRIPT_DIR}/terraform/terraform.tfvars.example ${SCRIPT_DIR}/terraform/terraform.tfvars"
fi

# =============================================================================
# Summary
# =============================================================================
log ""
log "=========================================="
log "Deployment Summary"
log "=========================================="
log "  Stack:        ${STACK_NAME}"
log "  S3 AP Alias:  ${S3_AP_ALIAS}"
log "  IAM Role:     ${IAM_ROLE_ARN}"
log "  Region:       ${REGION}"
log ""
log "Next Steps:"
log "  1. Get External ID from Databricks UI (Storage Credential creation)"
log "  2. Update CloudFormation ExternalId parameter"
log "  3. Apply Terraform for Unity Catalog resources"
log "  4. Run notebooks 01-09 in Databricks workspace"
log "=========================================="

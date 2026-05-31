#!/bin/bash
# =============================================================================
# Create S3 Tables Table Bucket for Iceberg Metadata Catalog
# =============================================================================
# Creates the S3 Tables table bucket and Iceberg table with the metadata schema.
#
# Prerequisites:
#   - AWS CLI v2 with S3 Tables support
#   - IAM permissions: s3tables:CreateTableBucket, s3tables:CreateNamespace, s3tables:CreateTable
#
# Usage:
#   ./create-table-bucket.sh [create|status|delete]
#
# Environment Variables:
#   AWS_DEFAULT_REGION  - Target region (default: ap-northeast-1)
#   TABLE_BUCKET_NAME   - Table bucket name (default: fsxn-metadata-catalog)
# =============================================================================

set -euo pipefail

REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
TABLE_BUCKET_NAME="${TABLE_BUCKET_NAME:-fsxn-metadata-catalog}"
NAMESPACE="metadata"
TABLE_NAME="unstructured_files"
ACTION="${1:-status}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

case "${ACTION}" in
  create)
    log "Creating S3 Tables table bucket: ${TABLE_BUCKET_NAME}"
    log "  Region: ${REGION}"
    echo ""

    # Step 1: Create table bucket
    log "[1/3] Creating table bucket..."
    TABLE_BUCKET_ARN=$(aws s3tables create-table-bucket \
      --name "${TABLE_BUCKET_NAME}" \
      --region "${REGION}" \
      --query 'arn' \
      --output text 2>/dev/null || true)

    if [ -z "${TABLE_BUCKET_ARN}" ]; then
      # Bucket may already exist
      TABLE_BUCKET_ARN=$(aws s3tables get-table-bucket \
        --table-bucket-arn "arn:aws:s3tables:${REGION}:$(aws sts get-caller-identity --query Account --output text):bucket/${TABLE_BUCKET_NAME}" \
        --region "${REGION}" \
        --query 'arn' \
        --output text 2>/dev/null || true)

      if [ -n "${TABLE_BUCKET_ARN}" ]; then
        log "  Table bucket already exists: ${TABLE_BUCKET_ARN}"
      else
        error "Failed to create or find table bucket"
      fi
    else
      log "  Created: ${TABLE_BUCKET_ARN}"
    fi

    # Step 2: Create namespace
    log "[2/3] Creating namespace: ${NAMESPACE}..."
    aws s3tables create-namespace \
      --table-bucket-arn "${TABLE_BUCKET_ARN}" \
      --namespace "${NAMESPACE}" \
      --region "${REGION}" 2>/dev/null || log "  Namespace already exists"

    # Step 3: Create table with Iceberg schema
    log "[3/3] Creating Iceberg table: ${NAMESPACE}.${TABLE_NAME}..."
    aws s3tables create-table \
      --table-bucket-arn "${TABLE_BUCKET_ARN}" \
      --namespace "${NAMESPACE}" \
      --name "${TABLE_NAME}" \
      --format "ICEBERG" \
      --region "${REGION}" 2>/dev/null || log "  Table already exists"

    echo ""
    log "=== Setup Complete ==="
    log "  Table Bucket ARN: ${TABLE_BUCKET_ARN}"
    log "  Namespace:        ${NAMESPACE}"
    log "  Table:            ${TABLE_NAME}"
    echo ""
    log "Next steps:"
    log "  1. Run initial metadata scan:"
    log "     python scripts/initial-metadata-scan.py \\"
    log "       --access-point-arn <FSX_S3_AP_ARN> \\"
    log "       --table-bucket-arn ${TABLE_BUCKET_ARN}"
    log ""
    log "  2. Query with Athena (via SageMaker Lakehouse or Glue Catalog registration):"
    log "     SELECT * FROM \"${NAMESPACE}\".\"${TABLE_NAME}\" LIMIT 10;"
    ;;

  status)
    log "Checking S3 Tables table bucket status..."
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    TABLE_BUCKET_ARN="arn:aws:s3tables:${REGION}:${ACCOUNT_ID}:bucket/${TABLE_BUCKET_NAME}"

    echo ""
    aws s3tables get-table-bucket \
      --table-bucket-arn "${TABLE_BUCKET_ARN}" \
      --region "${REGION}" 2>/dev/null && log "  Table bucket exists" || warn "  Table bucket not found"

    echo ""
    aws s3tables list-tables \
      --table-bucket-arn "${TABLE_BUCKET_ARN}" \
      --namespace "${NAMESPACE}" \
      --region "${REGION}" 2>/dev/null || warn "  No tables found"
    ;;

  delete)
    warn "Deleting S3 Tables table bucket: ${TABLE_BUCKET_NAME}"
    warn "This will permanently delete all metadata records!"
    echo ""
    read -p "Are you sure? (y/N): " confirm
    if [[ "${confirm}" =~ ^[Yy]$ ]]; then
      ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
      TABLE_BUCKET_ARN="arn:aws:s3tables:${REGION}:${ACCOUNT_ID}:bucket/${TABLE_BUCKET_NAME}"

      # Delete table first
      aws s3tables delete-table \
        --table-bucket-arn "${TABLE_BUCKET_ARN}" \
        --namespace "${NAMESPACE}" \
        --name "${TABLE_NAME}" \
        --region "${REGION}" 2>/dev/null || true

      # Delete namespace
      aws s3tables delete-namespace \
        --table-bucket-arn "${TABLE_BUCKET_ARN}" \
        --namespace "${NAMESPACE}" \
        --region "${REGION}" 2>/dev/null || true

      # Delete table bucket
      aws s3tables delete-table-bucket \
        --table-bucket-arn "${TABLE_BUCKET_ARN}" \
        --region "${REGION}" 2>/dev/null || true

      log "Deleted."
    else
      log "Cancelled."
    fi
    ;;

  *)
    echo "Usage: $0 [create|status|delete]"
    echo ""
    echo "Actions:"
    echo "  create  - Create table bucket, namespace, and Iceberg table"
    echo "  status  - Check current table bucket status"
    echo "  delete  - Delete table bucket and all data (DESTRUCTIVE)"
    echo ""
    echo "Environment variables:"
    echo "  AWS_DEFAULT_REGION  - Target region (default: ap-northeast-1)"
    echo "  TABLE_BUCKET_NAME   - Bucket name (default: fsxn-metadata-catalog)"
    ;;
esac

#!/bin/bash
set -euo pipefail

# =============================================================================
# FSx for ONTAP Athena Integration — Resource Cleanup
# =============================================================================
# Deletes all resources created during verification:
#   - Athena workgroup (and saved queries)
#   - Glue database, tables, crawler
#   - CloudFormation stack
#   - Test data on FSx for ONTAP (optional)
#
# Usage:
#   ./cleanup.sh [--region ap-northeast-1] [--env dev] [--delete-data]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/../params.json"

REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
ENVIRONMENT="dev"
DELETE_DATA=false
STACK_NAME="fsxn-athena-integration"

while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --env) ENVIRONMENT="$2"; shift 2 ;;
    --delete-data) DELETE_DATA=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "============================================"
echo "FSx for ONTAP Athena Integration — Cleanup"
echo "============================================"
echo "Region:      ${REGION}"
echo "Environment: ${ENVIRONMENT}"
echo "Delete data: ${DELETE_DATA}"
echo ""

read -p "⚠️  This will delete all verification resources. Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 0
fi

# Load params
DATABASE_NAME="fsxn_athena_db"
WORKGROUP_NAME="fsxn-verification"
CRAWLER_NAME="fsxn-athena-crawler-${ENVIRONMENT}"

if [[ -f "${PARAMS_FILE}" ]]; then
  DATABASE_NAME=$(jq -r '.DatabaseName // "fsxn_athena_db"' "${PARAMS_FILE}")
  WORKGROUP_NAME=$(jq -r '.WorkgroupName // "fsxn-verification"' "${PARAMS_FILE}")
  CRAWLER_NAME=$(jq -r '.CrawlerName // "fsxn-athena-crawler-dev"' "${PARAMS_FILE}")
fi

# Step 1: Delete Athena workgroup
echo "🗑️  Deleting Athena workgroup: ${WORKGROUP_NAME}..."
aws athena delete-work-group \
  --work-group "${WORKGROUP_NAME}" \
  --recursive-delete-option \
  --region "${REGION}" 2>/dev/null || echo "  (already deleted or not found)"

# Step 2: Stop and delete Glue Crawler
echo "🗑️  Stopping Glue Crawler: ${CRAWLER_NAME}..."
aws glue stop-crawler --name "${CRAWLER_NAME}" --region "${REGION}" 2>/dev/null || true
echo "🗑️  Deleting Glue Crawler..."
aws glue delete-crawler --name "${CRAWLER_NAME}" --region "${REGION}" 2>/dev/null || echo "  (not found)"

# Step 3: Delete Glue tables and database
echo "🗑️  Deleting Glue tables in ${DATABASE_NAME}..."
TABLES=$(aws glue get-tables --database-name "${DATABASE_NAME}" --region "${REGION}" \
  --query 'TableList[].Name' --output text 2>/dev/null || echo "")
for TABLE in ${TABLES}; do
  echo "  Deleting table: ${TABLE}"
  aws glue delete-table --database-name "${DATABASE_NAME}" --name "${TABLE}" --region "${REGION}" 2>/dev/null || true
done

echo "🗑️  Deleting Glue database: ${DATABASE_NAME}..."
aws glue delete-database --name "${DATABASE_NAME}" --region "${REGION}" 2>/dev/null || echo "  (not found)"

# Step 4: Delete CloudFormation stack
echo "🗑️  Deleting CloudFormation stack: ${STACK_NAME}-${ENVIRONMENT}..."
aws cloudformation delete-stack \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --region "${REGION}" 2>/dev/null || echo "  (not found)"

echo "  Waiting for stack deletion..."
aws cloudformation wait stack-delete-complete \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --region "${REGION}" 2>/dev/null || echo "  (timeout or already deleted)"

# Step 5: Delete test data (optional)
if [[ "${DELETE_DATA}" == "true" ]]; then
  MOUNT_POINT=$(jq -r '.NfsMountPoint // "/mnt/fsxn"' "${PARAMS_FILE}" 2>/dev/null || echo "/mnt/fsxn")
  echo "🗑️  Deleting test data from FSx for ONTAP (${MOUNT_POINT})..."
  if mountpoint -q "${MOUNT_POINT}" 2>/dev/null; then
    rm -rf "${MOUNT_POINT}/transactions" "${MOUNT_POINT}/customers" "${MOUNT_POINT}/events" "${MOUNT_POINT}/gold"
    echo "  ✅ Test data deleted"
  else
    echo "  ⚠️  Mount point not available — skip data deletion"
  fi
fi

# Step 6: Clean local artifacts
echo "🗑️  Cleaning local test results..."
rm -rf "${SCRIPT_DIR}/../tests/results/"
rm -f "${SCRIPT_DIR}/../sample_data" 2>/dev/null || true

echo ""
echo "============================================"
echo "✅ Cleanup complete!"
echo "============================================"

#!/bin/bash
set -euo pipefail

# =============================================================================
# FSxN Glue Integration — Resource Cleanup
# =============================================================================
# Deletes all resources created during verification:
#   - Glue ETL jobs
#   - Glue Crawler
#   - Glue database and tables
#   - EventBridge rule
#   - CloudFormation stack
#   - ETL scripts from S3
#   - Test data on FSxN (optional)
#
# Usage:
#   ./cleanup.sh [--region ap-northeast-1] [--env dev] [--delete-data]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/../params.json"

REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
ENVIRONMENT="dev"
DELETE_DATA=false
STACK_NAME="fsxn-glue-integration"

while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --env) ENVIRONMENT="$2"; shift 2 ;;
    --delete-data) DELETE_DATA=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "============================================"
echo "FSxN Glue Integration — Cleanup"
echo "============================================"
echo "Region:      ${REGION}"
echo "Environment: ${ENVIRONMENT}"
echo "Delete data: ${DELETE_DATA}"
echo ""

read -p "⚠️  This will delete all Glue integration resources. Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Cancelled."
  exit 0
fi

# Load params
DATABASE_NAME="fsxn_glue_db"
CRAWLER_NAME="fsxn-glue-crawler-${ENVIRONMENT}"
BRONZE_TO_SILVER_JOB="fsxn-bronze-to-silver-${ENVIRONMENT}"
SILVER_TO_GOLD_JOB="fsxn-silver-to-gold-${ENVIRONMENT}"
ETL_SCRIPT_BUCKET=""

if [[ -f "${PARAMS_FILE}" ]]; then
  DATABASE_NAME=$(jq -r '.DatabaseName // "fsxn_glue_db"' "${PARAMS_FILE}")
  CRAWLER_NAME=$(jq -r '.CrawlerName // "fsxn-glue-crawler-dev"' "${PARAMS_FILE}")
  BRONZE_TO_SILVER_JOB=$(jq -r '.BronzeToSilverJob // "fsxn-bronze-to-silver-dev"' "${PARAMS_FILE}")
  SILVER_TO_GOLD_JOB=$(jq -r '.SilverToGoldJob // "fsxn-silver-to-gold-dev"' "${PARAMS_FILE}")
  ETL_SCRIPT_BUCKET=$(jq -r '.ETLScriptBucket // ""' "${PARAMS_FILE}")
fi

# Step 1: Stop and delete Glue ETL jobs
echo "🗑️  Deleting Glue ETL jobs..."
for JOB_NAME in "${BRONZE_TO_SILVER_JOB}" "${SILVER_TO_GOLD_JOB}"; do
  echo "  Deleting job: ${JOB_NAME}"
  aws glue delete-job --job-name "${JOB_NAME}" --region "${REGION}" 2>/dev/null || echo "    (not found)"
done

# Step 2: Stop and delete Glue Crawler
echo "🗑️  Stopping Glue Crawler: ${CRAWLER_NAME}..."
aws glue stop-crawler --name "${CRAWLER_NAME}" --region "${REGION}" 2>/dev/null || true
sleep 2
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

# Step 4: Delete EventBridge rule
RULE_NAME="fsxn-glue-etl-schedule-${ENVIRONMENT}"
echo "🗑️  Deleting EventBridge rule: ${RULE_NAME}..."
# Remove targets first
aws events remove-targets --rule "${RULE_NAME}" --ids "StartCrawler" \
  --region "${REGION}" 2>/dev/null || true
aws events delete-rule --name "${RULE_NAME}" --region "${REGION}" 2>/dev/null || echo "  (not found)"

# Step 5: Delete ETL scripts from S3
if [[ -n "${ETL_SCRIPT_BUCKET}" ]]; then
  echo "🗑️  Deleting ETL scripts from s3://${ETL_SCRIPT_BUCKET}/glue-scripts/..."
  aws s3 rm "s3://${ETL_SCRIPT_BUCKET}/glue-scripts/" --recursive --region "${REGION}" 2>/dev/null || true
  aws s3 rm "s3://${ETL_SCRIPT_BUCKET}/spark-logs/" --recursive --region "${REGION}" 2>/dev/null || true
  aws s3 rm "s3://${ETL_SCRIPT_BUCKET}/glue-temp/" --recursive --region "${REGION}" 2>/dev/null || true
fi

# Step 6: Delete CloudFormation stack
echo "🗑️  Deleting CloudFormation stack: ${STACK_NAME}-${ENVIRONMENT}..."
aws cloudformation delete-stack \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --region "${REGION}" 2>/dev/null || echo "  (not found)"

echo "  Waiting for stack deletion..."
aws cloudformation wait stack-delete-complete \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --region "${REGION}" 2>/dev/null || echo "  (timeout or already deleted)"

# Step 7: Delete test data (optional)
if [[ "${DELETE_DATA}" == "true" ]]; then
  MOUNT_POINT=$(jq -r '.NfsMountPoint // "/mnt/fsxn"' "${PARAMS_FILE}" 2>/dev/null || echo "/mnt/fsxn")
  echo "🗑️  Deleting test data from FSxN (${MOUNT_POINT})..."
  if mountpoint -q "${MOUNT_POINT}" 2>/dev/null; then
    rm -rf "${MOUNT_POINT}/bronze" "${MOUNT_POINT}/silver" "${MOUNT_POINT}/gold"
    echo "  ✅ Test data deleted (bronze, silver, gold)"
  else
    echo "  ⚠️  Mount point not available — skip data deletion"
  fi
fi

# Step 8: Clean local artifacts
echo "🗑️  Cleaning local test results..."
rm -rf "${SCRIPT_DIR}/../tests/results/"

echo ""
echo "============================================"
echo "✅ Cleanup complete!"
echo "============================================"

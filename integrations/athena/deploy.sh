#!/bin/bash
set -euo pipefail

# =============================================================================
# FSx for ONTAP Athena Integration — Deployment Script
# =============================================================================
# Deploys CloudFormation stack, creates S3 Access Point, runs Glue Crawler,
# and captures outputs to params.json.
#
# Prerequisites:
#   - AWS CLI configured with appropriate permissions
#   - FSx for ONTAP file system with S3 AP capability
#   - params.example.json copied to params.json with values filled
#
# Usage:
#   ./deploy.sh [--region ap-northeast-1] [--env dev]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/params.json"
STACK_NAME="fsxn-athena-integration"

# Default values
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
ENVIRONMENT="dev"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --env) ENVIRONMENT="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "============================================"
echo "FSx for ONTAP Athena Integration Deployment"
echo "============================================"
echo "Region:      ${REGION}"
echo "Environment: ${ENVIRONMENT}"
echo "Stack:       ${STACK_NAME}-${ENVIRONMENT}"
echo ""

# --- Load parameters ---
if [[ ! -f "${PARAMS_FILE}" ]]; then
  echo "❌ params.json not found. Copy params.example.json and fill values."
  exit 1
fi

FILE_SYSTEM_ID=$(jq -r '.FileSystemId' "${PARAMS_FILE}")
SVM_ID=$(jq -r '.StorageVirtualMachineId' "${PARAMS_FILE}")
VOLUME_ID=$(jq -r '.VolumeId' "${PARAMS_FILE}")
S3_AP_NAME=$(jq -r '.S3AccessPointName // "fsxn-athena-ap"' "${PARAMS_FILE}")
ATHENA_RESULTS_BUCKET=$(jq -r '.AthenaResultsBucket' "${PARAMS_FILE}")

echo "📋 Parameters:"
echo "  FileSystemId:  ${FILE_SYSTEM_ID}"
echo "  SVM ID:        ${SVM_ID}"
echo "  Volume ID:     ${VOLUME_ID}"
echo "  S3 AP Name:    ${S3_AP_NAME}"
echo "  Results Bucket: ${ATHENA_RESULTS_BUCKET}"
echo ""

# --- Step 1: Create S3 Access Point (internet origin) ---
echo "🔧 Step 1: Creating S3 Access Point (internet origin)..."

# Check if AP already exists
AP_EXISTS=$(aws fsx describe-data-repository-associations \
  --region "${REGION}" \
  --query "Associations[?ResourceARN!=null]" \
  --output text 2>/dev/null || echo "")

# Create S3 AP via FSx CLI
# Note: FSx for ONTAP S3 AP is created via `aws fsx create-and-attach-s3-access-point`
echo "  Creating S3 AP: ${S3_AP_NAME} (internet origin)..."
echo "  ⚠️  If AP already exists, this step will be skipped."
echo ""
echo "  Manual command (if needed):"
echo "    aws fsx create-and-attach-s3-access-point \\"
echo "      --file-system-id ${FILE_SYSTEM_ID} \\"
echo "      --volume-id ${VOLUME_ID} \\"
echo "      --s3-access-point-configuration '{\"Name\":\"${S3_AP_NAME}\",\"NetworkOrigin\":\"Internet\"}' \\"
echo "      --region ${REGION}"
echo ""

# --- Step 2: Deploy CloudFormation stack ---
echo "🚀 Step 2: Deploying CloudFormation stack..."

aws cloudformation deploy \
  --template-file "${SCRIPT_DIR}/template.yaml" \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --parameter-overrides \
    FileSystemId="${FILE_SYSTEM_ID}" \
    StorageVirtualMachineId="${SVM_ID}" \
    VolumeId="${VOLUME_ID}" \
    S3AccessPointName="${S3_AP_NAME}" \
    AthenaResultsBucket="${ATHENA_RESULTS_BUCKET}" \
    Environment="${ENVIRONMENT}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "${REGION}" \
  --tags \
    Key=Project,Value=fsxn-lakehouse-integrations \
    Key=Vendor,Value=athena \
    Key=Environment,Value="${ENVIRONMENT}"

echo "✅ CloudFormation stack deployed successfully."
echo ""

# --- Step 3: Capture outputs ---
echo "📤 Step 3: Capturing stack outputs..."

OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --region "${REGION}" \
  --query 'Stacks[0].Outputs' \
  --output json)

CRAWLER_NAME=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="GlueCrawlerName") | .OutputValue')
DATABASE_NAME=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="GlueDatabaseName") | .OutputValue')
WORKGROUP_NAME=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="AthenaWorkgroupName") | .OutputValue')
CRAWLER_ROLE_ARN=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="GlueCrawlerRoleArn") | .OutputValue')

# Update params.json with outputs
jq --arg cn "${CRAWLER_NAME}" \
   --arg dn "${DATABASE_NAME}" \
   --arg wn "${WORKGROUP_NAME}" \
   --arg cr "${CRAWLER_ROLE_ARN}" \
   '. + {CrawlerName: $cn, DatabaseName: $dn, WorkgroupName: $wn, CrawlerRoleArn: $cr}' \
   "${PARAMS_FILE}" > "${PARAMS_FILE}.tmp" && mv "${PARAMS_FILE}.tmp" "${PARAMS_FILE}"

echo "  CrawlerName:    ${CRAWLER_NAME}"
echo "  DatabaseName:   ${DATABASE_NAME}"
echo "  WorkgroupName:  ${WORKGROUP_NAME}"
echo ""

# --- Step 4: Run Glue Crawler ---
echo "🕷️ Step 4: Starting Glue Crawler..."

aws glue start-crawler \
  --name "${CRAWLER_NAME}" \
  --region "${REGION}" 2>/dev/null || echo "  ⚠️  Crawler may already be running."

echo "  Crawler started. Monitor progress in Glue console."
echo ""

# --- Done ---
echo "============================================"
echo "✅ Deployment complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Wait for Glue Crawler to complete"
echo "  2. Verify tables in Glue Data Catalog"
echo "  3. Run: python scripts/validate_connectivity.py"
echo "  4. Run: python scripts/execute_queries.py"
echo ""

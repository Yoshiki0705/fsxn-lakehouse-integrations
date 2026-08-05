#!/bin/bash
set -euo pipefail

# =============================================================================
# FSx for ONTAP Glue Integration — Deployment Script
# =============================================================================
# Deploys CloudFormation stack, uploads ETL scripts, runs Glue Crawler,
# and captures outputs to params.json.
#
# Prerequisites:
#   - AWS CLI configured with appropriate permissions
#   - FSx for ONTAP file system with S3 AP capability
#   - params.example.json copied to params.json with values filled
#   - S3 bucket for ETL scripts
#
# Usage:
#   ./deploy.sh [--region ap-northeast-1] [--env dev]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/params.json"
STACK_NAME="fsxn-glue-integration"

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
echo "FSx for ONTAP Glue Integration Deployment"
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
VOLUME_ID=$(jq -r '.VolumeId' "${PARAMS_FILE}")
S3_AP_NAME=$(jq -r '.S3AccessPointName // "fsxn-glue-ap"' "${PARAMS_FILE}")
ETL_SCRIPT_BUCKET=$(jq -r '.ETLScriptBucket' "${PARAMS_FILE}")
SCHEDULE_EXPRESSION=$(jq -r '.ScheduleExpression // "cron(0 2 * * ? *)"' "${PARAMS_FILE}")

echo "📋 Parameters:"
echo "  FileSystemId:     ${FILE_SYSTEM_ID}"
echo "  Volume ID:        ${VOLUME_ID}"
echo "  S3 AP Name:       ${S3_AP_NAME}"
echo "  ETL Script Bucket: ${ETL_SCRIPT_BUCKET}"
echo "  Schedule:         ${SCHEDULE_EXPRESSION}"
echo ""

# --- Step 1: Upload ETL scripts to S3 ---
echo "📤 Step 1: Uploading ETL scripts to S3..."

aws s3 cp "${SCRIPT_DIR}/etl/bronze_to_silver.py" \
  "s3://${ETL_SCRIPT_BUCKET}/glue-scripts/bronze_to_silver.py" \
  --region "${REGION}"

aws s3 cp "${SCRIPT_DIR}/etl/silver_to_gold.py" \
  "s3://${ETL_SCRIPT_BUCKET}/glue-scripts/silver_to_gold.py" \
  --region "${REGION}"

echo "  ✅ ETL scripts uploaded"
echo ""

# --- Step 2: Create S3 Access Point (internet origin) ---
echo "🔧 Step 2: Creating S3 Access Point (internet origin)..."
echo "  ⚠️  If AP already exists, this step will be skipped."
echo ""
echo "  Manual command (if needed):"
echo "    aws fsx create-and-attach-s3-access-point \\"
echo "      --file-system-id ${FILE_SYSTEM_ID} \\"
echo "      --volume-id ${VOLUME_ID} \\"
echo "      --s3-access-point-configuration '{\"Name\":\"${S3_AP_NAME}\",\"NetworkOrigin\":\"Internet\"}' \\"
echo "      --region ${REGION}"
echo ""

# --- Step 3: Deploy CloudFormation stack ---
echo "🚀 Step 3: Deploying CloudFormation stack..."

aws cloudformation deploy \
  --template-file "${SCRIPT_DIR}/template.yaml" \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --parameter-overrides \
    FileSystemId="${FILE_SYSTEM_ID}" \
    VolumeId="${VOLUME_ID}" \
    S3AccessPointName="${S3_AP_NAME}" \
    ETLScriptBucket="${ETL_SCRIPT_BUCKET}" \
    Environment="${ENVIRONMENT}" \
    ScheduleExpression="${SCHEDULE_EXPRESSION}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "${REGION}" \
  --tags \
    Key=Project,Value=fsxn-lakehouse-integrations \
    Key=Vendor,Value=glue \
    Key=Environment,Value="${ENVIRONMENT}"

echo "✅ CloudFormation stack deployed successfully."
echo ""

# --- Step 4: Capture outputs ---
echo "📤 Step 4: Capturing stack outputs..."

OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --region "${REGION}" \
  --query 'Stacks[0].Outputs' \
  --output json)

CRAWLER_NAME=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="GlueCrawlerName") | .OutputValue')
DATABASE_NAME=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="GlueDatabaseName") | .OutputValue')
BRONZE_TO_SILVER_JOB=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="BronzeToSilverJobName") | .OutputValue')
SILVER_TO_GOLD_JOB=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="SilverToGoldJobName") | .OutputValue')
GLUE_ROLE_ARN=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="GlueServiceRoleArn") | .OutputValue')

# Update params.json with outputs
jq --arg cn "${CRAWLER_NAME}" \
   --arg dn "${DATABASE_NAME}" \
   --arg bsj "${BRONZE_TO_SILVER_JOB}" \
   --arg sgj "${SILVER_TO_GOLD_JOB}" \
   --arg gr "${GLUE_ROLE_ARN}" \
   '. + {CrawlerName: $cn, DatabaseName: $dn, BronzeToSilverJob: $bsj, SilverToGoldJob: $sgj, GlueServiceRoleArn: $gr}' \
   "${PARAMS_FILE}" > "${PARAMS_FILE}.tmp" && mv "${PARAMS_FILE}.tmp" "${PARAMS_FILE}"

echo "  CrawlerName:        ${CRAWLER_NAME}"
echo "  DatabaseName:       ${DATABASE_NAME}"
echo "  BronzeToSilverJob:  ${BRONZE_TO_SILVER_JOB}"
echo "  SilverToGoldJob:    ${SILVER_TO_GOLD_JOB}"
echo ""

# --- Step 5: Run Glue Crawler ---
echo "🕷️ Step 5: Starting Glue Crawler..."

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
echo "  2. Verify tables: python scripts/run_crawler.py --wait"
echo "  3. Run ETL pipeline: python scripts/run_etl_pipeline.py"
echo "  4. Validate: python scripts/validate_connectivity.py"
echo ""

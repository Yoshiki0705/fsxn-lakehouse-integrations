#!/bin/bash
set -euo pipefail

# =============================================================================
# FSxN Delta Lake OSS — Deployment Script
# =============================================================================
# Deploys CloudFormation stack, creates S3 AP (VPC-scoped), and prepares
# EMR cluster configuration for Delta Lake verification.
#
# Usage:
#   ./deploy.sh [--region ap-northeast-1] [--env dev]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/params.json"
STACK_NAME="fsxn-delta-oss-integration"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
ENVIRONMENT="dev"

while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --env) ENVIRONMENT="$2"; shift 2 ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

if [[ ! -f "${PARAMS_FILE}" ]]; then
  echo "❌ params.json not found. Copy params.example.json and fill values."
  exit 1
fi

FILE_SYSTEM_ID=$(jq -r '.FileSystemId' "${PARAMS_FILE}")
VOLUME_ID=$(jq -r '.VolumeId' "${PARAMS_FILE}")
VPC_ID=$(jq -r '.VpcId' "${PARAMS_FILE}")
S3_AP_NAME=$(jq -r '.S3AccessPointName // "fsxn-delta-oss-ap"' "${PARAMS_FILE}")

echo "============================================"
echo "FSxN Delta Lake OSS Deployment"
echo "============================================"
echo "Region:    ${REGION}"
echo "VPC:       ${VPC_ID}"
echo "Volume:    ${VOLUME_ID}"
echo "S3 AP:     ${S3_AP_NAME}"
echo ""

# Step 1: Deploy CloudFormation
echo "🚀 Deploying CloudFormation..."
aws cloudformation deploy \
  --template-file "${SCRIPT_DIR}/template.yaml" \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --parameter-overrides \
    VpcId="${VPC_ID}" \
    FileSystemId="${FILE_SYSTEM_ID}" \
    VolumeId="${VOLUME_ID}" \
    S3AccessPointName="${S3_AP_NAME}" \
    Environment="${ENVIRONMENT}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "${REGION}" \
  --tags Key=Project,Value=fsxn-lakehouse-integrations Key=Vendor,Value=delta-lake-oss

echo "✅ Stack deployed"

# Step 2: Create S3 AP (VPC-scoped)
echo ""
echo "🔧 Create S3 AP (VPC-scoped):"
echo "  aws fsx create-and-attach-s3-access-point \\"
echo "    --name ${S3_AP_NAME} --type ONTAP \\"
echo "    --ontap-configuration 'VolumeId=${VOLUME_ID},FileSystemIdentity={Type=UNIX,UnixUser={Name=root}}' \\"
echo "    --s3-access-point 'VpcConfiguration={VpcId=${VPC_ID}}' \\"
echo "    --region ${REGION}"
echo ""
echo "Next steps:"
echo "  1. Create S3 AP (command above)"
echo "  2. Update params.json with S3AccessPointAlias"
echo "  3. Upload sample data via NFS"
echo "  4. Run: spark-submit notebooks/01_delta_crud.py --s3-ap-alias <alias>"

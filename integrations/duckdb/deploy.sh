#!/bin/bash
set -euo pipefail

# =============================================================================
# FSxN DuckDB Integration — Deployment Script
# =============================================================================
# Builds DuckDB Lambda Layer, deploys CloudFormation stack, captures outputs,
# and tests Lambda invocation.
#
# Prerequisites:
#   - AWS CLI configured with appropriate permissions
#   - Docker (for building arm64 Lambda Layer)
#   - params.example.json copied to params.json with values filled
#
# Usage:
#   ./deploy.sh [--region ap-northeast-1] [--env dev] [--skip-layer]
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/params.json"
STACK_NAME="fsxn-duckdb-integration"

# Default values
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
ENVIRONMENT="dev"
SKIP_LAYER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --env) ENVIRONMENT="$2"; shift 2 ;;
    --skip-layer) SKIP_LAYER=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "============================================"
echo "FSxN DuckDB Integration Deployment"
echo "============================================"
echo "Region:      ${REGION}"
echo "Environment: ${ENVIRONMENT}"
echo "Stack:       ${STACK_NAME}-${ENVIRONMENT}"
echo "Skip Layer:  ${SKIP_LAYER}"
echo ""

# --- Load parameters ---
if [[ ! -f "${PARAMS_FILE}" ]]; then
  echo "❌ params.json not found. Copy params.example.json and fill values."
  echo "   cp params.example.json params.json"
  exit 1
fi

VPC_ID=$(jq -r '.VpcId' "${PARAMS_FILE}")
SUBNET_IDS=$(jq -r '.SubnetIds | join(",")' "${PARAMS_FILE}")
SECURITY_GROUP_ID=$(jq -r '.SecurityGroupId' "${PARAMS_FILE}")
S3_AP_NAME=$(jq -r '.S3AccessPointName // "fsxn-duckdb-ap"' "${PARAMS_FILE}")
S3_AP_ALIAS=$(jq -r '.S3AccessPointAlias' "${PARAMS_FILE}")
LAMBDA_MEMORY=$(jq -r '.LambdaMemorySize // 1024' "${PARAMS_FILE}")
LAMBDA_TIMEOUT=$(jq -r '.LambdaTimeout // 300' "${PARAMS_FILE}")
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "📋 Parameters:"
echo "  VPC ID:          ${VPC_ID}"
echo "  Subnet IDs:      ${SUBNET_IDS}"
echo "  Security Group:  ${SECURITY_GROUP_ID}"
echo "  S3 AP Name:      ${S3_AP_NAME}"
echo "  S3 AP Alias:     ${S3_AP_ALIAS}"
echo "  Lambda Memory:   ${LAMBDA_MEMORY} MB"
echo "  Lambda Timeout:  ${LAMBDA_TIMEOUT} s"
echo "  Account ID:      ${ACCOUNT_ID}"
echo ""

# --- Step 1: Build Lambda Layer ---
if [[ "${SKIP_LAYER}" == "false" ]]; then
  echo "📦 Step 1: Building DuckDB Lambda Layer (arm64)..."
  
  LAYER_SCRIPT="${SCRIPT_DIR}/lambda/build_layer.sh"
  if [[ ! -f "${LAYER_SCRIPT}" ]]; then
    echo "❌ build_layer.sh not found at ${LAYER_SCRIPT}"
    exit 1
  fi
  
  chmod +x "${LAYER_SCRIPT}"
  bash "${LAYER_SCRIPT}"
  
  LAYER_ZIP="${SCRIPT_DIR}/lambda/layer.zip"
  if [[ ! -f "${LAYER_ZIP}" ]]; then
    echo "❌ layer.zip not generated"
    exit 1
  fi
  
  LAYER_SIZE=$(du -h "${LAYER_ZIP}" | cut -f1)
  echo "  ✅ Layer built: ${LAYER_ZIP} (${LAYER_SIZE})"
  echo ""
  
  # Upload layer to S3
  LAYER_BUCKET="fsxn-duckdb-layers-${ACCOUNT_ID}-${REGION}"
  LAYER_KEY="layers/duckdb-layer-${ENVIRONMENT}.zip"
  
  echo "  Ensuring layer bucket exists..."
  aws s3api head-bucket --bucket "${LAYER_BUCKET}" 2>/dev/null || \
    aws s3api create-bucket \
      --bucket "${LAYER_BUCKET}" \
      --region "${REGION}" \
      --create-bucket-configuration LocationConstraint="${REGION}"
  
  echo "  Uploading layer to s3://${LAYER_BUCKET}/${LAYER_KEY}..."
  aws s3 cp "${LAYER_ZIP}" "s3://${LAYER_BUCKET}/${LAYER_KEY}" --region "${REGION}"
  echo "  ✅ Layer uploaded"
  echo ""
else
  echo "⏭️  Step 1: Skipping layer build (--skip-layer)"
  echo ""
fi

# --- Step 2: Package Lambda function code ---
echo "📦 Step 2: Packaging Lambda function..."

LAMBDA_ZIP="${SCRIPT_DIR}/lambda/function.zip"
pushd "${SCRIPT_DIR}/lambda" > /dev/null
zip -j "${LAMBDA_ZIP}" handler.py
popd > /dev/null
echo "  ✅ Function packaged: ${LAMBDA_ZIP}"
echo ""

# --- Step 3: Deploy CloudFormation stack ---
echo "🚀 Step 3: Deploying CloudFormation stack..."

aws cloudformation deploy \
  --template-file "${SCRIPT_DIR}/template.yaml" \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --parameter-overrides \
    VpcId="${VPC_ID}" \
    SubnetIds="${SUBNET_IDS}" \
    SecurityGroupId="${SECURITY_GROUP_ID}" \
    S3AccessPointName="${S3_AP_NAME}" \
    S3AccessPointAlias="${S3_AP_ALIAS}" \
    LambdaMemorySize="${LAMBDA_MEMORY}" \
    LambdaTimeout="${LAMBDA_TIMEOUT}" \
    Environment="${ENVIRONMENT}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "${REGION}" \
  --tags \
    Key=Project,Value=fsxn-lakehouse-integrations \
    Key=Vendor,Value=duckdb \
    Key=Environment,Value="${ENVIRONMENT}"

echo "  ✅ CloudFormation stack deployed"
echo ""

# --- Step 4: Update Lambda function code ---
echo "📤 Step 4: Updating Lambda function code..."

FUNCTION_NAME="fsxn-duckdb-query-${ENVIRONMENT}"
aws lambda update-function-code \
  --function-name "${FUNCTION_NAME}" \
  --zip-file "fileb://${LAMBDA_ZIP}" \
  --region "${REGION}" \
  --output text --query 'FunctionArn'

echo "  ✅ Function code updated"
echo ""

# --- Step 5: Capture outputs ---
echo "📤 Step 5: Capturing stack outputs..."

OUTPUTS=$(aws cloudformation describe-stacks \
  --stack-name "${STACK_NAME}-${ENVIRONMENT}" \
  --region "${REGION}" \
  --query 'Stacks[0].Outputs' \
  --output json)

FUNCTION_ARN=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="LambdaFunctionArn") | .OutputValue')
ROLE_ARN=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="LambdaRoleArn") | .OutputValue')
LAYER_ARN=$(echo "${OUTPUTS}" | jq -r '.[] | select(.OutputKey=="LayerVersionArn") | .OutputValue')

jq --arg fn "${FUNCTION_NAME}" \
   --arg fa "${FUNCTION_ARN}" \
   --arg ra "${ROLE_ARN}" \
   --arg la "${LAYER_ARN}" \
   '. + {FunctionName: $fn, FunctionArn: $fa, LambdaRoleArn: $ra, LayerArn: $la}' \
   "${PARAMS_FILE}" > "${PARAMS_FILE}.tmp" && mv "${PARAMS_FILE}.tmp" "${PARAMS_FILE}"

echo "  FunctionName: ${FUNCTION_NAME}"
echo "  FunctionArn:  ${FUNCTION_ARN}"
echo "  LayerArn:     ${LAYER_ARN}"
echo ""

# --- Step 6: Test Lambda invocation ---
echo "🧪 Step 6: Testing Lambda invocation..."

TEST_PAYLOAD='{"query": "SELECT version() AS duckdb_version, current_timestamp AS ts"}'
RESPONSE_FILE="/tmp/duckdb-lambda-test-response.json"

aws lambda invoke \
  --function-name "${FUNCTION_NAME}" \
  --payload "${TEST_PAYLOAD}" \
  --cli-binary-format raw-in-base64-out \
  --region "${REGION}" \
  "${RESPONSE_FILE}" > /dev/null

echo "  Response:"
cat "${RESPONSE_FILE}" | jq .
rm -f "${RESPONSE_FILE}"
echo ""

# --- Done ---
echo "============================================"
echo "✅ Deployment complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Validate connectivity: python scripts/validate_connectivity.py"
echo "  2. Run local queries:     python notebooks/01_local_queries.py"
echo "  3. Run benchmarks:        python tests/benchmark_duckdb_fsxn.py"
echo ""

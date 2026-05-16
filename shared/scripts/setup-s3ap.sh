#!/bin/bash
# =============================================================================
# setup-s3ap.sh - S3 Access Point Setup Script
# =============================================================================
# Creates and configures an S3 Access Point for FSx for NetApp ONTAP.
# This script automates the manual steps of S3 AP creation and validation.
#
# Usage:
#   ./setup-s3ap.sh --bucket <svm-bucket> --vpc <vpc-id> --name <ap-name>
#
# Prerequisites:
#   - AWS CLI v2 configured
#   - FSxN SVM with S3 protocol enabled
#   - VPC ID where FSxN resides
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default values
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
AP_NAME=""
BUCKET_NAME=""
VPC_ID=""
ACCOUNT_ID=""

usage() {
    echo "Usage: $0 --bucket <svm-bucket> --vpc <vpc-id> --name <ap-name> [--region <region>]"
    echo ""
    echo "Options:"
    echo "  --bucket    FSxN SVM S3 bucket name"
    echo "  --vpc       VPC ID where FSxN resides"
    echo "  --name      S3 Access Point name"
    echo "  --region    AWS region (default: ap-northeast-1)"
    echo "  --help      Show this help message"
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --bucket) BUCKET_NAME="$2"; shift 2 ;;
        --vpc) VPC_ID="$2"; shift 2 ;;
        --name) AP_NAME="$2"; shift 2 ;;
        --region) REGION="$2"; shift 2 ;;
        --help) usage ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

# Validate required parameters
if [[ -z "$BUCKET_NAME" || -z "$VPC_ID" || -z "$AP_NAME" ]]; then
    echo -e "${RED}Error: --bucket, --vpc, and --name are required${NC}"
    usage
fi

# Get AWS Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
echo -e "${GREEN}AWS Account: ${ACCOUNT_ID}${NC}"
echo -e "${GREEN}Region: ${REGION}${NC}"

# =============================================================================
# Step 1: Create S3 Access Point
# =============================================================================
echo -e "\n${YELLOW}Step 1: Creating S3 Access Point...${NC}"

aws s3control create-access-point \
    --account-id "$ACCOUNT_ID" \
    --name "$AP_NAME" \
    --bucket "$BUCKET_NAME" \
    --vpc-configuration "VpcId=$VPC_ID" \
    --region "$REGION" 2>/dev/null || {
    echo -e "${YELLOW}Access Point may already exist, continuing...${NC}"
}

# Get Access Point ARN
AP_ARN="arn:aws:s3:${REGION}:${ACCOUNT_ID}:accesspoint/${AP_NAME}"
echo -e "${GREEN}Access Point ARN: ${AP_ARN}${NC}"

# =============================================================================
# Step 2: Get Access Point Alias
# =============================================================================
echo -e "\n${YELLOW}Step 2: Getting Access Point details...${NC}"

AP_INFO=$(aws s3control get-access-point \
    --account-id "$ACCOUNT_ID" \
    --name "$AP_NAME" \
    --region "$REGION" \
    --output json)

AP_ALIAS=$(echo "$AP_INFO" | python3 -c "import sys,json; print(json.load(sys.stdin).get('Alias','N/A'))")
echo -e "${GREEN}Access Point Alias: ${AP_ALIAS}${NC}"

# =============================================================================
# Step 3: Set Access Point Policy
# =============================================================================
echo -e "\n${YELLOW}Step 3: Setting Access Point policy...${NC}"

POLICY=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowAccountAccess",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::${ACCOUNT_ID}:root"
            },
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket",
                "s3:GetBucketLocation"
            ],
            "Resource": [
                "${AP_ARN}",
                "${AP_ARN}/object/*"
            ]
        }
    ]
}
EOF
)

aws s3control put-access-point-policy \
    --account-id "$ACCOUNT_ID" \
    --name "$AP_NAME" \
    --policy "$POLICY" \
    --region "$REGION"

echo -e "${GREEN}Policy applied successfully${NC}"

# =============================================================================
# Step 4: Validate Access
# =============================================================================
echo -e "\n${YELLOW}Step 4: Validating access...${NC}"

# Try to list objects
if aws s3api list-objects-v2 \
    --bucket "$AP_ALIAS" \
    --max-keys 5 \
    --region "$REGION" 2>/dev/null; then
    echo -e "${GREEN}✅ ListObjects successful${NC}"
else
    echo -e "${YELLOW}⚠️  ListObjects failed (may need VPC endpoint or data)${NC}"
fi

# =============================================================================
# Summary
# =============================================================================
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}S3 Access Point Setup Complete${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "  Name:    ${AP_NAME}"
echo -e "  ARN:     ${AP_ARN}"
echo -e "  Alias:   ${AP_ALIAS}"
echo -e "  Bucket:  ${BUCKET_NAME}"
echo -e "  VPC:     ${VPC_ID}"
echo -e "  Region:  ${REGION}"
echo -e ""
echo -e "  S3 URL:  s3://${AP_ALIAS}/"
echo -e "${GREEN}========================================${NC}"

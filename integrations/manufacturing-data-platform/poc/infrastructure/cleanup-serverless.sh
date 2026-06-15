#!/bin/bash
set -euo pipefail

# Cleanup: Delete MSK Serverless cluster (no longer needed after Provisioned migration)
# Run this AFTER MSK Provisioned + Multi-VPC connectivity is verified working.
#
# Saves ~$50-150/month by removing unused Serverless cluster.

REGION="ap-northeast-1"
SERVERLESS_STACK="manufacturing-poc-msk"

echo "[$(date)] Deleting MSK Serverless CloudFormation stack: ${SERVERLESS_STACK}"
echo "  This will delete the MSK Serverless cluster and associated IAM policy."
echo ""
echo "  Press Ctrl+C to cancel, or Enter to continue..."
read -r

aws cloudformation delete-stack --stack-name "$SERVERLESS_STACK" --region "$REGION"
echo "[$(date)] Stack deletion initiated. Monitor with:"
echo "  aws cloudformation describe-stacks --stack-name $SERVERLESS_STACK --region $REGION --query 'Stacks[0].StackStatus'"

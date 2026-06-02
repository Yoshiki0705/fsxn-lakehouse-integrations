#!/bin/bash
# =============================================================================
# Deploy Industry Use Case Stack
# =============================================================================
# Deploys the shared CloudFormation template for a specific industry.
#
# Usage:
#   ./deploy.sh --industry manufacturing [--ap-alias <alias>] [--opensearch]
#   ./deploy.sh --industry healthcare --ap-alias my-ap-ext-s3alias --opensearch
#   ./deploy.sh --delete --industry manufacturing
#
# Cost: $0 when idle (all resources scale-to-zero)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INDUSTRY=""
AP_ALIAS=""
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
OPENSEARCH="false"
DELETE=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --industry) INDUSTRY="$2"; shift 2 ;;
    --ap-alias) AP_ALIAS="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --opensearch) OPENSEARCH="true"; shift ;;
    --delete) DELETE=true; shift ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

if [[ -z "$INDUSTRY" ]]; then
  echo "Usage: $0 --industry <name> [--ap-alias <alias>] [--opensearch]"
  echo "       $0 --delete --industry <name>"
  echo ""
  echo "Available industries:"
  ls -d "$SCRIPT_DIR"/../*/ 2>/dev/null | grep -v _shared | xargs -I{} basename {} | sort
  exit 1
fi

STACK_NAME="fsxn-${INDUSTRY}-demo"

if [[ "$DELETE" == "true" ]]; then
  echo "Deleting stack: $STACK_NAME"
  aws cloudformation delete-stack --stack-name "$STACK_NAME" --region "$REGION"
  echo "Stack deletion initiated. Monitor: aws cloudformation describe-stacks --stack-name $STACK_NAME"
  exit 0
fi

echo "═══════════════════════════════════════════════════════════"
echo " Deploying: $INDUSTRY"
echo " Stack:     $STACK_NAME"
echo " Region:    $REGION"
echo " S3 AP:     ${AP_ALIAS:-'(none - S3-only mode)'}"
echo " OpenSearch: $OPENSEARCH"
echo "═══════════════════════════════════════════════════════════"
echo ""

aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/cloudformation/industry-demo-stack.yaml" \
  --stack-name "$STACK_NAME" \
  --parameter-overrides \
    Industry="$INDUSTRY" \
    S3AccessPointAlias="${AP_ALIAS}" \
    EnableOpenSearch="$OPENSEARCH" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --no-fail-on-empty-changeset \
  --tags Key=Project,Value=fsxn-lakehouse-integrations Key=Industry,Value="$INDUSTRY"

echo ""
echo "✅ Stack deployed: $STACK_NAME"
echo ""
echo "Outputs:"
aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' --output table 2>/dev/null || true

echo ""
echo "Next steps:"
echo "  1. Generate sample data:"
echo "     python demo/sample-data/generate-sample-data.py --industry $INDUSTRY --count 100"
echo ""
echo "  2. Run demo:"
echo "     ./use-cases/_shared/demo-runner.sh --industry $INDUSTRY --ap-alias ${AP_ALIAS:-<your-alias>}"
echo ""
echo "  3. Cleanup:"
echo "     $0 --delete --industry $INDUSTRY"

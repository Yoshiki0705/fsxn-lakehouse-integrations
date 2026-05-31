#!/bin/bash
# =============================================================================
# Iceberg Metadata Catalog — Customer Demo Script
# =============================================================================
# Runs the complete demo flow:
#   1. Deploy infrastructure (CloudFormation)
#   2. Initial metadata scan (FSx S3 AP → S3 Tables)
#   3. AI enrichment (Bedrock Vision + Embeddings)
#   4. Athena query demonstration
#   5. Vector similarity search (OpenSearch)
#   6. PII detection + anonymization
#
# Prerequisites:
#   - AWS CLI v2 configured
#   - FSx for ONTAP with S3 Access Point
#   - Python 3.12+ with: boto3, pyarrow, pyiceberg[s3tables], opensearch-py
#   - Bedrock model access (Claude 3 Haiku, Titan Embeddings V2)
#
# Usage:
#   ./run-demo.sh --ap-alias <FSx-S3-AP-alias> [--region ap-northeast-1] [--skip-deploy]
#
# Duration: ~15 minutes (including CloudFormation deployment)
# Cost: < $1 (all resources scale-to-zero when idle)
# =============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
BOLD='\033[1m'

log() { echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1"; }
info() { echo -e "${CYAN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
header() { echo -e "\n${BOLD}═══════════════════════════════════════════════════${NC}"; echo -e "${BOLD} $1${NC}"; echo -e "${BOLD}═══════════════════════════════════════════════════${NC}\n"; }

# Parse arguments
AP_ALIAS=""
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
SKIP_DEPLOY=false
STACK_NAME="fsxn-metadata-catalog-demo"

while [[ $# -gt 0 ]]; do
  case $1 in
    --ap-alias) AP_ALIAS="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --skip-deploy) SKIP_DEPLOY=true; shift ;;
    --stack-name) STACK_NAME="$2"; shift 2 ;;
    *) error "Unknown option: $1" ;;
  esac
done

if [[ -z "$AP_ALIAS" ]]; then
  error "Usage: $0 --ap-alias <FSx-S3-AP-alias-ext-s3alias> [--region ap-northeast-1]"
fi

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
TABLE_BUCKET_ARN="arn:aws:s3tables:${REGION}:${ACCOUNT_ID}:bucket/fsxn-metadata-catalog"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${SCRIPT_DIR}/../.."

header "Iceberg Metadata Catalog — Customer Demo"
info "Account:      ${ACCOUNT_ID}"
info "Region:       ${REGION}"
info "S3 AP Alias:  ${AP_ALIAS}"
info "Stack:        ${STACK_NAME}"
echo ""

# Record demo start time
DEMO_START=$(date +%s)

# =========================================================================
# Step 1: Before/After Comparison (Impact Demo)
# =========================================================================
header "Step 1/8: Before/After — File Discovery Time"

python3 "${SCRIPT_DIR}/demo-before-after.py" \
  --ap-alias "${AP_ALIAS}" \
  --region "${REGION}" \
  --search-term "invoice"

# =========================================================================
# Step 2: Deploy Infrastructure
# =========================================================================
if [[ "$SKIP_DEPLOY" == "false" ]]; then
  header "Step 2/8: Deploy Infrastructure (CloudFormation)"

  aws cloudformation deploy \
    --template-file "${SCRIPT_DIR}/../cloudformation/demo-stack.yaml" \
    --stack-name "${STACK_NAME}" \
    --parameter-overrides \
      S3AccessPointAlias="${AP_ALIAS}" \
      Region="${REGION}" \
    --capabilities CAPABILITY_NAMED_IAM \
    --region "${REGION}" \
    --no-fail-on-empty-changeset

  log "✅ Infrastructure deployed"
  aws cloudformation describe-stacks --stack-name "${STACK_NAME}" --region "${REGION}" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' --output table
else
  log "⏭️  Skipping deployment (--skip-deploy)"
fi

# =========================================================================
# Step 3: Initial Metadata Scan
# =========================================================================
header "Step 3/8: Scan Files on FSx for ONTAP"

log "Scanning files via S3 Access Point..."
python3 "${PROJECT_DIR}/scripts/initial-metadata-scan.py" \
  --access-point-arn "${AP_ALIAS}" \
  --table-bucket-arn "${TABLE_BUCKET_ARN}" \
  --max-files 100

log "✅ Metadata scan complete"

# =========================================================================
# Step 4: AI Enrichment
# =========================================================================
header "Step 4/8: AI Enrichment (Bedrock Vision + Embeddings)"

python3 "${SCRIPT_DIR}/demo-enrich.py" \
  --table-bucket-arn "${TABLE_BUCKET_ARN}" \
  --ap-alias "${AP_ALIAS}" \
  --region "${REGION}" \
  --max-files 5

log "✅ AI enrichment complete"

# =========================================================================
# Step 5: Athena Query + Time Travel
# =========================================================================
header "Step 5/8: Query Metadata with Athena + Time Travel"

QUERY_SQL="SELECT file_name, file_type, classification, confidence_score, enrichment_status FROM \"s3tablescatalog/fsxn-metadata-catalog\".\"metadata\".\"unstructured_files\" WHERE is_deleted = false ORDER BY file_size DESC LIMIT 10"

QUERY_ID=$(aws athena start-query-execution \
  --query-string "${QUERY_SQL}" \
  --work-group primary \
  --result-configuration "OutputLocation=s3://fsxn-athena-verification-results-${REGION}/demo/" \
  --region "${REGION}" \
  --query 'QueryExecutionId' --output text)

log "Query submitted: ${QUERY_ID}"
log "Waiting for results..."
sleep 12

STATUS=$(aws athena get-query-execution --query-execution-id "${QUERY_ID}" --region "${REGION}" \
  --query 'QueryExecution.Status.State' --output text)

if [[ "$STATUS" == "SUCCEEDED" ]]; then
  log "✅ Query succeeded"
  aws athena get-query-results --query-execution-id "${QUERY_ID}" --region "${REGION}" \
    --query 'ResultSet.Rows[*].Data[*].VarCharValue' --output table 2>/dev/null | head -30
else
  warn "Query status: ${STATUS}"
fi

echo ""
log "Iceberg Time Travel (snapshot history):"
python3 "${SCRIPT_DIR}/demo-time-travel.py" --region "${REGION}"

# =========================================================================
# Step 6: Vector Similarity Search
# =========================================================================
header "Step 6/8: Vector Similarity Search (OpenSearch)"

python3 "${SCRIPT_DIR}/demo-search.py" \
  --query "find invoice or payment documents" \
  --region "${REGION}"

# =========================================================================
# Step 7: PII Detection + Anonymization + Access Control
# =========================================================================
header "Step 7/8: PII Detection, Anonymization & Access Control"

python3 "${SCRIPT_DIR}/demo-anonymize.py" \
  --ap-alias "${AP_ALIAS}" \
  --region "${REGION}"

echo ""
python3 "${SCRIPT_DIR}/demo-access-control.py" \
  --region "${REGION}"

# =========================================================================
# Step 8: Cost & ROI Summary
# =========================================================================
header "Step 8/8: Cost & ROI Analysis"

python3 "${SCRIPT_DIR}/demo-cost-calculator.py" \
  --files-processed 5 \
  --queries-run 10

# =========================================================================
# Summary
# =========================================================================
header "Demo Complete ✅"

# Calculate demo duration
DEMO_END=$(date +%s)
DEMO_DURATION=$((DEMO_END - DEMO_START))
DEMO_MINUTES=$((DEMO_DURATION / 60))
DEMO_SECONDS=$((DEMO_DURATION % 60))

echo -e "${BOLD}Demo duration: ${DEMO_MINUTES}m ${DEMO_SECONDS}s${NC}"
echo ""
echo -e "${BOLD}Demonstrated capabilities:${NC}"
echo "  1. ✅ Before/After: File search time comparison (ListObjectsV2 vs Athena)"
echo "  2. ✅ Metadata scan: FSx S3 AP → S3 Tables (Iceberg)"
echo "  3. ✅ AI classification: Bedrock Vision (image → category)"
echo "  4. ✅ Vector embeddings: Titan Embeddings V2 (1024-dim)"
echo "  5. ✅ SQL queries: Athena < 2 seconds + Iceberg Time Travel"
echo "  6. ✅ Similarity search: OpenSearch kNN"
echo "  7. ✅ PII anonymization: Comprehend/Bedrock + redaction"
echo "  8. ✅ Access control: Lake Formation grant/revoke + CloudTrail audit"
echo "  9. ✅ Cost & ROI: Demo cost + projected savings"
echo ""
echo -e "${BOLD}Cost:${NC}"
echo "  • This demo: < \$1"
echo "  • Active: ~\$0.01/file (AI processing)"
echo "  • Idle: \$0 (all resources scale-to-zero)"
echo ""
echo -e "${BOLD}Cleanup:${NC}"
echo "  aws cloudformation delete-stack --stack-name ${STACK_NAME} --region ${REGION}"

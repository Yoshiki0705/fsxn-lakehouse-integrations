#!/bin/bash
# =============================================================================
# Iceberg Metadata Catalog — Prerequisites Check
# =============================================================================
# Run this BEFORE attempting the demo to verify your environment is ready.
# Checks: AWS CLI, Python, packages, credentials, Bedrock access, region support
#
# Usage:
#   ./check-prerequisites.sh [--region ap-northeast-1] [--ap-alias <alias>]
#
# Exit codes:
#   0 = All prerequisites met
#   1 = Critical prerequisites missing (cannot proceed)
#   2 = Optional prerequisites missing (can proceed with limitations)
# =============================================================================

set -uo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
AP_ALIAS=""
CRITICAL_FAIL=0
OPTIONAL_FAIL=0

while [[ $# -gt 0 ]]; do
  case $1 in
    --region) REGION="$2"; shift 2 ;;
    --ap-alias) AP_ALIAS="$2"; shift 2 ;;
    *) shift ;;
  esac
done

pass() { echo -e "  ${GREEN}✅${NC} $1"; }
fail() { echo -e "  ${RED}❌${NC} $1"; CRITICAL_FAIL=1; }
warn() { echo -e "  ${YELLOW}⚠️${NC} $1"; OPTIONAL_FAIL=1; }
info() { echo -e "  ${CYAN}ℹ️${NC} $1"; }

echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD} Iceberg Metadata Catalog — Prerequisites Check${NC}"
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
echo ""

# =========================================================================
# 1. Basic Tools
# =========================================================================
echo -e "${BOLD}[1/6] Basic Tools${NC}"

if command -v aws &>/dev/null; then
  AWS_VER=$(aws --version 2>&1 | head -1)
  pass "AWS CLI: ${AWS_VER}"
else
  fail "AWS CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
fi

if command -v python3 &>/dev/null; then
  PY_VER=$(python3 --version 2>&1)
  pass "Python: ${PY_VER}"
else
  fail "Python 3 not found. Install Python 3.12+: https://www.python.org/downloads/"
fi

if command -v pip3 &>/dev/null || command -v pip &>/dev/null; then
  pass "pip available"
else
  warn "pip not found. May need: python3 -m ensurepip"
fi
echo ""

# =========================================================================
# 2. Python Packages
# =========================================================================
echo -e "${BOLD}[2/6] Python Packages${NC}"

check_package() {
  if python3 -c "import $1" 2>/dev/null; then
    pass "$1"
  else
    fail "$1 not installed. Run: pip install -r requirements.txt"
  fi
}

check_package "boto3"
check_package "pyarrow"
check_package "pyiceberg"
if python3 -c "import opensearchpy" 2>/dev/null; then
  pass "opensearch-py"
else
  warn "opensearch-py not installed (needed for vector search only)"
fi
echo ""

# =========================================================================
# 3. AWS Credentials
# =========================================================================
echo -e "${BOLD}[3/6] AWS Credentials & Identity${NC}"

if aws sts get-caller-identity --region "$REGION" &>/dev/null; then
  IDENTITY=$(aws sts get-caller-identity --query "Arn" --output text --region "$REGION" 2>/dev/null)
  pass "AWS credentials valid"
  info "Identity: ${IDENTITY}"
  info "Region: ${REGION}"
else
  fail "AWS credentials not configured or expired. Run: aws configure"
fi
echo ""

# =========================================================================
# 4. Bedrock Model Access
# =========================================================================
echo -e "${BOLD}[4/6] Bedrock Model Access${NC}"

if aws bedrock list-foundation-models --region "$REGION" --query "modelSummaries[?modelId=='anthropic.claude-3-haiku-20240307-v1:0'].modelId" --output text 2>/dev/null | grep -q "claude"; then
  pass "Claude 3 Haiku available in region"
else
  warn "Cannot verify Claude 3 Haiku. Enable at: https://console.aws.amazon.com/bedrock/home#/modelaccess"
fi

if aws bedrock list-foundation-models --region "$REGION" --query "modelSummaries[?modelId=='amazon.titan-embed-text-v2:0'].modelId" --output text 2>/dev/null | grep -q "titan"; then
  pass "Titan Embeddings V2 available in region"
else
  warn "Cannot verify Titan Embeddings V2. Enable at: https://console.aws.amazon.com/bedrock/home#/modelaccess"
fi

info "If models are not enabled, visit: https://console.aws.amazon.com/bedrock/home#/modelaccess"
info "Model access approval may take a few minutes."
echo ""

# =========================================================================
# 5. S3 Tables & Glue
# =========================================================================
echo -e "${BOLD}[5/6] S3 Tables & Glue Catalog${NC}"

if aws s3tables list-table-buckets --region "$REGION" &>/dev/null; then
  pass "S3 Tables API accessible in ${REGION}"
else
  fail "S3 Tables API not accessible. Check region support: https://aws.amazon.com/s3/tables/"
fi

if aws glue get-catalog --name "s3tablescatalog" --region "$REGION" &>/dev/null; then
  pass "Glue federated catalog (s3tablescatalog) registered"
else
  warn "Glue federated catalog not registered. Will be created during demo setup."
  info "Manual: aws glue create-catalog --name s3tablescatalog --catalog-input '{...}'"
fi
echo ""

# =========================================================================
# 6. FSx S3 Access Point (optional)
# =========================================================================
echo -e "${BOLD}[6/6] FSx for ONTAP S3 Access Point${NC}"

if [[ -n "$AP_ALIAS" ]]; then
  if aws s3 ls "s3://${AP_ALIAS}/" --region "$REGION" &>/dev/null; then
    FILE_COUNT=$(aws s3 ls "s3://${AP_ALIAS}/" --region "$REGION" --recursive 2>/dev/null | wc -l | tr -d ' ')
    pass "S3 Access Point accessible: ${AP_ALIAS}"
    info "Files visible: ${FILE_COUNT}"
  else
    fail "Cannot access S3 AP: ${AP_ALIAS}. Check IAM policy and AP configuration."
  fi
else
  info "No --ap-alias specified. Skipping S3 AP check."
  info "For S3-only mode, this is not required."
  info "For full demo, provide: --ap-alias <your-alias-ext-s3alias>"
fi
echo ""

# =========================================================================
# Summary
# =========================================================================
echo -e "${BOLD}═══════════════════════════════════════════════════════════${NC}"
if [[ $CRITICAL_FAIL -eq 0 && $OPTIONAL_FAIL -eq 0 ]]; then
  echo -e "${GREEN}${BOLD} ✅ All prerequisites met! Ready to run the demo.${NC}"
  echo ""
  echo "  Next steps:"
  echo "    S3-only:  See demo/docs/quickstart-s3-only.md"
  echo "    Full:     ./run-demo.sh --ap-alias <your-alias-ext-s3alias>"
  exit 0
elif [[ $CRITICAL_FAIL -eq 0 ]]; then
  echo -e "${YELLOW}${BOLD} ⚠️  Optional items missing (demo will work with limitations)${NC}"
  echo ""
  echo "  You can proceed with the S3-only quickstart."
  echo "  Fix warnings above for the full demo experience."
  exit 2
else
  echo -e "${RED}${BOLD} ❌ Critical prerequisites missing. Fix items above before proceeding.${NC}"
  echo ""
  echo "  Quick fix:"
  echo "    pip install -r requirements.txt"
  echo "    aws configure"
  exit 1
fi

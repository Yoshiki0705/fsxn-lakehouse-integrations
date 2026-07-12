#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# FSx for ONTAP Lakehouse Integrations — Preflight Check
# Validates environment readiness before CloudFormation deployment.
#
# Usage:
#   ./scripts/preflight-check.sh --integration <name> [--region <region>]
#
# Integration names:
#   athena, glue, duckdb, databricks, snowflake, fpolicy,
#   manufacturing, iceberg-catalog, opensharing, all
# ============================================================================

VERSION="1.0.0"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
INTEGRATION="all"
VERBOSE=false
ERRORS=0
WARNINGS=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
  cat <<EOF
FSx for ONTAP Lakehouse — Preflight Check v${VERSION}

Usage: $0 --integration <name> [OPTIONS]

Options:
  --integration, -i   Integration to validate (required)
  --region, -r        AWS region (default: ${REGION})
  --vpc               VPC ID for endpoint checks (duckdb, databricks, fpolicy)
  --verbose, -v       Show detailed output
  --help, -h          Show this help

Integration names:
  athena          Athena + Glue Crawler
  glue            Glue ETL pipeline
  duckdb          DuckDB Lambda (VPC-attached)
  databricks      Databricks Unity Catalog
  snowflake       Snowflake Storage Integration
  fpolicy         FPolicy event-driven pipeline
  manufacturing   Manufacturing Data Platform PoC
  iceberg-catalog Iceberg Metadata Catalog
  opensharing     OpenSharing Volumes Server
  all             Run all checks

Examples:
  $0 --integration athena
  $0 --integration duckdb --vpc vpc-0abc123 --region us-east-1
  $0 --integration all
EOF
  exit 0
}

pass() { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; ((ERRORS++)); }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; ((WARNINGS++)); }
info() { echo -e "  ${BLUE}ℹ${NC} $1"; }
header() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --integration|-i) INTEGRATION="$2"; shift 2 ;;
    --region|-r) REGION="$2"; shift 2 ;;
    --vpc) VPC_ID="$2"; shift 2 ;;
    --verbose|-v) VERBOSE=true; shift ;;
    --help|-h) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

VPC_ID="${VPC_ID:-}"

# ============================================================================
# Core Checks (always run)
# ============================================================================

check_aws_cli() {
  header "AWS CLI & Credentials"

  # Check AWS CLI version
  if command -v aws &>/dev/null; then
    local cli_version
    cli_version=$(aws --version 2>&1 | awk '{print $1}' | cut -d/ -f2)
    local major minor
    major=$(echo "$cli_version" | cut -d. -f1)
    minor=$(echo "$cli_version" | cut -d. -f2)
    if [[ "$major" -ge 2 ]] && [[ "$minor" -ge 15 ]]; then
      pass "AWS CLI v${cli_version} (>= 2.15 required)"
    else
      fail "AWS CLI v${cli_version} — upgrade to >= 2.15.0"
    fi
  else
    fail "AWS CLI not found. Install: https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html"
    return
  fi

  # Check credentials
  if aws sts get-caller-identity --region "$REGION" &>/dev/null; then
    local account_id identity_arn
    account_id=$(aws sts get-caller-identity --query Account --output text --region "$REGION")
    identity_arn=$(aws sts get-caller-identity --query Arn --output text --region "$REGION")
    pass "Authenticated: ${identity_arn}"
    pass "Account: ${account_id}"
  else
    fail "AWS credentials invalid or expired. Run: aws configure"
    return
  fi

  # Check region
  pass "Region: ${REGION}"
}

check_fsxn_environment() {
  header "FSx for ONTAP Environment"

  # Check for ONTAP file systems
  local fs_count
  fs_count=$(aws fsx describe-file-systems \
    --query 'FileSystems[?FileSystemType==`ONTAP`] | length(@)' \
    --output text --region "$REGION" 2>/dev/null || echo "0")

  if [[ "$fs_count" -eq "0" ]]; then
    fail "No FSx for ONTAP file systems found in ${REGION}"
    info "Create one first: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/getting-started.html"
    return
  fi
  pass "Found ${fs_count} FSx for ONTAP file system(s)"

  # Check file system lifecycle
  local fs_available
  fs_available=$(aws fsx describe-file-systems \
    --query 'FileSystems[?FileSystemType==`ONTAP` && Lifecycle==`AVAILABLE`] | length(@)' \
    --output text --region "$REGION" 2>/dev/null || echo "0")

  if [[ "$fs_available" -gt "0" ]]; then
    pass "${fs_available} file system(s) in AVAILABLE state"
  else
    fail "No file systems in AVAILABLE state"
  fi

  # Check SVMs
  local svm_count
  svm_count=$(aws fsx describe-storage-virtual-machines \
    --query 'StorageVirtualMachines | length(@)' \
    --output text --region "$REGION" 2>/dev/null || echo "0")

  if [[ "$svm_count" -gt "0" ]]; then
    pass "Found ${svm_count} SVM(s)"
  else
    fail "No SVMs found. Create one on your FSx for ONTAP file system."
  fi

  # Check S3 Access Points
  local ap_count
  ap_count=$(aws fsx describe-s3-access-point-attachments \
    --query 'S3AccessPointAttachments | length(@)' \
    --output text --region "$REGION" 2>/dev/null || echo "0")

  if [[ "$ap_count" -gt "0" ]]; then
    pass "Found ${ap_count} S3 Access Point attachment(s)"
    # Check if any are AVAILABLE
    local ap_available
    ap_available=$(aws fsx describe-s3-access-point-attachments \
      --query 'S3AccessPointAttachments[?Lifecycle==`AVAILABLE`] | length(@)' \
      --output text --region "$REGION" 2>/dev/null || echo "0")
    if [[ "$ap_available" -gt "0" ]]; then
      pass "${ap_available} S3 AP(s) in AVAILABLE state"
    else
      warn "No S3 APs in AVAILABLE state (may be CREATING or FAILED)"
    fi
  else
    warn "No S3 Access Points found. Create one before deploying integrations."
    info "Command: aws fsx create-and-attach-s3-access-point --name <name> --type ONTAP --ontap-configuration '...'"
  fi
}

# ============================================================================
# Integration-Specific Checks
# ============================================================================

check_vpc_endpoints() {
  header "VPC Endpoints (for: ${1:-VPC-based integration})"

  local vpc_id="${1:-}"
  if [[ -z "$vpc_id" ]]; then
    warn "No VPC ID provided; skipping VPC endpoint checks"
    return
  fi

  # S3 Gateway Endpoint
  local s3_gw
  s3_gw=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=${vpc_id}" "Name=service-name,Values=com.amazonaws.${REGION}.s3" "Name=vpc-endpoint-type,Values=Gateway" \
    --query 'VpcEndpoints | length(@)' \
    --output text --region "$REGION" 2>/dev/null || echo "0")

  if [[ "$s3_gw" -gt "0" ]]; then
    pass "S3 Gateway Endpoint exists"
    warn "S3 Gateway EP may block FSx for ONTAP S3 AP traffic for internet-origin APs"
    info "See docs/en/fsx-ontap-s3ap-networking.md for workarounds"
  else
    info "No S3 Gateway Endpoint (internet-origin S3 AP traffic will use NAT/IGW)"
  fi

  # S3 Interface Endpoint
  local s3_if
  s3_if=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=${vpc_id}" "Name=service-name,Values=com.amazonaws.${REGION}.s3" "Name=vpc-endpoint-type,Values=Interface" \
    --query 'VpcEndpoints | length(@)' \
    --output text --region "$REGION" 2>/dev/null || echo "0")

  if [[ "$s3_if" -gt "0" ]]; then
    pass "S3 Interface Endpoint exists (required for VPC-scoped APs)"
  else
    info "No S3 Interface Endpoint (needed for Databricks VPC-scoped AP)"
  fi

  # SQS Interface Endpoint
  local sqs_if
  sqs_if=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=${vpc_id}" "Name=service-name,Values=com.amazonaws.${REGION}.sqs" \
    --query 'VpcEndpoints | length(@)' \
    --output text --region "$REGION" 2>/dev/null || echo "0")

  if [[ "$sqs_if" -gt "0" ]]; then
    pass "SQS Interface Endpoint exists (required for FPolicy pipeline)"
  else
    info "No SQS Interface Endpoint (needed for FPolicy Fargate in private subnets)"
  fi

  # STS Interface Endpoint
  local sts_if
  sts_if=$(aws ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=${vpc_id}" "Name=service-name,Values=com.amazonaws.${REGION}.sts" \
    --query 'VpcEndpoints | length(@)' \
    --output text --region "$REGION" 2>/dev/null || echo "0")

  if [[ "$sts_if" -gt "0" ]]; then
    pass "STS Interface Endpoint exists"
  else
    info "No STS Interface Endpoint (needed for MSK IAM auth, cross-account)"
  fi
}

check_athena() {
  header "Athena Integration Readiness"
  info "Athena uses internet-origin S3 AP (no VPC required)"
  info "Glue Crawler will auto-discover schema from S3 AP"

  # Check if Athena results bucket exists (user must provide)
  info "Ensure you have an S3 bucket for Athena query results"
  info "Template parameter: AthenaResultsBucket"
  pass "Athena integration: ready (minimal prerequisites)"
}

check_glue() {
  header "Glue ETL Integration Readiness"
  info "Glue ETL uses internet-origin S3 AP"
  info "Requires ETL script bucket with bronze_to_silver.py and silver_to_gold.py"

  # Check if Glue service role limit
  local glue_roles
  glue_roles=$(aws iam list-roles \
    --query 'Roles[?starts_with(RoleName, `fsxn-glue`)] | length(@)' \
    --output text 2>/dev/null || echo "0")

  if [[ "$glue_roles" -lt "5" ]]; then
    pass "IAM role namespace available for Glue"
  else
    warn "Multiple fsxn-glue roles exist; check for conflicts"
  fi
}

check_duckdb() {
  header "DuckDB Lambda Readiness"
  info "DuckDB Lambda requires VPC attachment for VPC-scoped S3 AP"
  warn "Ensure private subnets have NAT Gateway or S3 Interface Endpoint"
  info "Lambda Layer bucket will be auto-created by the template"
  info "build-layer.sh must be run first to upload the DuckDB layer zip to S3"
}

check_databricks() {
  header "Databricks Integration Readiness"
  info "Requires: Databricks Workspace ID + External ID from Storage Credential setup"
  warn "VPC-scoped S3 AP requires S3 Interface Endpoint (created by template)"
  warn "Known limitation: Unity Catalog session policy may not recognize S3 AP ARN"
  info "Fallback: DataSync NFS→S3 task (poc-templates/04-databricks-integration/)"
}

check_snowflake() {
  header "Snowflake Integration Readiness"
  info "Two-phase deployment: Phase 1 (placeholder) → DESCRIBE → Phase 2 (actual trust)"
  info "S3 AP must be internet-origin (no VpcConfiguration) for Snowflake access"
  info "After Phase 1, run in Snowflake:"
  info "  CREATE STORAGE INTEGRATION ... STORAGE_AWS_ROLE_ARN = '<output IAMRoleArn>'"
  info "  DESCRIBE INTEGRATION <name>; -- get STORAGE_AWS_IAM_USER_ARN + EXTERNAL_ID"
}

check_fpolicy() {
  header "FPolicy Pipeline Readiness"
  info "Requires: VPC with private subnets + SQS VPC Endpoint"
  info "Deploy order: fpolicy-routing → fpolicy-ingestion → fpolicy-server → fpolicy-ip-updater"
  warn "ONTAP FPolicy external-engine must be configured after deployment"
  info "ONTAP commands needed post-deploy:"
  info "  fpolicy external-engine create -vserver <svm> -engine-name <name> -primary-servers <fargate-ip>"
  info "  fpolicy policy create ..."
  info "  fpolicy policy scope create ..."
  info "  fpolicy enable -vserver <svm> -policy-name <name>"

  # Check for Secrets Manager secret (ONTAP credentials)
  info "Ensure ONTAP admin credentials are stored in Secrets Manager (JSON: {\"username\":\"fsxadmin\",\"password\":\"...\"})"
}

# ============================================================================
# Main Execution
# ============================================================================

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  FSx for ONTAP Lakehouse — Preflight Check v${VERSION}              ║"
printf "║  Integration: %-49s║\n" "${INTEGRATION}"
printf "║  Region: %-54s║\n" "${REGION}"
echo "╚══════════════════════════════════════════════════════════════════╝"

# Always run core checks
check_aws_cli
check_fsxn_environment

# Integration-specific checks
case "$INTEGRATION" in
  athena)
    check_athena
    ;;
  glue)
    check_glue
    ;;
  duckdb)
    check_duckdb
    [[ -n "$VPC_ID" ]] && check_vpc_endpoints "$VPC_ID"
    ;;
  databricks)
    check_databricks
    [[ -n "$VPC_ID" ]] && check_vpc_endpoints "$VPC_ID"
    ;;
  snowflake)
    check_snowflake
    ;;
  fpolicy)
    check_fpolicy
    [[ -n "$VPC_ID" ]] && check_vpc_endpoints "$VPC_ID"
    ;;
  manufacturing)
    header "Manufacturing PoC Readiness"
    info "Full greenfield deployment (creates VPC, FSx for ONTAP, MSK)"
    info "Deploy order: 01-vpc-network → 02-s3-buckets → 03-fsx-ontap → msk-serverless"
    info "Estimated total deploy time: ~60 minutes (FSx creation dominates)"
    info "Estimated monthly cost: ~$250 (PoC tier)"
    ;;
  iceberg-catalog)
    header "Iceberg Metadata Catalog Readiness"
    info "Requires: Athena results bucket"
    info "S3 Tables is serverless and scale-to-zero ($0 idle cost)"
    ;;
  opensharing)
    header "OpenSharing Server Readiness"
    info "Lambda-based, no VPC required"
    info "S3 AP alias needed as parameter"
    pass "Minimal prerequisites (S3 AP alias only)"
    ;;
  all)
    check_athena
    check_glue
    check_duckdb
    check_databricks
    check_snowflake
    check_fpolicy
    ;;
  *)
    fail "Unknown integration: ${INTEGRATION}"
    echo "Valid options: athena, glue, duckdb, databricks, snowflake, fpolicy, manufacturing, iceberg-catalog, opensharing, all"
    ;;
esac

# Summary
header "Summary"
if [[ "$ERRORS" -eq 0 ]]; then
  echo -e "  ${GREEN}All checks passed.${NC} ${WARNINGS} warning(s)."
  echo ""
  echo "  Next step: Deploy with"
  echo "    aws cloudformation create-stack \\"
  echo "      --stack-name fsxn-${INTEGRATION}-dev \\"
  echo "      --template-body file://<template-path> \\"
  echo "      --parameters file://cfn-params/<integration>.example.json \\"
  echo "      --capabilities CAPABILITY_NAMED_IAM"
  echo ""
  exit 0
else
  echo -e "  ${RED}${ERRORS} error(s)${NC}, ${WARNINGS} warning(s). Fix errors before deploying."
  echo ""
  exit 1
fi

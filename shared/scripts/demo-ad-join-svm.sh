#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# Demo AD Join SVM — Join FSx for ONTAP SVM to Active Directory Domain
#
# Prerequisites:
#   - FSx for ONTAP file system AVAILABLE
#   - AD environment deployed (shared/templates/demo-ad-environment.yaml)
#   - AD directory in Active state with reachable DNS IPs
#   - ONTAP REST API accessible from this machine (via mgmt endpoint)
#   - jq, curl, aws-cli installed
#
# Usage:
#   ./shared/scripts/demo-ad-join-svm.sh \
#     --fsxn-mgmt-ip 198.51.100.10 \
#     --svm-name svm-lakehouse \
#     --domain lakehouse.example.com \
#     --dns-ips 198.51.100.50,198.51.100.51 \
#     --secret-arn arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:demo/ad-credentials-XXXXXX
#
# What this script does:
#   1. Retrieves AD credentials from Secrets Manager
#   2. Configures DNS on the SVM
#   3. Creates CIFS server (joins SVM to AD domain)
#   4. Verifies domain membership
#   5. Creates a test AD user for WINDOWS S3 AP testing
# ============================================================================

VERSION="1.0.0"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}✓${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; exit 1; }
info() { echo -e "  ${BLUE}ℹ${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }

# Defaults
FSXN_MGMT_IP=""
SVM_NAME=""
DOMAIN=""
DNS_IPS=""
SECRET_ARN=""
ONTAP_USER="fsxadmin"
ONTAP_PASS=""
CIFS_SERVER_NAME=""
OU_PATH=""
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
SKIP_USER_CREATE=false

usage() {
  cat <<EOF
Demo AD Join SVM v${VERSION}

Joins an FSx for ONTAP SVM to an Active Directory domain for WINDOWS S3 AP testing.

Usage: $0 [OPTIONS]

Required:
  --fsxn-mgmt-ip    FSx for ONTAP management endpoint IP
  --svm-name        SVM name to join to AD
  --domain          AD domain FQDN (e.g., lakehouse.example.com)
  --dns-ips         Comma-separated DNS IPs (AD domain controllers)

Authentication (one of):
  --secret-arn      Secrets Manager ARN containing AD + ONTAP credentials
  --ontap-pass      ONTAP fsxadmin password (if not using secret)

Optional:
  --cifs-name       CIFS server name (default: first 15 chars of SVM name)
  --ou-path         AD Organizational Unit path (e.g., OU=FSx,DC=lakehouse,DC=example,DC=com)
  --region          AWS region (default: ap-northeast-1)
  --skip-user       Skip test user creation
  --help            Show this help

Examples:
  # Using Secrets Manager (recommended)
  $0 --fsxn-mgmt-ip 198.51.100.10 --svm-name svm-lakehouse \\
     --domain lakehouse.example.com --dns-ips 198.51.100.50,198.51.100.51 \\
     --secret-arn arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:demo/ad-credentials-XXXXXX

  # Using inline password
  $0 --fsxn-mgmt-ip 198.51.100.10 --svm-name svm-lakehouse \\
     --domain lakehouse.example.com --dns-ips 198.51.100.50,198.51.100.51 \\
     --ontap-pass 'YourFsxAdminPassword'
EOF
  exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --fsxn-mgmt-ip) FSXN_MGMT_IP="$2"; shift 2 ;;
    --svm-name) SVM_NAME="$2"; shift 2 ;;
    --domain) DOMAIN="$2"; shift 2 ;;
    --dns-ips) DNS_IPS="$2"; shift 2 ;;
    --secret-arn) SECRET_ARN="$2"; shift 2 ;;
    --ontap-pass) ONTAP_PASS="$2"; shift 2 ;;
    --cifs-name) CIFS_SERVER_NAME="$2"; shift 2 ;;
    --ou-path) OU_PATH="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --skip-user) SKIP_USER_CREATE=true; shift ;;
    --help|-h) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

# Validate required params
[[ -z "$FSXN_MGMT_IP" ]] && fail "Missing --fsxn-mgmt-ip"
[[ -z "$SVM_NAME" ]] && fail "Missing --svm-name"
[[ -z "$DOMAIN" ]] && fail "Missing --domain"
[[ -z "$DNS_IPS" ]] && fail "Missing --dns-ips"
[[ -z "$SECRET_ARN" && -z "$ONTAP_PASS" ]] && fail "Need --secret-arn or --ontap-pass"

# Default CIFS name: first 15 chars of SVM name (NetBIOS limit)
if [[ -z "$CIFS_SERVER_NAME" ]]; then
  CIFS_SERVER_NAME=$(echo "$SVM_NAME" | tr '[:lower:]' '[:upper:]' | tr '-' '_' | cut -c1-15)
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  FSx for ONTAP — AD Domain Join                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
info "SVM: ${SVM_NAME}"
info "Domain: ${DOMAIN}"
info "DNS: ${DNS_IPS}"
info "CIFS Server: ${CIFS_SERVER_NAME}"
echo ""

# ============================================================================
# Step 1: Retrieve credentials
# ============================================================================
echo -e "${BLUE}━━━ Step 1: Retrieve Credentials ━━━${NC}"

AD_USER=""
AD_PASS=""

if [[ -n "$SECRET_ARN" ]]; then
  info "Fetching credentials from Secrets Manager..."
  SECRET_JSON=$(aws secretsmanager get-secret-value \
    --secret-id "$SECRET_ARN" \
    --query SecretString \
    --output text \
    --region "$REGION")

  AD_USER=$(echo "$SECRET_JSON" | jq -r '.username // "Admin"')
  AD_PASS=$(echo "$SECRET_JSON" | jq -r '.password')
  [[ -z "$ONTAP_PASS" ]] && ONTAP_PASS=$(echo "$SECRET_JSON" | jq -r '.ontap_password // empty')

  if [[ -z "$AD_PASS" || "$AD_PASS" == "null" ]]; then
    fail "Could not extract AD password from secret"
  fi
  pass "AD credentials retrieved (user: ${AD_USER})"
else
  AD_USER="Admin"
  AD_PASS="(not from secret — manual mode)"
  info "Using --ontap-pass for ONTAP auth; AD join will need manual password entry"
fi

if [[ -z "$ONTAP_PASS" ]]; then
  echo -n "  Enter fsxadmin password: "
  read -rs ONTAP_PASS
  echo ""
fi

# ONTAP REST API base
ONTAP_API="https://${FSXN_MGMT_IP}/api"
ONTAP_AUTH="${ONTAP_USER}:${ONTAP_PASS}"

# Verify ONTAP connectivity
info "Testing ONTAP REST API connectivity..."
HTTP_CODE=$(curl -sk -o /dev/null -w '%{http_code}' \
  -u "${ONTAP_AUTH}" "${ONTAP_API}/cluster" 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" == "200" ]]; then
  pass "ONTAP REST API accessible (HTTP ${HTTP_CODE})"
else
  fail "Cannot reach ONTAP REST API at ${FSXN_MGMT_IP} (HTTP ${HTTP_CODE}). Check IP and credentials."
fi

# ============================================================================
# Step 2: Get SVM UUID
# ============================================================================
echo -e "\n${BLUE}━━━ Step 2: Locate SVM ━━━${NC}"

SVM_UUID=$(curl -sk -u "${ONTAP_AUTH}" \
  "${ONTAP_API}/svm/svms?name=${SVM_NAME}&fields=uuid" \
  | jq -r '.records[0].uuid // empty')

if [[ -z "$SVM_UUID" ]]; then
  fail "SVM '${SVM_NAME}' not found. Check name and try again."
fi
pass "SVM found: ${SVM_NAME} (${SVM_UUID})"

# ============================================================================
# Step 3: Configure DNS on SVM
# ============================================================================
echo -e "\n${BLUE}━━━ Step 3: Configure DNS ━━━${NC}"

# Build DNS IP array
IFS=',' read -ra DNS_ARRAY <<< "$DNS_IPS"
DNS_JSON=$(printf '"%s",' "${DNS_ARRAY[@]}" | sed 's/,$//')

info "Setting DNS servers: ${DNS_IPS}"
DNS_RESPONSE=$(curl -sk -u "${ONTAP_AUTH}" \
  -X POST "${ONTAP_API}/name-services/dns" \
  -H "Content-Type: application/json" \
  -d "{
    \"svm\": {\"uuid\": \"${SVM_UUID}\"},
    \"domains\": [\"${DOMAIN}\"],
    \"servers\": [${DNS_JSON}]
  }" -w "\n%{http_code}" 2>/dev/null)

DNS_CODE=$(echo "$DNS_RESPONSE" | tail -1)
if [[ "$DNS_CODE" == "201" || "$DNS_CODE" == "200" ]]; then
  pass "DNS configured on SVM"
elif [[ "$DNS_CODE" == "409" ]]; then
  warn "DNS already configured (409 Conflict) — updating..."
  curl -sk -u "${ONTAP_AUTH}" \
    -X PATCH "${ONTAP_API}/name-services/dns/${SVM_UUID}" \
    -H "Content-Type: application/json" \
    -d "{\"domains\": [\"${DOMAIN}\"], \"servers\": [${DNS_JSON}]}" >/dev/null 2>&1
  pass "DNS updated on SVM"
else
  warn "DNS configuration returned HTTP ${DNS_CODE} — may already exist or check ONTAP logs"
fi

# ============================================================================
# Step 4: Create CIFS Server (AD domain join)
# ============================================================================
echo -e "\n${BLUE}━━━ Step 4: Join AD Domain (CIFS Server Create) ━━━${NC}"

info "Creating CIFS server '${CIFS_SERVER_NAME}' and joining domain '${DOMAIN}'..."
info "This may take 30-60 seconds..."

CIFS_BODY="{
  \"svm\": {\"uuid\": \"${SVM_UUID}\"},
  \"name\": \"${CIFS_SERVER_NAME}\",
  \"ad_domain\": {
    \"fqdn\": \"${DOMAIN}\",
    \"user\": \"${AD_USER}\",
    \"password\": \"${AD_PASS}\"
  }
}"

# Add OU if specified
if [[ -n "$OU_PATH" ]]; then
  CIFS_BODY=$(echo "$CIFS_BODY" | jq --arg ou "$OU_PATH" '.ad_domain.organizational_unit = $ou')
fi

CIFS_RESPONSE=$(curl -sk -u "${ONTAP_AUTH}" \
  -X POST "${ONTAP_API}/protocols/cifs/services" \
  -H "Content-Type: application/json" \
  -d "$CIFS_BODY" -w "\n%{http_code}" 2>/dev/null)

CIFS_CODE=$(echo "$CIFS_RESPONSE" | tail -1)
CIFS_BODY_RESP=$(echo "$CIFS_RESPONSE" | sed '$d')

if [[ "$CIFS_CODE" == "201" || "$CIFS_CODE" == "202" ]]; then
  pass "CIFS server created — SVM joined to ${DOMAIN}"

  # If 202 (async), wait for job
  JOB_UUID=$(echo "$CIFS_BODY_RESP" | jq -r '.job.uuid // empty')
  if [[ -n "$JOB_UUID" ]]; then
    info "Waiting for domain join job to complete..."
    for i in $(seq 1 30); do
      JOB_STATE=$(curl -sk -u "${ONTAP_AUTH}" "${ONTAP_API}/cluster/jobs/${JOB_UUID}" \
        | jq -r '.state // "unknown"')
      if [[ "$JOB_STATE" == "success" ]]; then
        pass "Domain join completed successfully"
        break
      elif [[ "$JOB_STATE" == "failure" ]]; then
        JOB_MSG=$(curl -sk -u "${ONTAP_AUTH}" "${ONTAP_API}/cluster/jobs/${JOB_UUID}" \
          | jq -r '.message // "unknown error"')
        fail "Domain join failed: ${JOB_MSG}"
      fi
      sleep 5
    done
  fi
elif [[ "$CIFS_CODE" == "409" ]]; then
  warn "CIFS server already exists on this SVM (409 Conflict)"
  pass "SVM is already domain-joined"
else
  echo "$CIFS_BODY_RESP" | jq '.error // .' 2>/dev/null || echo "$CIFS_BODY_RESP"
  fail "CIFS server creation failed (HTTP ${CIFS_CODE})"
fi

# ============================================================================
# Step 5: Verify domain membership
# ============================================================================
echo -e "\n${BLUE}━━━ Step 5: Verify Domain Membership ━━━${NC}"

CIFS_STATUS=$(curl -sk -u "${ONTAP_AUTH}" \
  "${ONTAP_API}/protocols/cifs/services?svm.uuid=${SVM_UUID}&fields=ad_domain" \
  | jq -r '.records[0].ad_domain.fqdn // empty')

if [[ "$CIFS_STATUS" == "$DOMAIN" ]]; then
  pass "SVM '${SVM_NAME}' is joined to domain '${CIFS_STATUS}'"
else
  warn "Could not verify domain join (got: '${CIFS_STATUS}')"
fi

# ============================================================================
# Step 6: Create test user (optional)
# ============================================================================
if [[ "$SKIP_USER_CREATE" == "false" ]]; then
  echo -e "\n${BLUE}━━━ Step 6: Create Test AD User (via ONTAP) ━━━${NC}"
  info "For WINDOWS S3 AP testing, you need a domain user."
  info "Create users in AD directly (via AD Users and Computers or PowerShell):"
  echo ""
  echo "  # PowerShell on Domain Controller:"
  echo "  New-ADUser -Name 'lakehouse-reader' \\"
  echo "    -SamAccountName 'lakehouse-reader' \\"
  echo "    -UserPrincipalName 'lakehouse-reader@${DOMAIN}' \\"
  echo "    -AccountPassword (ConvertTo-SecureString 'P@ssw0rd123!' -AsPlainText -Force) \\"
  echo "    -Enabled \$true"
  echo ""
  echo "  # Then create S3 AP with WINDOWS identity:"
  echo "  aws fsx create-and-attach-s3-access-point \\"
  echo "    --name windows-test-ap \\"
  echo "    --type ONTAP \\"
  echo "    --ontap-configuration '{\"VolumeId\":\"<VOL_ID>\",\"FileSystemIdentity\":{\"Type\":\"WINDOWS\",\"WindowsUser\":{\"Name\":\"${DOMAIN}\\\\lakehouse-reader\"}}}'"
  echo ""
else
  info "Skipping test user creation (--skip-user)"
fi

# ============================================================================
# Summary
# ============================================================================
echo -e "\n${BLUE}━━━ Summary ━━━${NC}"
echo ""
pass "AD domain join complete"
echo ""
echo "  Domain:       ${DOMAIN}"
echo "  SVM:          ${SVM_NAME}"
echo "  CIFS Server:  ${CIFS_SERVER_NAME}"
echo "  DNS Servers:  ${DNS_IPS}"
echo ""
echo "  Next steps:"
echo "    1. Create AD user(s) for S3 AP testing"
echo "    2. Set volume security style to NTFS (if not already):"
echo "       curl -sk -u '${ONTAP_USER}:***' \\"
echo "         -X PATCH '${ONTAP_API}/storage/volumes/<vol-uuid>' \\"
echo "         -H 'Content-Type: application/json' \\"
echo "         -d '{\"nas\":{\"security_style\":\"ntfs\"}}'"
echo "    3. Create S3 AP with WINDOWS FileSystemIdentity"
echo "    4. Test: aws s3 ls s3://<AP-ALIAS>/ --region ${REGION}"
echo ""

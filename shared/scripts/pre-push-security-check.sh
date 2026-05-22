#!/bin/bash
# =============================================================================
# Pre-Push Security Check
# =============================================================================
# Scans tracked files for accidentally committed secrets, real AWS account IDs,
# personal file paths, and other sensitive data.
#
# Usage:
#   bash shared/scripts/pre-push-security-check.sh
#
# Environment Variables:
#   SECURITY_CHECK_ACCOUNT_ID  - Your AWS account ID to search for (optional)
#   SECURITY_CHECK_STRICT      - Set to "true" for strict mode (exit on first fail)
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAIL_COUNT=0
WARN_COUNT=0

pass() {
  echo -e "  ${GREEN}✓ PASS${NC}: $1"
}

fail() {
  echo -e "  ${RED}✗ FAIL${NC}: $1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
  if [[ "${SECURITY_CHECK_STRICT:-false}" == "true" ]]; then
    exit 1
  fi
}

warn() {
  echo -e "  ${YELLOW}⚠ WARN${NC}: $1"
  WARN_COUNT=$((WARN_COUNT + 1))
}

echo "============================================="
echo " Security & Privacy Pre-Push Check"
echo "============================================="
echo ""

# -----------------------------------------------
# Check 1: .kiro/ not tracked
# -----------------------------------------------
echo "📁 Check 1: .kiro/ directory not tracked"
KIRO_FILES=$(git ls-files .kiro/ 2>/dev/null || true)
if [[ -z "$KIRO_FILES" ]]; then
  pass ".kiro/ is not tracked"
else
  fail ".kiro/ files are tracked: $KIRO_FILES"
fi

# -----------------------------------------------
# Check 2: .env files not tracked
# -----------------------------------------------
echo "📁 Check 2: .env files not tracked"
ENV_FILES=$(git ls-files '*.env' '.env' '.env.*' '.env.local' 2>/dev/null || true)
if [[ -z "$ENV_FILES" ]]; then
  pass "No .env files tracked"
else
  fail ".env files are tracked: $ENV_FILES"
fi

# -----------------------------------------------
# Check 3: .pem files not tracked
# -----------------------------------------------
echo "📁 Check 3: .pem files not tracked"
PEM_FILES=$(git ls-files -- '*.pem' 2>/dev/null || true)
if [[ -z "$PEM_FILES" ]]; then
  pass "No .pem files tracked"
else
  fail ".pem files are tracked: $PEM_FILES"
fi

# -----------------------------------------------
# Check 4: .private/ directories not tracked
# -----------------------------------------------
echo "📁 Check 4: .private/ directories not tracked"
PRIVATE_FILES=$(git ls-files -- '*/.private/*' '.private/*' 2>/dev/null || true)
if [[ -z "$PRIVATE_FILES" ]]; then
  pass "No .private/ files tracked"
else
  fail ".private/ files are tracked: $PRIVATE_FILES"
fi

# -----------------------------------------------
# Check 5: No personal file paths
# -----------------------------------------------
echo "🔍 Check 5: No personal file paths (/Users/*/Downloads, /home/*/)"
PERSONAL_PATHS=$(git ls-files | xargs grep -rln '/Users/.*/Downloads\|/Users/.*/\.ssh\|/home/.*/\.ssh' 2>/dev/null || true)
if [[ -z "$PERSONAL_PATHS" ]]; then
  pass "No personal file paths found"
else
  fail "Personal file paths found in: $PERSONAL_PATHS"
fi

# -----------------------------------------------
# Check 6: No real AWS Account ID (if provided)
# -----------------------------------------------
echo "🔍 Check 6: No real AWS Account ID"
if [[ -n "${SECURITY_CHECK_ACCOUNT_ID:-}" ]]; then
  ACCOUNT_HITS=$(git ls-files | xargs grep -rln "${SECURITY_CHECK_ACCOUNT_ID}" 2>/dev/null || true)
  if [[ -z "$ACCOUNT_HITS" ]]; then
    pass "Account ID ${SECURITY_CHECK_ACCOUNT_ID:0:4}****${SECURITY_CHECK_ACCOUNT_ID: -4} not found"
  else
    fail "Real AWS Account ID found in: $ACCOUNT_HITS"
  fi
else
  warn "SECURITY_CHECK_ACCOUNT_ID not set, skipping account ID check"
fi

# -----------------------------------------------
# Check 7: No IAM access keys
# -----------------------------------------------
echo "🔍 Check 7: No IAM access keys (AKIA...)"
ACCESS_KEY_HITS=$(git ls-files | xargs grep -rln 'AKIA[0-9A-Z]\{16\}' 2>/dev/null || true)
if [[ -z "$ACCESS_KEY_HITS" ]]; then
  pass "No IAM access keys found"
else
  fail "IAM access keys found in: $ACCESS_KEY_HITS"
fi

# -----------------------------------------------
# Check 8: No hardcoded real IP addresses
# -----------------------------------------------
echo "🔍 Check 8: No hardcoded real IP addresses (non-RFC1918, non-example)"
# Exclude 10.x.x.x, 172.16-31.x.x, 192.168.x.x, 127.x.x.x, 0.0.0.0, and version numbers
REAL_IP_HITS=$(git ls-files | xargs grep -rn '[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}\.[0-9]\{1,3\}' 2>/dev/null \
  | grep -v '10\.\|172\.1[6-9]\.\|172\.2[0-9]\.\|172\.3[01]\.\|192\.168\.\|127\.\|0\.0\.0\.0' \
  | grep -v '\.example\.\|version\|v[0-9]\|[0-9]\.[0-9]\.[0-9]' \
  | grep -v '\.md:.*example\|\.md:.*placeholder' \
  || true)
if [[ -z "$REAL_IP_HITS" ]]; then
  pass "No suspicious real IP addresses found"
else
  warn "Potential real IP addresses found (review manually):"
  echo "$REAL_IP_HITS" | head -5
fi

# -----------------------------------------------
# Check 9: No .pem path references in scripts
# -----------------------------------------------
echo "🔍 Check 9: No .pem path references in scripts"
PEM_REF_HITS=$(git ls-files -- '*.sh' '*.py' '*.yaml' '*.yml' | xargs grep -rln '\.pem' 2>/dev/null \
  | grep -v 'example\|template\|\.gitignore\|security-check' || true)
if [[ -z "$PEM_REF_HITS" ]]; then
  pass "No .pem path references in scripts"
else
  warn "Files referencing .pem (verify they use placeholders): $PEM_REF_HITS"
fi

# -----------------------------------------------
# Summary
# -----------------------------------------------
echo ""
echo "============================================="
if [[ $FAIL_COUNT -eq 0 ]]; then
  echo -e " ${GREEN}ALL CHECKS PASSED${NC} (${WARN_COUNT} warnings)"
  echo "============================================="
  exit 0
else
  echo -e " ${RED}${FAIL_COUNT} CHECK(S) FAILED${NC} (${WARN_COUNT} warnings)"
  echo "============================================="
  echo ""
  echo "Fix the issues above before pushing."
  exit 1
fi

#!/bin/bash
set -euo pipefail

# FSx for ONTAP S3 Access Points — Connectivity Validation
# Usage: ./validate.sh --ap-alias <your-ap-alias-ext-s3alias>

AP_ALIAS=""
REGION="${AWS_REGION:-ap-northeast-1}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --ap-alias) AP_ALIAS="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --help) echo "Usage: ./validate.sh --ap-alias <alias> [--region <region>]"; exit 0 ;;
    *) shift ;;
  esac
done

if [ -z "${AP_ALIAS}" ]; then
  echo "Error: --ap-alias is required"
  echo "Usage: ./validate.sh --ap-alias <your-ap-alias-ext-s3alias>"
  exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  FSx for ONTAP S3 AP — Connectivity Validation              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "AP Alias: ${AP_ALIAS}"
echo "Region:   ${REGION}"
echo ""

PASS=0
FAIL=0

# Test 1: ListObjectsV2
echo "━━━ Test 1: ListObjectsV2 ━━━"
if aws s3api list-objects-v2 --bucket "${AP_ALIAS}" --max-keys 5 --region "${REGION}" > /tmp/poc-list-result.json 2>&1; then
  COUNT=$(jq '.KeyCount // 0' /tmp/poc-list-result.json)
  STORAGE=$(jq -r '.Contents[0].StorageClass // "N/A"' /tmp/poc-list-result.json)
  echo "  ✅ PASS — ${COUNT} objects found, StorageClass: ${STORAGE}"
  PASS=$((PASS + 1))
else
  echo "  ❌ FAIL — ListObjectsV2 failed"
  cat /tmp/poc-list-result.json
  FAIL=$((FAIL + 1))
fi
echo ""

# Test 2: HeadObject (first file)
echo "━━━ Test 2: HeadObject ━━━"
FIRST_KEY=$(jq -r '.Contents[0].Key // empty' /tmp/poc-list-result.json)
if [ -n "${FIRST_KEY}" ]; then
  if aws s3api head-object --bucket "${AP_ALIAS}" --key "${FIRST_KEY}" --region "${REGION}" > /tmp/poc-head-result.json 2>&1; then
    SIZE=$(jq '.ContentLength' /tmp/poc-head-result.json)
    echo "  ✅ PASS — ${FIRST_KEY} (${SIZE} bytes)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ FAIL — HeadObject failed for ${FIRST_KEY}"
    FAIL=$((FAIL + 1))
  fi
else
  echo "  ⚠️ SKIP — No objects found to test HeadObject"
fi
echo ""

# Test 3: GetObject (download first file)
echo "━━━ Test 3: GetObject ━━━"
if [ -n "${FIRST_KEY}" ]; then
  START=$(date +%s%N)
  if aws s3api get-object --bucket "${AP_ALIAS}" --key "${FIRST_KEY}" --region "${REGION}" /tmp/poc-get-result > /dev/null 2>&1; then
    END=$(date +%s%N)
    LATENCY=$(( (END - START) / 1000000 ))
    echo "  ✅ PASS — GetObject succeeded (${LATENCY}ms)"
    PASS=$((PASS + 1))
  else
    echo "  ❌ FAIL — GetObject failed"
    FAIL=$((FAIL + 1))
  fi
else
  echo "  ⚠️ SKIP — No objects found to test GetObject"
fi
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════════"
echo "Results: ${PASS} PASS, ${FAIL} FAIL"
if [ ${FAIL} -eq 0 ]; then
  echo "✅ All tests passed — S3 AP connectivity validated"
  echo ""
  echo "Next: Run your first Athena query:"
  echo "  ../02-athena-quickstart/run-first-query.sh --ap-alias ${AP_ALIAS}"
else
  echo "❌ Some tests failed — check IAM policy, AP policy, and file system permissions"
  echo ""
  echo "Troubleshooting:"
  echo "  1. Verify AP lifecycle: aws fsx describe-s3-access-point-attachments --region ${REGION}"
  echo "  2. Check IAM role has s3:GetObject + s3:ListBucket on AP ARN"
  echo "  3. Check AP resource policy allows your IAM principal"
  echo "  4. Check file system user has read permission on target files"
fi
echo "═══════════════════════════════════════════════════════════════"

# Cleanup
rm -f /tmp/poc-list-result.json /tmp/poc-head-result.json /tmp/poc-get-result

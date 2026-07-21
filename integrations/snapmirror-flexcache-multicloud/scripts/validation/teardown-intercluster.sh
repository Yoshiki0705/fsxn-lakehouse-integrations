#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# FSx for ONTAP S3 AP + SnapMirror/FlexCache — Inter-Cluster Teardown
#
# Reverse of setup-intercluster.sh. Removes:
#   1. FlexCache relationship and Cache Volume
#   2. SnapMirror relationship (release + delete)
#   3. DP Volume on destination
#   4. SVM Peering
#   5. Cluster Peering
#   6. S3 Access Point (detach)
#
# The source volume and CloudFormation stack are handled separately:
#   aws cloudformation delete-stack --stack-name fsxn-snapmirror-flexcache-val
#
# Usage:
#   ./teardown-intercluster.sh \
#     --source-fs fs-0EXAMPLE \
#     --dest-fs fs-0EXAMPLE \
#     --source-secret arn:aws:secretsmanager:... \
#     --dest-secret arn:aws:secretsmanager:...
# ============================================================================

REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
SOURCE_FS=""
DEST_FS=""
SOURCE_SECRET=""
DEST_SECRET=""
SOURCE_SVM_NAME="${SOURCE_SVM_NAME:-svm-source}"
DEST_SVM_NAME="${DEST_SVM_NAME:-svm-dest}"
SOURCE_VOL_NAME="${SOURCE_VOL_NAME:-vol_s3ap_snapmirror_src}"
DEST_VOL_NAME="${DEST_VOL_NAME:-vol_s3ap_snapmirror_dst}"
FLEXCACHE_VOL_NAME="${FLEXCACHE_VOL_NAME:-vol_flexcache_cross}"
S3AP_NAME="${S3AP_NAME:-fsxn-snapmirror-val-src}"
DRY_RUN=false
FORCE=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
pass() { echo -e "${GREEN}[DONE]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

while [[ $# -gt 0 ]]; do
  case $1 in
    --source-fs) SOURCE_FS="$2"; shift 2 ;;
    --dest-fs) DEST_FS="$2"; shift 2 ;;
    --source-secret) SOURCE_SECRET="$2"; shift 2 ;;
    --dest-secret) DEST_SECRET="$2"; shift 2 ;;
    --source-svm) SOURCE_SVM_NAME="$2"; shift 2 ;;
    --dest-svm) DEST_SVM_NAME="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --force) FORCE=true; shift ;;
    --help|-h)
      echo "Usage: $0 --source-fs <id> --dest-fs <id> --source-secret <arn> --dest-secret <arn> [--force] [--dry-run]"
      exit 0 ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

[[ -z "$SOURCE_FS" ]] && fail "--source-fs required"
[[ -z "$DEST_FS" ]] && fail "--dest-fs required"
[[ -z "$SOURCE_SECRET" ]] && fail "--source-secret required"
[[ -z "$DEST_SECRET" ]] && fail "--dest-secret required"

if [[ "$FORCE" != "true" ]]; then
  echo -e "${YELLOW}WARNING: This will destroy all inter-cluster test resources.${NC}"
  echo -e "  - FlexCache: ${FLEXCACHE_VOL_NAME}"
  echo -e "  - SnapMirror: ${SOURCE_SVM_NAME}:${SOURCE_VOL_NAME} → ${DEST_SVM_NAME}:${DEST_VOL_NAME}"
  echo -e "  - DP Volume: ${DEST_VOL_NAME}"
  echo -e "  - SVM/Cluster Peering"
  read -rp "Continue? (yes/no): " CONFIRM
  [[ "$CONFIRM" != "yes" ]] && { echo "Aborted."; exit 0; }
fi

# --- Helpers (same as setup) ---
get_mgmt_ip() {
  aws fsx describe-file-systems --file-system-ids "$1" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
    --output text --region "$REGION"
}

get_credentials() {
  aws secretsmanager get-secret-value --secret-id "$1" \
    --query 'SecretString' --output text --region "$REGION"
}

ontap_api() {
  local mgmt_ip="$1" method="$2" endpoint="$3" user="$4" pass="$5" body="${6:-}"
  local args=(-s -k -X "$method" -u "${user}:${pass}" -H "Content-Type: application/json")
  [[ -n "$body" ]] && args+=(-d "$body")
  if [[ "$DRY_RUN" == "true" ]]; then
    info "[DRY-RUN] ${method} https://${mgmt_ip}/api${endpoint}"
    echo '{"dry_run":true}'
    return 0
  fi
  curl "${args[@]}" "https://${mgmt_ip}/api${endpoint}"
}

# --- Resolve ---
SOURCE_MGMT=$(get_mgmt_ip "$SOURCE_FS")
DEST_MGMT=$(get_mgmt_ip "$DEST_FS")
SOURCE_CREDS=$(get_credentials "$SOURCE_SECRET")
SOURCE_USER=$(echo "$SOURCE_CREDS" | jq -r '.username')
SOURCE_PASS=$(echo "$SOURCE_CREDS" | jq -r '.password')
DEST_CREDS=$(get_credentials "$DEST_SECRET")
DEST_USER=$(echo "$DEST_CREDS" | jq -r '.username')
DEST_PASS=$(echo "$DEST_CREDS" | jq -r '.password')

# --- 1. Delete FlexCache ---
info "=== Deleting FlexCache: ${FLEXCACHE_VOL_NAME} ==="
FC_UUID=$(ontap_api "$DEST_MGMT" GET "/storage/volumes?name=${FLEXCACHE_VOL_NAME}&svm.name=${DEST_SVM_NAME}" "$DEST_USER" "$DEST_PASS" | \
  jq -r '.records[0].uuid // empty')
if [[ -n "$FC_UUID" ]]; then
  ontap_api "$DEST_MGMT" DELETE "/storage/volumes/${FC_UUID}" "$DEST_USER" "$DEST_PASS" > /dev/null
  pass "FlexCache deleted"
else
  warn "FlexCache not found, skipping"
fi

# --- 2. Delete SnapMirror relationship ---
info "=== Releasing SnapMirror ==="
SM_UUID=$(ontap_api "$DEST_MGMT" GET "/snapmirror/relationships?destination.path=${DEST_SVM_NAME}:${DEST_VOL_NAME}" "$DEST_USER" "$DEST_PASS" | \
  jq -r '.records[0].uuid // empty')
if [[ -n "$SM_UUID" ]]; then
  # Break if mirrored
  ontap_api "$DEST_MGMT" PATCH "/snapmirror/relationships/${SM_UUID}" "$DEST_USER" "$DEST_PASS" '{"state":"broken_off"}' > /dev/null 2>&1 || true
  sleep 5
  # Delete relationship
  ontap_api "$DEST_MGMT" DELETE "/snapmirror/relationships/${SM_UUID}?destination_only=true" "$DEST_USER" "$DEST_PASS" > /dev/null
  sleep 5
  # Release on source
  ontap_api "$SOURCE_MGMT" DELETE "/snapmirror/relationships/${SM_UUID}?source_only=true" "$SOURCE_USER" "$SOURCE_PASS" > /dev/null 2>&1 || true
  pass "SnapMirror relationship deleted"
else
  warn "SnapMirror relationship not found, skipping"
fi

# --- 3. Delete DP Volume ---
info "=== Deleting DP volume: ${DEST_VOL_NAME} ==="
DP_UUID=$(ontap_api "$DEST_MGMT" GET "/storage/volumes?name=${DEST_VOL_NAME}&svm.name=${DEST_SVM_NAME}" "$DEST_USER" "$DEST_PASS" | \
  jq -r '.records[0].uuid // empty')
if [[ -n "$DP_UUID" ]]; then
  ontap_api "$DEST_MGMT" DELETE "/storage/volumes/${DP_UUID}" "$DEST_USER" "$DEST_PASS" > /dev/null
  pass "DP volume deleted"
else
  warn "DP volume not found, skipping"
fi

# --- 4. Delete SVM Peering ---
info "=== Deleting SVM Peering ==="
SVM_PEER_UUID=$(ontap_api "$SOURCE_MGMT" GET "/svm/peers" "$SOURCE_USER" "$SOURCE_PASS" | \
  jq -r '.records[0].uuid // empty')
if [[ -n "$SVM_PEER_UUID" ]]; then
  ontap_api "$SOURCE_MGMT" DELETE "/svm/peers/${SVM_PEER_UUID}" "$SOURCE_USER" "$SOURCE_PASS" > /dev/null
  pass "SVM Peering deleted"
else
  warn "SVM Peering not found, skipping"
fi

# --- 5. Delete Cluster Peering ---
info "=== Deleting Cluster Peering ==="
CLUSTER_PEER_UUID=$(ontap_api "$SOURCE_MGMT" GET "/cluster/peers" "$SOURCE_USER" "$SOURCE_PASS" | \
  jq -r '.records[0].uuid // empty')
if [[ -n "$CLUSTER_PEER_UUID" ]]; then
  ontap_api "$SOURCE_MGMT" DELETE "/cluster/peers/${CLUSTER_PEER_UUID}" "$SOURCE_USER" "$SOURCE_PASS" > /dev/null
  pass "Cluster Peering deleted"
else
  warn "Cluster Peering not found, skipping"
fi

# --- 6. Detach S3 AP ---
info "=== Detaching S3 Access Point (via AWS CLI) ==="
# S3 AP detach requires the association ID from FSx API
# This is handled by CloudFormation stack deletion (SourceVolume resource)
info "S3 AP will be removed when CloudFormation stack is deleted."
info "Or detach manually: aws fsx delete-data-repository-association --association-id <id>"

echo ""
info "=============================================="
info "  Teardown Complete"
info "=============================================="
info ""
info "  Final step: delete CloudFormation stack"
info "  aws cloudformation delete-stack --stack-name fsxn-snapmirror-flexcache-val"
echo ""

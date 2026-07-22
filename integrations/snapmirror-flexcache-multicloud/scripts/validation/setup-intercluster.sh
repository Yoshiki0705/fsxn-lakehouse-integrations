#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# FSx for ONTAP S3 AP + SnapMirror/FlexCache — Inter-Cluster Setup
#
# Performs ONTAP-layer operations that cannot be expressed in CloudFormation:
#   1. Cluster Peering
#   2. SVM Peering
#   3. SnapMirror relationship creation (DP volume + initialize)
#   4. FlexCache creation (cross-cluster)
#
# Prerequisites:
#   - CloudFormation stack deployed (template.yaml)
#   - Source volume exists with S3 AP attached
#   - Test data written via S3 AP
#   - jq, aws CLI installed
#
# Usage:
#   ./setup-intercluster.sh \
#     --source-fs fs-0EXAMPLE \
#     --dest-fs fs-0EXAMPLE \
#     --source-secret arn:aws:secretsmanager:... \
#     --dest-secret arn:aws:secretsmanager:...
#
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"

# --- Defaults (override via CLI args or env) ---
SOURCE_FS=""
DEST_FS=""
SOURCE_SECRET=""
DEST_SECRET=""
SOURCE_SVM_NAME="${SOURCE_SVM_NAME:-svm-source}"
DEST_SVM_NAME="${DEST_SVM_NAME:-svm-dest}"
SOURCE_VOL_NAME="${SOURCE_VOL_NAME:-vol_s3ap_snapmirror_src}"
DEST_VOL_NAME="${DEST_VOL_NAME:-vol_s3ap_snapmirror_dst}"
DEST_VOL_SIZE_MB="${DEST_VOL_SIZE_MB:-10240}"
FLEXCACHE_VOL_NAME="${FLEXCACHE_VOL_NAME:-vol_flexcache_cross}"
FLEXCACHE_SIZE_MB="${FLEXCACHE_SIZE_MB:-5120}"
DRY_RUN=false

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }

usage() {
  cat <<EOF
Usage: $0 --source-fs <id> --dest-fs <id> --source-secret <arn> --dest-secret <arn> [OPTIONS]

Required:
  --source-fs         Source FSx for ONTAP File System ID
  --dest-fs           Destination FSx for ONTAP File System ID
  --source-secret     Source cluster Secrets Manager ARN
  --dest-secret       Destination cluster Secrets Manager ARN

Optional:
  --source-svm        Source SVM name (default: svm-source)
  --dest-svm          Destination SVM name (default: svm-dest)
  --source-vol        Source volume name (default: vol_s3ap_snapmirror_src)
  --dest-vol          Destination volume name (default: vol_s3ap_snapmirror_dst)
  --region            AWS region (default: ap-northeast-1)
  --dry-run           Print commands without executing
  --help              Show this help
EOF
  exit 0
}

# --- Parse Args ---
while [[ $# -gt 0 ]]; do
  case $1 in
    --source-fs) SOURCE_FS="$2"; shift 2 ;;
    --dest-fs) DEST_FS="$2"; shift 2 ;;
    --source-secret) SOURCE_SECRET="$2"; shift 2 ;;
    --dest-secret) DEST_SECRET="$2"; shift 2 ;;
    --source-svm) SOURCE_SVM_NAME="$2"; shift 2 ;;
    --dest-svm) DEST_SVM_NAME="$2"; shift 2 ;;
    --source-vol) SOURCE_VOL_NAME="$2"; shift 2 ;;
    --dest-vol) DEST_VOL_NAME="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help|-h) usage ;;
    *) echo "Unknown: $1"; usage ;;
  esac
done

[[ -z "$SOURCE_FS" ]] && fail "--source-fs is required"
[[ -z "$DEST_FS" ]] && fail "--dest-fs is required"
[[ -z "$SOURCE_SECRET" ]] && fail "--source-secret is required"
[[ -z "$DEST_SECRET" ]] && fail "--dest-secret is required"

# ============================================================================
# Helper: Get ONTAP Management Endpoint
# ============================================================================
get_mgmt_ip() {
  local fs_id="$1"
  aws fsx describe-file-systems \
    --file-system-ids "$fs_id" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' \
    --output text --region "$REGION"
}

# ============================================================================
# Helper: Get credentials from Secrets Manager
# ============================================================================
get_credentials() {
  local secret_arn="$1"
  aws secretsmanager get-secret-value \
    --secret-id "$secret_arn" \
    --query 'SecretString' \
    --output text --region "$REGION"
}

# ============================================================================
# Helper: ONTAP REST API call
# ============================================================================
ontap_api() {
  local mgmt_ip="$1"
  local method="$2"
  local endpoint="$3"
  local username="$4"
  local password="$5"
  local body="${6:-}"

  local url="https://${mgmt_ip}/api${endpoint}"
  local args=(-s -k -X "$method" -u "${username}:${password}" -H "Content-Type: application/json")

  if [[ -n "$body" ]]; then
    args+=(-d "$body")
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    info "[DRY-RUN] curl ${method} ${url}"
    [[ -n "$body" ]] && info "  Body: ${body}"
    echo '{"dry_run": true}'
    return 0
  fi

  curl "${args[@]}" "$url"
}

# ============================================================================
# STEP 0: Resolve Management IPs and Credentials
# ============================================================================
info "=== Step 0: Resolving cluster management endpoints ==="

SOURCE_MGMT=$(get_mgmt_ip "$SOURCE_FS")
DEST_MGMT=$(get_mgmt_ip "$DEST_FS")
info "Source management IP: ${SOURCE_MGMT}"
info "Destination management IP: ${DEST_MGMT}"

SOURCE_CREDS=$(get_credentials "$SOURCE_SECRET")
SOURCE_USER=$(echo "$SOURCE_CREDS" | jq -r '.username')
SOURCE_PASS=$(echo "$SOURCE_CREDS" | jq -r '.password')

DEST_CREDS=$(get_credentials "$DEST_SECRET")
DEST_USER=$(echo "$DEST_CREDS" | jq -r '.username')
DEST_PASS=$(echo "$DEST_CREDS" | jq -r '.password')

pass "Credentials resolved for both clusters"

# ============================================================================
# STEP 1: Get Intercluster LIF IPs
# ============================================================================
info "=== Step 1: Discovering Intercluster LIFs ==="

SOURCE_IC_IPS=$(ontap_api "$SOURCE_MGMT" GET "/network/ip/interfaces?services=intercluster&fields=ip.address" "$SOURCE_USER" "$SOURCE_PASS" | \
  jq -r '[.records[].ip.address] | join(",")')
info "Source intercluster IPs: ${SOURCE_IC_IPS}"

DEST_IC_IPS=$(ontap_api "$DEST_MGMT" GET "/network/ip/interfaces?services=intercluster&fields=ip.address" "$DEST_USER" "$DEST_PASS" | \
  jq -r '[.records[].ip.address] | join(",")')
info "Destination intercluster IPs: ${DEST_IC_IPS}"

[[ -z "$SOURCE_IC_IPS" ]] && fail "No intercluster LIFs found on source cluster"
[[ -z "$DEST_IC_IPS" ]] && fail "No intercluster LIFs found on destination cluster"
pass "Intercluster LIFs confirmed on both clusters"

# ============================================================================
# STEP 2: Create Cluster Peering
# ============================================================================
info "=== Step 2: Creating Cluster Peering ==="

# Check if peering already exists
EXISTING_PEER=$(ontap_api "$SOURCE_MGMT" GET "/cluster/peers" "$SOURCE_USER" "$SOURCE_PASS" | \
  jq -r '.num_records // 0')

if [[ "$EXISTING_PEER" -gt 0 ]]; then
  warn "Cluster peering already exists (${EXISTING_PEER} peer(s)). Skipping creation."
else
  # Generate passphrase
  PEER_PASSPHRASE="SnapMirrorVal-$(date +%s)"

  # Initiate from destination (offer)
  info "Initiating peer from destination cluster..."
  PEER_BODY=$(cat <<EOF
{
  "remote": {
    "ip_addresses": [$(echo "$SOURCE_IC_IPS" | sed 's/,/","/g' | sed 's/^/"/' | sed 's/$/"/' )]
  },
  "authentication": {
    "passphrase": "${PEER_PASSPHRASE}",
    "state": "passed"
  },
  "encryption": {
    "proposed": "tls_psk"
  }
}
EOF
  )
  PEER_RESULT=$(ontap_api "$DEST_MGMT" POST "/cluster/peers" "$DEST_USER" "$DEST_PASS" "$PEER_BODY")
  info "Peer result: $(echo "$PEER_RESULT" | jq -c '.job // .error // .')"

  # Accept from source
  info "Accepting peer from source cluster..."
  ACCEPT_BODY=$(cat <<EOF
{
  "remote": {
    "ip_addresses": [$(echo "$DEST_IC_IPS" | sed 's/,/","/g' | sed 's/^/"/' | sed 's/$/"/' )]
  },
  "authentication": {
    "passphrase": "${PEER_PASSPHRASE}",
    "state": "passed"
  },
  "encryption": {
    "proposed": "tls_psk"
  }
}
EOF
  )
  ACCEPT_RESULT=$(ontap_api "$SOURCE_MGMT" POST "/cluster/peers" "$SOURCE_USER" "$SOURCE_PASS" "$ACCEPT_BODY")
  info "Accept result: $(echo "$ACCEPT_RESULT" | jq -c '.job // .error // .')"

  # Wait for peering to establish
  info "Waiting for cluster peering to stabilize (30s)..."
  sleep 30
  pass "Cluster Peering created"
fi

# ============================================================================
# STEP 3: Create SVM Peering
# ============================================================================
info "=== Step 3: Creating SVM Peering ==="

# Get SVM UUIDs
SOURCE_SVM_UUID=$(ontap_api "$SOURCE_MGMT" GET "/svm/svms?name=${SOURCE_SVM_NAME}&fields=uuid" "$SOURCE_USER" "$SOURCE_PASS" | \
  jq -r '.records[0].uuid')
DEST_SVM_UUID=$(ontap_api "$DEST_MGMT" GET "/svm/svms?name=${DEST_SVM_NAME}&fields=uuid" "$DEST_USER" "$DEST_PASS" | \
  jq -r '.records[0].uuid')

info "Source SVM UUID: ${SOURCE_SVM_UUID}"
info "Destination SVM UUID: ${DEST_SVM_UUID}"

# Check existing SVM peer
EXISTING_SVM_PEER=$(ontap_api "$SOURCE_MGMT" GET "/svm/peers" "$SOURCE_USER" "$SOURCE_PASS" | \
  jq -r '.num_records // 0')

if [[ "$EXISTING_SVM_PEER" -gt 0 ]]; then
  warn "SVM peering already exists. Skipping."
else
  # Get peer cluster name
  PEER_CLUSTER_NAME=$(ontap_api "$SOURCE_MGMT" GET "/cluster/peers?fields=name" "$SOURCE_USER" "$SOURCE_PASS" | \
    jq -r '.records[0].name')

  SVM_PEER_BODY=$(cat <<EOF
{
  "svm": {"uuid": "${SOURCE_SVM_UUID}"},
  "peer": {
    "svm": {"name": "${DEST_SVM_NAME}"},
    "cluster": {"name": "${PEER_CLUSTER_NAME}"}
  },
  "applications": ["snapmirror", "flexcache"]
}
EOF
  )
  SVM_PEER_RESULT=$(ontap_api "$SOURCE_MGMT" POST "/svm/peers" "$SOURCE_USER" "$SOURCE_PASS" "$SVM_PEER_BODY")
  info "SVM Peer result: $(echo "$SVM_PEER_RESULT" | jq -c '.job // .error // .')"

  sleep 10
  pass "SVM Peering created (applications: snapmirror, flexcache)"
fi

# ============================================================================
# STEP 4: Create DP Volume on Destination (SnapMirror target)
# ============================================================================
info "=== Step 4: Creating DP volume on destination ==="

# Check if dest volume already exists
EXISTING_DEST_VOL=$(ontap_api "$DEST_MGMT" GET "/storage/volumes?name=${DEST_VOL_NAME}&svm.name=${DEST_SVM_NAME}" "$DEST_USER" "$DEST_PASS" | \
  jq -r '.num_records // 0')

if [[ "$EXISTING_DEST_VOL" -gt 0 ]]; then
  warn "Destination volume ${DEST_VOL_NAME} already exists. Skipping."
else
  # Get destination aggregate
  DEST_AGGR=$(ontap_api "$DEST_MGMT" GET "/storage/aggregates?fields=name" "$DEST_USER" "$DEST_PASS" | \
    jq -r '.records[0].name')

  DP_VOL_BODY=$(cat <<EOF
{
  "name": "${DEST_VOL_NAME}",
  "svm": {"name": "${DEST_SVM_NAME}"},
  "aggregates": [{"name": "${DEST_AGGR}"}],
  "size": $((DEST_VOL_SIZE_MB * 1048576)),
  "type": "dp",
  "style": "flexvol"
}
EOF
  )
  DP_RESULT=$(ontap_api "$DEST_MGMT" POST "/storage/volumes" "$DEST_USER" "$DEST_PASS" "$DP_VOL_BODY")
  info "DP Volume result: $(echo "$DP_RESULT" | jq -c '.job // .error // .')"
  sleep 5
  pass "DP volume created: ${DEST_VOL_NAME}"
fi

# ============================================================================
# STEP 5: Create SnapMirror Relationship
# ============================================================================
info "=== Step 5: Creating SnapMirror relationship ==="

SM_BODY=$(cat <<EOF
{
  "source": {
    "path": "${SOURCE_SVM_NAME}:${SOURCE_VOL_NAME}"
  },
  "destination": {
    "path": "${DEST_SVM_NAME}:${DEST_VOL_NAME}"
  },
  "policy": {"name": "MirrorAllSnapshots"},
  "create_destination": {"enabled": false}
}
EOF
)
SM_RESULT=$(ontap_api "$DEST_MGMT" POST "/snapmirror/relationships" "$DEST_USER" "$DEST_PASS" "$SM_BODY")
info "SnapMirror result: $(echo "$SM_RESULT" | jq -c '.job // .uuid // .error // .')"

# Get relationship UUID and initialize
SM_UUID=$(ontap_api "$DEST_MGMT" GET "/snapmirror/relationships?destination.path=${DEST_SVM_NAME}:${DEST_VOL_NAME}" "$DEST_USER" "$DEST_PASS" | \
  jq -r '.records[0].uuid // empty')

if [[ -n "$SM_UUID" ]]; then
  info "Initializing SnapMirror transfer..."
  INIT_BODY='{"state": "snapmirrored"}'
  ontap_api "$DEST_MGMT" PATCH "/snapmirror/relationships/${SM_UUID}" "$DEST_USER" "$DEST_PASS" "$INIT_BODY" > /dev/null
  pass "SnapMirror relationship created and initialized: ${SOURCE_SVM_NAME}:${SOURCE_VOL_NAME} → ${DEST_SVM_NAME}:${DEST_VOL_NAME}"
else
  warn "Could not find SnapMirror relationship UUID. Check manually."
fi

# ============================================================================
# STEP 6: Create FlexCache (cross-cluster)
# ============================================================================
info "=== Step 6: Creating FlexCache Cache Volume (cross-cluster) ==="

# Get source volume UUID
SOURCE_VOL_UUID=$(ontap_api "$SOURCE_MGMT" GET "/storage/volumes?name=${SOURCE_VOL_NAME}&svm.name=${SOURCE_SVM_NAME}&fields=uuid" "$SOURCE_USER" "$SOURCE_PASS" | \
  jq -r '.records[0].uuid // empty')

if [[ -z "$SOURCE_VOL_UUID" ]]; then
  warn "Source volume UUID not found. FlexCache creation skipped."
else
  # Get destination aggregate for FlexCache
  DEST_AGGR_FC=$(ontap_api "$DEST_MGMT" GET "/storage/aggregates?fields=name" "$DEST_USER" "$DEST_PASS" | \
    jq -r '.records[0].name')

  FC_BODY=$(cat <<EOF
{
  "name": "${FLEXCACHE_VOL_NAME}",
  "svm": {"name": "${DEST_SVM_NAME}"},
  "aggregates": [{"name": "${DEST_AGGR_FC}"}],
  "size": $((FLEXCACHE_SIZE_MB * 1048576)),
  "origins": [
    {
      "volume": {"name": "${SOURCE_VOL_NAME}"},
      "svm": {"name": "${SOURCE_SVM_NAME}"}
    }
  ],
  "junction_path": "/${FLEXCACHE_VOL_NAME}"
}
EOF
  )
  FC_RESULT=$(ontap_api "$DEST_MGMT" POST "/storage/volumes" "$DEST_USER" "$DEST_PASS" "$FC_BODY")
  info "FlexCache result: $(echo "$FC_RESULT" | jq -c '.job // .error // .')"
  pass "FlexCache Cache Volume created: ${FLEXCACHE_VOL_NAME} (Origin: ${SOURCE_SVM_NAME}:${SOURCE_VOL_NAME})"
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
info "=============================================="
info "  Inter-Cluster Setup Complete"
info "=============================================="
info "  Source: ${SOURCE_FS} / ${SOURCE_SVM_NAME}:${SOURCE_VOL_NAME}"
info "  Dest:   ${DEST_FS} / ${DEST_SVM_NAME}:${DEST_VOL_NAME} (SnapMirror DP)"
info "  Cache:  ${DEST_FS} / ${DEST_SVM_NAME}:${FLEXCACHE_VOL_NAME} (FlexCache)"
info ""
info "Next steps:"
info "  1. Write test data via S3 AP: aws s3 cp test.parquet s3://<s3ap-alias>/data/"
info "  2. Trigger SnapMirror update: ONTAP REST PATCH /snapmirror/relationships/<uuid>"
info "  3. Verify NFS read on FlexCache: mount -t nfs <dest-data-lif>:/${FLEXCACHE_VOL_NAME} /mnt/cache"
info "  4. Run TC-06/TC-07/TC-08: ./run-intercluster-tests.sh"
echo ""

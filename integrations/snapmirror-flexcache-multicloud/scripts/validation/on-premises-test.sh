#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# On-Premises FlexCache + SnapMirror Validation (Guide 03 / Guide 08)
#
# Validates:
#   1. Cluster Peering (FSx for ONTAP ↔ On-premises ONTAP via DX/VPN)
#   2. SVM Peering (flexcache + snapmirror applications)
#   3. FlexCache: Origin (FSx) → Cache (On-premises), NFS read verification
#   4. SnapMirror: FSx → On-premises, break + S3 AP re-attach readiness
#
# Prerequisites:
#   - on-premises-params.env filled in (copy from .example)
#   - Direct Connect or VPN active
#   - EC2 instance reachable via SSM with network path to on-premises ONTAP
#
# Usage:
#   ./on-premises-test.sh [--flexcache-only | --snapmirror-only | --teardown]
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/on-premises-params.env"

if [[ ! -f "$PARAMS_FILE" ]]; then
  echo "ERROR: $PARAMS_FILE not found. Copy on-premises-params.env.example and edit."
  exit 1
fi
source "$PARAMS_FILE"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
header() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }

MODE="${1:-full}"  # full | --flexcache-only | --snapmirror-only | --teardown

# Helper: ONTAP REST API call via SSM (to FSx)
ontap_fsx() {
  local method="$1" path="$2" body="${3:-}"
  local password
  password=$(aws secretsmanager get-secret-value --secret-id "$SECRET_ARN_A" \
    --query 'SecretString' --output text --region "$REGION_A" | python3 -c "import sys,json; print(json.loads(sys.stdin.read())['password'])")
  local mgmt_ip
  mgmt_ip=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' --output text --region "$REGION_A")

  local cmd="curl -sk -u fsxadmin:${password} -X ${method} \"https://${mgmt_ip}/api${path}\" -H 'Content-Type: application/json'"
  [[ -n "$body" ]] && cmd="${cmd} -d '${body}'"

  aws ssm send-command --instance-ids "$SSM_INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --parameters "commands=[\"$cmd\"]" \
    --output text --query 'Command.CommandId' --region "$REGION_A"
}

# Helper: ONTAP REST API call to on-premises cluster
ontap_onprem() {
  local method="$1" path="$2" body="${3:-}"
  local cmd="curl -sk -u ${ONPREM_USERNAME}:${ONPREM_PASSWORD} -X ${method} \"https://${ONPREM_MGMT_IP}/api${path}\" -H 'Content-Type: application/json'"
  [[ -n "$body" ]] && cmd="${cmd} -d '${body}'"

  aws ssm send-command --instance-ids "$SSM_INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --parameters "commands=[\"$cmd\"]" \
    --output text --query 'Command.CommandId' --region "$REGION_A"
}

# ============================================================================
header "On-Premises Validation: FSx for ONTAP ↔ On-Premises ONTAP"
info "Network type: $NETWORK_TYPE"
info "On-premises ONTAP: $ONPREM_MGMT_IP (IC: $ONPREM_IC_IP)"

# --- Step 0: Connectivity Check ---
header "Step 0: Connectivity Check"
info "Verifying EC2 can reach on-premises ONTAP management IP..."

PING_CMD_ID=$(aws ssm send-command --instance-ids "$SSM_INSTANCE_ID" \
  --document-name AWS-RunShellScript \
  --parameters 'commands=["curl -sk -o /dev/null -w \"%{http_code}\" -u '"${ONPREM_USERNAME}:${ONPREM_PASSWORD}"' https://'"${ONPREM_MGMT_IP}"'/api/cluster"]' \
  --output text --query 'Command.CommandId' --region "$REGION_A")

sleep 10
PING_RESULT=$(aws ssm get-command-invocation --command-id "$PING_CMD_ID" --instance-id "$SSM_INSTANCE_ID" \
  --query 'StandardOutputContent' --output text --region "$REGION_A" 2>/dev/null || echo "timeout")

if [[ "$PING_RESULT" == "200" ]]; then
  pass "On-premises ONTAP reachable (HTTP 200)"
else
  fail "Cannot reach on-premises ONTAP at $ONPREM_MGMT_IP (got: $PING_RESULT). Check DX/VPN and security groups."
fi

# --- Step 1: Cluster Peering ---
if [[ "$MODE" != "--teardown" ]]; then
  header "Step 1: Cluster Peering"
  info "Creating cluster peer: FSx for ONTAP ↔ On-premises ($ONPREM_IC_IP)"

  IC_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Intercluster.IpAddresses[0]' --output text --region "$REGION_A")
  info "FSx Intercluster LIF: $IC_A"

  PASSPHRASE="OnPremPeer$(date +%Y%m%d)"

  # Initiate from FSx side
  info "Initiating cluster peer from FSx (remote: $ONPREM_IC_IP)..."
  # TODO: Replace with actual SSM execution and response parsing
  echo "  CMD: POST /api/cluster/peers {remote.ip_addresses: [$ONPREM_IC_IP], authentication.passphrase: $PASSPHRASE}"

  # Accept on on-premises side
  info "Accepting cluster peer from on-premises (remote: $IC_A)..."
  echo "  CMD: POST /api/cluster/peers {remote.ip_addresses: [$IC_A], authentication.passphrase: $PASSPHRASE}"

  warn "TODO: Implement SSM-based execution (see cross-region-test.sh for pattern)"
fi

# --- Step 2: SVM Peering ---
if [[ "$MODE" != "--teardown" ]]; then
  header "Step 2: SVM Peering"
  info "Creating SVM peer: $SVM_NAME_A ↔ $ONPREM_SVM_NAME"
  echo "  CMD: POST /api/svm/peers {svm.name: $SVM_NAME_A, peer.svm.name: $ONPREM_SVM_NAME, applications: [flexcache, snapmirror]}"
  warn "TODO: Implement (same pattern as cross-region-test.sh Step 2)"
fi

# --- Step 3: FlexCache (Guide 03) ---
if [[ "$MODE" == "full" || "$MODE" == "--flexcache-only" ]]; then
  header "Step 3: FlexCache — Origin (FSx) → Cache (On-premises)"
  info "Creating origin volume on FSx..."
  echo "  CMD: POST /api/storage/volumes {name: flexcache_origin_onprem, svm.name: $SVM_NAME_A, size: 1GB, style: flexvol}"

  info "Creating FlexCache on on-premises cluster..."
  echo "  CMD: POST /api/storage/flexcache/flexcaches {name: flexcache_from_fsx, svm.name: $ONPREM_SVM_NAME, origins: [{volume.name: flexcache_origin_onprem, svm.name: $SVM_NAME_A}], aggregates: [{name: $ONPREM_AGGR_NAME}]}"

  info "Writing test data to origin via S3 AP..."
  echo "  CMD: aws s3api put-object --bucket <s3-ap-alias> --key test/onprem-validation.txt --body <file>"

  info "Verifying NFS read from on-premises FlexCache..."
  echo "  CMD: ssh <onprem-client> 'cat /mnt/flexcache_from_fsx/test/onprem-validation.txt'"

  warn "TODO: Full implementation pending on-premises lab access"
fi

# --- Step 4: SnapMirror (Guide 08) ---
if [[ "$MODE" == "full" || "$MODE" == "--snapmirror-only" ]]; then
  header "Step 4: SnapMirror — FSx → On-premises DR"
  info "Creating SnapMirror destination volume on on-premises..."
  echo "  CMD: POST /api/storage/volumes {name: dr_from_fsx, svm.name: $ONPREM_SVM_NAME, type: dp}"

  info "Creating SnapMirror relationship..."
  echo "  CMD: POST /api/snapmirror/relationships {source.path: $SVM_NAME_A:flexcache_origin_onprem, destination.path: $ONPREM_SVM_NAME:dr_from_fsx}"

  info "Initializing SnapMirror transfer..."
  echo "  CMD: POST /api/snapmirror/relationships/{uuid}/transfers"

  info "Breaking SnapMirror for failover test..."
  echo "  CMD: PATCH /api/snapmirror/relationships/{uuid} {state: broken_off}"

  info "Verifying NFS access on on-premises destination..."
  echo "  CMD: ssh <onprem-client> 'ls /mnt/dr_from_fsx/test/'"

  warn "TODO: Full implementation pending on-premises lab access"
fi

# --- Teardown ---
if [[ "$MODE" == "--teardown" ]]; then
  header "Teardown: On-premises validation resources"
  info "Deleting FlexCache on on-premises..."
  echo "  CMD: DELETE /api/storage/flexcache/flexcaches/{uuid} (on-premises)"
  info "Deleting origin volume on FSx..."
  echo "  CMD: DELETE /api/storage/volumes/{uuid}?force=true (FSx)"
  info "Deleting SnapMirror relationship..."
  echo "  CMD: DELETE /api/snapmirror/relationships/{uuid} (FSx)"
  info "Deleting SVM peer..."
  echo "  CMD: DELETE /api/svm/peers/{uuid} (FSx)"
  info "Deleting cluster peer..."
  echo "  CMD: DELETE /api/cluster/peers/{uuid} (FSx)"
  warn "TODO: Full implementation pending on-premises lab access"
fi

echo ""
header "Summary"
echo "  On-premises validation script template."
echo "  Steps marked TODO require on-premises ONTAP lab access."
echo "  See: docs/en/demo-guide-03-flexcache-on-premises.md"
echo "  See: docs/en/demo-guide-08-snapmirror-on-premises.md"

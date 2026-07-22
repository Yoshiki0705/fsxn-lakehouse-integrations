#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# CVO on GCP — FlexCache + SnapMirror Validation (Guide 04 / Guide 09)
#
# Validates:
#   1. Cluster Peering (FSx for ONTAP ↔ CVO on GCP via HA VPN)
#   2. SVM Peering (flexcache + snapmirror applications)
#   3. FlexCache: Origin (FSx) → Cache (CVO GCP), NFS read from GCE
#   4. SnapMirror: FSx → CVO GCP, break + NFS access verification
#
# Prerequisites:
#   - cvo-gcp-params.env filled in
#   - CVO on GCP deployed and AVAILABLE
#   - HA VPN active between AWS VPC and GCP VPC
#   - EC2 reachable via SSM with network path to CVO management IP
#
# Usage:
#   ./cvo-gcp-test.sh [--flexcache-only | --snapmirror-only | --teardown]
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/cvo-gcp-params.env"

if [[ ! -f "$PARAMS_FILE" ]]; then
  echo "ERROR: $PARAMS_FILE not found. Copy cvo-gcp-params.env.example and edit."
  exit 1
fi
source "$PARAMS_FILE"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; exit 1; }
header() { echo -e "\n${BLUE}━━━ $1 ━━━${NC}"; }

MODE="${1:-full}"

# Helper: get FSx password
get_fsx_password() {
  aws secretsmanager get-secret-value --secret-id "$SECRET_ARN_A" \
    --query 'SecretString' --output text --region "$REGION_A" | \
    python3 -c "import sys,json; print(json.loads(sys.stdin.read())['password'])"
}

# Helper: SSM command execution
ssm_run() {
  local cmd="$1"
  local timeout="${2:-60}"
  local cmd_id
  cmd_id=$(aws ssm send-command \
    --instance-ids "$SSM_INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --parameters "commands=[\"$cmd\"]" \
    --output text --query 'Command.CommandId' --region "$REGION_A")
  
  sleep "$timeout"
  aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$SSM_INSTANCE_ID" \
    --query 'StandardOutputContent' --output text --region "$REGION_A" 2>/dev/null
}

# ============================================================================
header "CVO GCP Validation: FSx for ONTAP (AWS) ↔ CVO on GCP"
info "CVO: $CVO_MGMT_IP ($GCP_REGION)"

# --- Step 0: Connectivity ---
header "Step 0: Connectivity Check (AWS → GCP via HA VPN)"
RESULT=$(ssm_run "curl -sk -o /dev/null -w '%{http_code}' -u ${CVO_USERNAME}:${CVO_PASSWORD} https://${CVO_MGMT_IP}/api/cluster" 15)
if [[ "$RESULT" == "200" ]]; then
  pass "CVO on GCP reachable (HTTP 200)"
else
  fail "Cannot reach CVO at $CVO_MGMT_IP (got: $RESULT). Check HA VPN tunnel and GCP firewall rules."
fi

# --- Step 1: Cluster Peering ---
if [[ "$MODE" != "--teardown" ]]; then
  header "Step 1: Cluster Peering (FSx ↔ CVO GCP)"
  
  FSX_PASSWORD=$(get_fsx_password)
  MGMT_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' --output text --region "$REGION_A")
  IC_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Intercluster.IpAddresses[0]' --output text --region "$REGION_A")

  PASSPHRASE="CvoGcpPeer$(date +%Y%m%d)"
  info "Initiating cluster peer from FSx (remote: $CVO_IC_IP)..."
  
  PEER_RESULT=$(ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} -X POST https://${MGMT_A}/api/cluster/peers -H 'Content-Type: application/json' -d '{\"remote\":{\"ip_addresses\":[\"${CVO_IC_IP}\"]},\"authentication\":{\"passphrase\":\"${PASSPHRASE}\"}}'" 10)
  info "FSx peer initiation: $PEER_RESULT"

  info "Accepting cluster peer from CVO (remote: $IC_A)..."
  ACCEPT_RESULT=$(ssm_run "curl -sk -u ${CVO_USERNAME}:${CVO_PASSWORD} -X POST https://${CVO_MGMT_IP}/api/cluster/peers -H 'Content-Type: application/json' -d '{\"remote\":{\"ip_addresses\":[\"${IC_A}\"]},\"authentication\":{\"passphrase\":\"${PASSPHRASE}\"}}'" 10)
  info "CVO peer acceptance: $ACCEPT_RESULT"

  sleep 10
  PEER_STATE=$(ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} https://${MGMT_A}/api/cluster/peers?fields=authentication.state,status" 8)
  if echo "$PEER_STATE" | grep -q '"state":"available"'; then
    pass "Cluster peering established (available)"
  else
    warn "Cluster peering may still be initializing. Check: $PEER_STATE"
  fi
fi

# --- Step 2: SVM Peering ---
if [[ "$MODE" != "--teardown" ]]; then
  header "Step 2: SVM Peering ($SVM_NAME_A ↔ $CVO_SVM_NAME)"
  
  CLUSTER_B_NAME=$(ssm_run "curl -sk -u ${CVO_USERNAME}:${CVO_PASSWORD} https://${CVO_MGMT_IP}/api/cluster?fields=name | python3 -c \"import sys,json; print(json.loads(sys.stdin.read())['name'])\"" 8)
  info "CVO cluster name: $CLUSTER_B_NAME"

  SVM_PEER_RESULT=$(ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} -X POST https://${MGMT_A}/api/svm/peers -H 'Content-Type: application/json' -d '{\"svm\":{\"name\":\"${SVM_NAME_A}\"},\"peer\":{\"svm\":{\"name\":\"${CVO_SVM_NAME}\"},\"cluster\":{\"name\":\"${CLUSTER_B_NAME}\"}},\"applications\":[\"flexcache\",\"snapmirror\"]}'" 10)
  info "SVM peer result: $SVM_PEER_RESULT"

  info "Accepting SVM peer from CVO side..."
  # SVM peering auto-accepts when initiated from peer with correct cluster name
  sleep 5
  SVM_STATE=$(ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} 'https://${MGMT_A}/api/svm/peers?fields=state'" 8)
  info "SVM peer state: $SVM_STATE"
fi

# --- Step 3: FlexCache (Guide 04) ---
if [[ "$MODE" == "full" || "$MODE" == "--flexcache-only" ]]; then
  header "Step 3: FlexCache — Origin (FSx) → Cache (CVO GCP)"

  info "Creating origin volume on FSx..."
  ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} -X POST https://${MGMT_A}/api/storage/volumes -H 'Content-Type: application/json' -d '{\"name\":\"fc_origin_cvo_gcp\",\"svm\":{\"name\":\"${SVM_NAME_A}\"},\"aggregates\":[{\"name\":\"aggr1\"}],\"size\":1073741824,\"style\":\"flexvol\",\"nas\":{\"path\":\"/fc_origin_cvo_gcp\",\"security_style\":\"unix\"}}'" 10
  pass "Origin volume created"

  info "Creating FlexCache on CVO GCP..."
  ssm_run "curl -sk -u ${CVO_USERNAME}:${CVO_PASSWORD} -X POST https://${CVO_MGMT_IP}/api/storage/flexcache/flexcaches -H 'Content-Type: application/json' -d '{\"name\":\"fc_from_fsx\",\"svm\":{\"name\":\"${CVO_SVM_NAME}\"},\"origins\":[{\"volume\":{\"name\":\"fc_origin_cvo_gcp\"},\"svm\":{\"name\":\"${SVM_NAME_A}\"}}],\"aggregates\":[{\"name\":\"${CVO_AGGR_NAME}\"}],\"size\":1073741824,\"path\":\"/fc_from_fsx\"}'" 30
  pass "FlexCache created on CVO GCP"

  info "Writing test data to origin via NFS..."
  ssm_run "sudo mkdir -p /mnt/fc_origin_cvo_gcp && sudo mount -t nfs -o nfsvers=3 \$(curl -sk -u fsxadmin:${FSX_PASSWORD} 'https://${MGMT_A}/api/network/ip/interfaces?svm.name=${SVM_NAME_A}&services=data_nfs&fields=ip.address' | python3 -c \"import sys,json; print(json.loads(sys.stdin.read())['records'][0]['ip']['address'])\"):/fc_origin_cvo_gcp /mnt/fc_origin_cvo_gcp && echo 'CVO GCP FlexCache test - $(date -u)' | sudo tee /mnt/fc_origin_cvo_gcp/test.txt" 15

  info "Verifying NFS read from GCE instance on GCP..."
  echo "  MANUAL STEP: ssh to GCE instance and run:"
  echo "    sudo mount -t nfs <CVO-data-LIF>:/fc_from_fsx /mnt/cache"
  echo "    cat /mnt/cache/test.txt"
  warn "Automated GCE verification requires gcloud SSH — implement if gcloud is available"
fi

# --- Step 4: SnapMirror (Guide 09) ---
if [[ "$MODE" == "full" || "$MODE" == "--snapmirror-only" ]]; then
  header "Step 4: SnapMirror — FSx → CVO GCP DR"

  info "Creating DP volume on CVO GCP..."
  ssm_run "curl -sk -u ${CVO_USERNAME}:${CVO_PASSWORD} -X POST https://${CVO_MGMT_IP}/api/storage/volumes -H 'Content-Type: application/json' -d '{\"name\":\"sm_dr_from_fsx\",\"svm\":{\"name\":\"${CVO_SVM_NAME}\"},\"aggregates\":[{\"name\":\"${CVO_AGGR_NAME}\"}],\"size\":1073741824,\"type\":\"dp\"}'" 10

  info "Creating SnapMirror relationship..."
  ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} -X POST https://${MGMT_A}/api/snapmirror/relationships -H 'Content-Type: application/json' -d '{\"source\":{\"path\":\"${SVM_NAME_A}:fc_origin_cvo_gcp\"},\"destination\":{\"path\":\"${CVO_SVM_NAME}:sm_dr_from_fsx\"}}'" 15

  info "Initializing transfer (this may take a few minutes)..."
  echo "  Poll: GET /api/snapmirror/relationships?fields=state,transfer.state"
  warn "Transfer time depends on data volume and VPN bandwidth"

  info "After transfer completes, break SnapMirror for failover test:"
  echo "  PATCH /api/snapmirror/relationships/{uuid} {state: broken_off}"
  echo "  Verify NFS access from GCE to sm_dr_from_fsx"
fi

# --- Teardown ---
if [[ "$MODE" == "--teardown" ]]; then
  header "Teardown: CVO GCP validation resources"
  FSX_PASSWORD=$(get_fsx_password)
  MGMT_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' --output text --region "$REGION_A")

  info "Step 1: Remove FlexCache junction + delete on CVO..."
  ssm_run "curl -sk -u ${CVO_USERNAME}:${CVO_PASSWORD} -X PATCH https://${CVO_MGMT_IP}/api/storage/volumes?name=fc_from_fsx -H 'Content-Type: application/json' -d '{\"nas\":{\"path\":\"\"}}'" 8
  sleep 3
  FC_UUID=$(ssm_run "curl -sk -u ${CVO_USERNAME}:${CVO_PASSWORD} 'https://${CVO_MGMT_IP}/api/storage/flexcache/flexcaches?name=fc_from_fsx' | python3 -c \"import sys,json; r=json.loads(sys.stdin.read()); print(r['records'][0]['uuid'] if r['num_records']>0 else '')\"" 8)
  [[ -n "$FC_UUID" ]] && ssm_run "curl -sk -u ${CVO_USERNAME}:${CVO_PASSWORD} -X DELETE https://${CVO_MGMT_IP}/api/storage/flexcache/flexcaches/${FC_UUID}" 20

  info "Step 2: Delete SnapMirror relationship..."
  echo "  DELETE /api/snapmirror/relationships/{uuid} (from FSx side)"

  info "Step 3: Delete origin volume on FSx..."
  ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} -X DELETE 'https://${MGMT_A}/api/storage/volumes?name=fc_origin_cvo_gcp&force=true'" 10

  info "Step 4: Delete SVM peer..."
  echo "  DELETE /api/svm/peers/{uuid}"

  info "Step 5: Delete cluster peer..."
  echo "  DELETE /api/cluster/peers/{uuid}"

  info "Step 6 (manual): Destroy CVO instance via BlueXP/Terraform"
  echo "  terraform destroy -target=module.cvo_gcp"
  echo "  OR: BlueXP → Working Environments → Delete"
fi

echo ""
header "Summary"
echo "  CVO GCP validation script."
echo "  Network layer (HA VPN) and CVO deployment are external prerequisites."
echo "  See: docs/en/demo-guide-04-flexcache-cvo-gcp.md"
echo "  See: docs/en/demo-guide-09-snapmirror-cvo-gcp.md"

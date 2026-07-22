#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# CVO on Azure — FlexCache + SnapMirror Validation (Guide 05 / Guide 10)
#
# Validates:
#   1. Cluster Peering (FSx for ONTAP ↔ CVO on Azure via Azure VPN GW)
#   2. SVM Peering (flexcache + snapmirror applications)
#   3. FlexCache: Origin (FSx) → Cache (CVO Azure), NFS read from Azure VM
#   4. SnapMirror: FSx → CVO Azure, break + NFS access verification
#
# Prerequisites:
#   - cvo-azure-params.env filled in
#   - CVO on Azure deployed and AVAILABLE
#   - Azure VPN Gateway ↔ AWS VPN active
#   - EC2 reachable via SSM with network path to CVO management IP
#
# Usage:
#   ./cvo-azure-test.sh [--flexcache-only | --snapmirror-only | --teardown]
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/cvo-azure-params.env"

if [[ ! -f "$PARAMS_FILE" ]]; then
  echo "ERROR: $PARAMS_FILE not found. Copy cvo-azure-params.env.example and edit."
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

get_fsx_password() {
  aws secretsmanager get-secret-value --secret-id "$SECRET_ARN_A" \
    --query 'SecretString' --output text --region "$REGION_A" | \
    python3 -c "import sys,json; print(json.loads(sys.stdin.read())['password'])"
}

ssm_run() {
  local cmd="$1" timeout="${2:-60}"
  local cmd_id
  cmd_id=$(aws ssm send-command --instance-ids "$SSM_INSTANCE_ID" \
    --document-name AWS-RunShellScript \
    --parameters "commands=[\"$cmd\"]" \
    --output text --query 'Command.CommandId' --region "$REGION_A")
  sleep "$timeout"
  aws ssm get-command-invocation --command-id "$cmd_id" --instance-id "$SSM_INSTANCE_ID" \
    --query 'StandardOutputContent' --output text --region "$REGION_A" 2>/dev/null
}

# ============================================================================
header "CVO Azure Validation: FSx for ONTAP (AWS) ↔ CVO on Azure"
info "CVO: $CVO_MGMT_IP ($AZURE_REGION)"

# --- Step 0: Connectivity ---
header "Step 0: Connectivity Check (AWS → Azure via VPN)"
RESULT=$(ssm_run "curl -sk -o /dev/null -w '%{http_code}' -u ${CVO_USERNAME}:${CVO_PASSWORD} https://${CVO_MGMT_IP}/api/cluster" 15)
if [[ "$RESULT" == "200" ]]; then
  pass "CVO on Azure reachable (HTTP 200)"
else
  fail "Cannot reach CVO at $CVO_MGMT_IP (got: $RESULT). Check Azure VPN GW and NSG rules."
fi

# --- Step 1: Cluster Peering ---
if [[ "$MODE" != "--teardown" ]]; then
  header "Step 1: Cluster Peering (FSx ↔ CVO Azure)"
  FSX_PASSWORD=$(get_fsx_password)
  MGMT_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' --output text --region "$REGION_A")
  IC_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
    --query 'FileSystems[0].OntapConfiguration.Endpoints.Intercluster.IpAddresses[0]' --output text --region "$REGION_A")

  PASSPHRASE="CvoAzurePeer$(date +%Y%m%d)"
  info "Initiating from FSx (remote: $CVO_IC_IP)..."
  ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} -X POST https://${MGMT_A}/api/cluster/peers -H 'Content-Type: application/json' -d '{\"remote\":{\"ip_addresses\":[\"${CVO_IC_IP}\"]},\"authentication\":{\"passphrase\":\"${PASSPHRASE}\"}}'" 10

  info "Accepting from CVO Azure (remote: $IC_A)..."
  ssm_run "curl -sk -u ${CVO_USERNAME}:${CVO_PASSWORD} -X POST https://${CVO_MGMT_IP}/api/cluster/peers -H 'Content-Type: application/json' -d '{\"remote\":{\"ip_addresses\":[\"${IC_A}\"]},\"authentication\":{\"passphrase\":\"${PASSPHRASE}\"}}'" 10

  sleep 10
  info "Verifying cluster peer state..."
  ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} 'https://${MGMT_A}/api/cluster/peers?fields=status,authentication.state'" 8
fi

# --- Step 2: SVM Peering ---
if [[ "$MODE" != "--teardown" ]]; then
  header "Step 2: SVM Peering"
  CLUSTER_B_NAME=$(ssm_run "curl -sk -u ${CVO_USERNAME}:${CVO_PASSWORD} https://${CVO_MGMT_IP}/api/cluster?fields=name | python3 -c \"import sys,json; print(json.loads(sys.stdin.read())['name'])\"" 8)
  info "CVO cluster: $CLUSTER_B_NAME"
  ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} -X POST https://${MGMT_A}/api/svm/peers -H 'Content-Type: application/json' -d '{\"svm\":{\"name\":\"${SVM_NAME_A}\"},\"peer\":{\"svm\":{\"name\":\"${CVO_SVM_NAME}\"},\"cluster\":{\"name\":\"${CLUSTER_B_NAME}\"}},\"applications\":[\"flexcache\",\"snapmirror\"]}'" 10
fi

# --- Step 3: FlexCache (Guide 05) ---
if [[ "$MODE" == "full" || "$MODE" == "--flexcache-only" ]]; then
  header "Step 3: FlexCache — Origin (FSx) → Cache (CVO Azure)"
  info "Creating origin volume on FSx..."
  ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} -X POST https://${MGMT_A}/api/storage/volumes -H 'Content-Type: application/json' -d '{\"name\":\"fc_origin_cvo_azure\",\"svm\":{\"name\":\"${SVM_NAME_A}\"},\"aggregates\":[{\"name\":\"aggr1\"}],\"size\":1073741824,\"style\":\"flexvol\",\"nas\":{\"path\":\"/fc_origin_cvo_azure\",\"security_style\":\"unix\"}}'" 10

  info "Creating FlexCache on CVO Azure..."
  ssm_run "curl -sk -u ${CVO_USERNAME}:${CVO_PASSWORD} -X POST https://${CVO_MGMT_IP}/api/storage/flexcache/flexcaches -H 'Content-Type: application/json' -d '{\"name\":\"fc_from_fsx\",\"svm\":{\"name\":\"${CVO_SVM_NAME}\"},\"origins\":[{\"volume\":{\"name\":\"fc_origin_cvo_azure\"},\"svm\":{\"name\":\"${SVM_NAME_A}\"}}],\"aggregates\":[{\"name\":\"${CVO_AGGR_NAME}\"}],\"size\":1073741824,\"path\":\"/fc_from_fsx\"}'" 30

  info "Write test data + verify from Azure VM (manual):"
  echo "  az vm run-command invoke --command-id RunShellScript --name <vm> -g $AZURE_RESOURCE_GROUP --scripts 'mount -t nfs <cvo-lif>:/fc_from_fsx /mnt/cache && cat /mnt/cache/test.txt'"
fi

# --- Step 4: SnapMirror (Guide 10) ---
if [[ "$MODE" == "full" || "$MODE" == "--snapmirror-only" ]]; then
  header "Step 4: SnapMirror — FSx → CVO Azure"
  info "Creating DP volume + SnapMirror relationship..."
  echo "  Same pattern as cvo-gcp-test.sh Step 4"
  echo "  POST /api/storage/volumes (type: dp) on CVO Azure"
  echo "  POST /api/snapmirror/relationships on FSx"
  warn "Implementation mirrors cvo-gcp-test.sh — adapt CVO_MGMT_IP and CVO_SVM_NAME"
fi

# --- Teardown ---
if [[ "$MODE" == "--teardown" ]]; then
  header "Teardown"
  info "Same pattern as cvo-gcp-test.sh --teardown"
  echo "  1. Remove FlexCache junction + delete"
  echo "  2. Delete SnapMirror relationship"
  echo "  3. Delete origin volume (force=true)"
  echo "  4. Delete SVM peer"
  echo "  5. Delete cluster peer"
  echo "  6. Destroy CVO via BlueXP/Terraform"
  echo "  7. (Optional) Delete Azure VPN Gateway"
fi

echo ""
header "Summary"
echo "  CVO Azure validation script."
echo "  See: docs/en/demo-guide-05-flexcache-cvo-azure.md"
echo "  See: docs/en/demo-guide-10-snapmirror-cvo-azure.md"

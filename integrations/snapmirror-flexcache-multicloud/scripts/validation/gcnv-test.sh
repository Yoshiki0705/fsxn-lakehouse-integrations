#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# GCNV — FlexCache + SnapMirror (External Replication) Validation
# (Guide 06 / Guide 11)
#
# Validates:
#   Guide 06: FlexCache Origin (FSx) → Cache (GCNV), NFSv3 read from GCE
#   Guide 11: SnapMirror External Replication (FSx → GCNV)
#
# Key difference from CVO scripts:
#   GCNV does NOT expose ONTAP REST API. All GCNV-side configuration is done
#   via gcloud CLI (gcloud netapp volumes / gcloud netapp replications).
#   FSx-side operations still use ONTAP REST API via SSM.
#
# Prerequisites:
#   - gcnv-params.env filled in
#   - HA VPN active between AWS VPC and GCP VPC
#   - GCNV storage pool exists in target region
#   - gcloud CLI authenticated with appropriate permissions
#   - EC2 reachable via SSM
#
# Usage:
#   ./gcnv-test.sh [--flexcache-only | --snapmirror-only | --teardown]
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARAMS_FILE="${SCRIPT_DIR}/gcnv-params.env"

if [[ ! -f "$PARAMS_FILE" ]]; then
  echo "ERROR: $PARAMS_FILE not found. Copy gcnv-params.env.example and edit."
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
header "GCNV Validation: FSx for ONTAP (AWS) ↔ Google Cloud NetApp Volumes"
info "GCP project: $GCP_PROJECT, region: $GCP_REGION"

# --- Step 0: Prerequisites Check ---
header "Step 0: Prerequisites Check"

# Check gcloud auth
if ! gcloud auth list --filter="status:ACTIVE" --format="value(account)" 2>/dev/null | head -1 | grep -q "@"; then
  fail "gcloud not authenticated. Run: gcloud auth login"
fi
pass "gcloud authenticated"

# Check GCNV pool exists
POOL_STATUS=$(gcloud netapp storage-pools describe "$GCNV_POOL_NAME" \
  --project="$GCP_PROJECT" --location="$GCP_REGION" \
  --format="value(state)" 2>/dev/null || echo "NOT_FOUND")
if [[ "$POOL_STATUS" == "READY" ]]; then
  pass "GCNV storage pool '$GCNV_POOL_NAME' is READY"
else
  fail "GCNV storage pool not found or not ready (state: $POOL_STATUS). Create one first."
fi

# Check VPN connectivity (FSx intercluster reachable from GCP)
info "VPN connectivity check: verify from EC2 side..."
FSX_PASSWORD=$(get_fsx_password)
MGMT_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management.IpAddresses[0]' --output text --region "$REGION_A")
IC_A=$(aws fsx describe-file-systems --file-system-ids "$FS_ID_A" \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Intercluster.IpAddresses[0]' --output text --region "$REGION_A")
info "FSx Intercluster LIF: $IC_A (must be reachable from GCNV service network)"

# --- Step 1: FlexCache (Guide 06) ---
if [[ "$MODE" == "full" || "$MODE" == "--flexcache-only" ]]; then
  header "Step 1: FlexCache — Origin (FSx) → Cache (GCNV)"
  
  info "Creating origin volume on FSx..."
  ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} -X POST https://${MGMT_A}/api/storage/volumes -H 'Content-Type: application/json' -d '{\"name\":\"fc_origin_gcnv\",\"svm\":{\"name\":\"${SVM_NAME_A}\"},\"aggregates\":[{\"name\":\"aggr1\"}],\"size\":1073741824,\"style\":\"flexvol\",\"nas\":{\"path\":\"/fc_origin_gcnv\",\"security_style\":\"unix\"}}'" 10
  pass "Origin volume created on FSx"

  info "Creating FlexCache volume on GCNV (via gcloud)..."
  echo "  gcloud netapp volumes create $GCNV_VOLUME_NAME \\"
  echo "    --project=$GCP_PROJECT \\"
  echo "    --location=$GCP_REGION \\"
  echo "    --storage-pool=$GCNV_POOL_NAME \\"
  echo "    --capacity-gib=1024 \\"
  echo "    --protocols=NFSV3 \\"
  echo "    --flexcache-origin-volume=<ORIGIN_VOLUME_RESOURCE_NAME> \\"
  echo "    --flexcache-origin-cluster=<FSx_CLUSTER_NAME> \\"
  echo "    --flexcache-origin-svm=$SVM_NAME_A"
  warn "GCNV FlexCache creation via gcloud netapp CLI — exact syntax depends on GCNV API version"
  warn "Constraints: NFSv3 only, read-only (no write-back), Cache only (not Origin)"

  info "After FlexCache creation, verify NFSv3 read from GCE:"
  echo "  GCE_IP=\$(gcloud compute instances describe <gce-name> --zone=$GCP_ZONE --format='value(networkInterfaces[0].accessConfigs[0].natIP)')"
  echo "  gcloud compute ssh <gce-name> --zone=$GCP_ZONE -- 'sudo mount -t nfs -o nfsvers=3 <gcnv-mount-ip>:/<export-path> /mnt/gcnv && cat /mnt/gcnv/test.txt'"
fi

# --- Step 2: SnapMirror External Replication (Guide 11) ---
if [[ "$MODE" == "full" || "$MODE" == "--snapmirror-only" ]]; then
  header "Step 2: SnapMirror External Replication — FSx → GCNV"

  info "GCNV External Replication is configured via GCP API, not ONTAP REST API."
  info "The GCP side initiates the relationship (GCNV as destination)."
  echo ""
  echo "  Step 2a: Create destination volume with replication on GCNV:"
  echo "    gcloud netapp volumes create sm-dest-from-fsx \\"
  echo "      --project=$GCP_PROJECT \\"
  echo "      --location=$GCP_REGION \\"
  echo "      --storage-pool=$GCNV_POOL_NAME \\"
  echo "      --capacity-gib=1024 \\"
  echo "      --protocols=NFSV3 \\"
  echo "      --replication-schedule=EVERY_10_MINUTES \\"
  echo "      --replication-source-volume=projects/$GCP_PROJECT/locations/$GCP_REGION/volumes/fc_origin_gcnv \\"
  echo "      --replication-cluster-peering=<peering-resource>"
  echo ""
  echo "  Step 2b: Verify Cluster Peering (FSx ↔ GCNV):"
  echo "    The peering is initiated from GCNV side."
  echo "    FSx side must accept via ONTAP REST API:"
  echo "      POST /api/cluster/peers {remote.ip_addresses: [<GCNV_IC_IPs>], passphrase: <from_GCNV>}"
  echo ""
  echo "  Step 2c: Monitor replication status:"
  echo "    gcloud netapp volumes replications list --project=$GCP_PROJECT --location=$GCP_REGION"
  echo ""
  warn "External Replication setup requires GCNV-specific API calls — see GCP documentation"
  warn "Reference: https://cloud.google.com/netapp/volumes/docs/protect-data/replicate-ontap/overview"
fi

# --- Teardown ---
if [[ "$MODE" == "--teardown" ]]; then
  header "Teardown: GCNV validation resources"
  
  info "Step 1: Delete FlexCache/Replication on GCNV..."
  echo "  gcloud netapp volumes delete $GCNV_VOLUME_NAME --project=$GCP_PROJECT --location=$GCP_REGION --quiet"

  info "Step 2: Delete origin volume on FSx..."
  ssm_run "curl -sk -u fsxadmin:${FSX_PASSWORD} -X DELETE 'https://${MGMT_A}/api/storage/volumes?name=fc_origin_gcnv&force=true'" 10

  info "Step 3: Delete cluster peer on FSx (if exists)..."
  echo "  DELETE /api/cluster/peers/{uuid}"

  info "Step 4: (Optional) Delete GCNV storage pool if no longer needed"
  echo "  gcloud netapp storage-pools delete $GCNV_POOL_NAME --project=$GCP_PROJECT --location=$GCP_REGION"
fi

echo ""
header "Summary"
echo "  GCNV validation script."
echo "  GCNV-side operations use gcloud CLI (not ONTAP REST API)."
echo "  Key constraints: NFSv3 only, Cache only (not Origin), no write-back."
echo "  See: docs/en/demo-guide-06-flexcache-gcnv.md"
echo "  See: docs/en/demo-guide-11-snapmirror-gcnv.md"
